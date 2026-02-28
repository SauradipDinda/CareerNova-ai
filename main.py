"""CareerNova-AI  --  Main FastAPI application."""

import logging
import os
import uuid
from pathlib import Path
from typing import Optional

from fastapi import (
    FastAPI, Request, Depends, HTTPException, UploadFile, File, Form, status,
)
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from config import UPLOAD_DIR, MAX_PDF_SIZE_MB, CHAT_RATE_LIMIT, OPENROUTER_API_KEY
from database import get_db, init_db
from models import User, Portfolio
from auth import (
    create_user, authenticate_user, create_access_token,
    get_current_user, get_optional_user, get_user_by_username, get_user_by_email,
    verify_password, hash_password
)
from generator import process_resume
from exporter import generate_portfolio_ppt
from rag_engine import index_resume, chat as rag_chat, delete_index
from jobs_engine import get_recommended_jobs, JobFilter

# ---------- Logging ----------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# ---------- App setup ----------
app = FastAPI(title="CareerNova-AI", version="1.0.0")

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

BASE_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

os.makedirs(UPLOAD_DIR, exist_ok=True)


@app.on_event("startup")
def on_startup():
    init_db()

    # ---- DB connection check ----
    from sqlalchemy import text
    from database import engine
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()
            db_url = str(engine.url)
            # Mask password in logs
            masked = db_url.replace(str(engine.url.password or ""), "***")
            logger.info("✅ Database connected successfully  |  %s", masked)
    except Exception as e:
        logger.error("❌ Database connection FAILED: %s", e)

    logger.info("CareerNova-AI started")

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"Validation error for {request.url}: {exc.errors()}")
    # Don't log the body as it might contain non-serializable data
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception for {request.url}: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": str(exc)},
    )


# ========================================================================
# Pydantic request schemas
# ========================================================================

class SignupRequest(BaseModel):
    username: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class ChatRequest(BaseModel):
    message: str
    history: Optional[list] = None

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

class ApiKeyUpdate(BaseModel):
    openrouter_api_key: str

# ========================================================================
# Page routes (HTML)
# ========================================================================

@app.get("/", response_class=HTMLResponse)
async def home(request: Request, user: Optional[User] = Depends(get_optional_user)):
    return templates.TemplateResponse("index.html", {"request": request, "user": user})


@app.get("/about", response_class=HTMLResponse)
async def about_page(request: Request, user: Optional[User] = Depends(get_optional_user)):
    return templates.TemplateResponse("about.html", {"request": request, "user": user})


@app.get("/contact", response_class=HTMLResponse)
async def contact_page(request: Request, user: Optional[User] = Depends(get_optional_user)):
    return templates.TemplateResponse("contact.html", {"request": request, "user": user})


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "mode": "login"})


@app.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "mode": "signup"})


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(
    request: Request,
    user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    if user is None:
        return RedirectResponse(url="/login", status_code=302)
    portfolio = db.query(Portfolio).filter(Portfolio.user_id == user.id).first()
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "portfolio": portfolio,
    })


from sqlalchemy import func

@app.get("/p/{slug}", response_class=HTMLResponse)
async def portfolio_page(
    request: Request,
    slug: str,
    user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    # Make slug lookup case-insensitive
    portfolio = db.query(Portfolio).filter(func.lower(Portfolio.slug) == slug.lower()).first()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")
        
    # Check if the user is authorized to view it
    is_owner = (user is not None) and (user.id == portfolio.user_id)
    if not portfolio.is_published and not is_owner:
        raise HTTPException(status_code=403, detail="This portfolio is not public.")

    owner = db.query(User).filter(User.id == portfolio.user_id).first()
    return templates.TemplateResponse("portfolio.html", {
        "request": request,
        "portfolio": portfolio,
        "owner": owner,
        "is_owner": is_owner,
    })

@app.get("/test_chat", response_class=HTMLResponse)
async def test_chat_page(request: Request):
    return templates.TemplateResponse("test_chat.html", {"request": request})


# ========================================================================
# Auth API routes
# ========================================================================

@app.post("/api/signup")
async def api_signup(payload: SignupRequest, db: Session = Depends(get_db)):
    if get_user_by_username(db, payload.username):
        raise HTTPException(status_code=400, detail="Username already taken")
    if get_user_by_email(db, payload.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    if len(payload.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    user = create_user(db, payload.username, payload.email, payload.password)
    token = create_access_token({"sub": user.username})
    resp = JSONResponse({"message": "Account created", "token": token})
    resp.set_cookie("access_token", token, httponly=False, samesite="lax", max_age=86400, path="/")
    return resp


@app.post("/api/login")
async def api_login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": user.username})
    resp = JSONResponse({"message": "Logged in", "token": token})
    resp.set_cookie("access_token", token, httponly=False, samesite="lax", max_age=86400, path="/")
    return resp

@app.post("/api/user/change-password")
async def api_change_password(
    payload: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect current password")
    user.hashed_password = hash_password(payload.new_password)
    db.commit()
    return {"message": "Password updated successfully"}


@app.post("/api/logout")
async def api_logout():
    resp = JSONResponse({"message": "Logged out"})
    resp.delete_cookie("access_token", path="/")
    return resp


# ========================================================================
# Portfolio API routes
# ========================================================================

@app.post("/api/upload")
async def upload_resume(
    file: UploadFile = File(..., description="PDF resume file"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    logger.info(f"Upload request received for user: {user.username}")
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    logger.info(f"File received: {file.filename}, content type: {file.content_type}")
    contents = await file.read()
    size_mb = len(contents) / (1024 * 1024)
    logger.info(f"File size: {size_mb:.2f} MB")
    if size_mb > MAX_PDF_SIZE_MB:
        raise HTTPException(status_code=400, detail=f"File exceeds {MAX_PDF_SIZE_MB}MB limit")

    api_key = user.openrouter_api_key or OPENROUTER_API_KEY
    if not api_key:
        raise HTTPException(status_code=400, detail="Please set your OpenRouter API key first")

    # Save file
    filename = f"{user.username}_{uuid.uuid4().hex[:8]}.pdf"
    filepath = os.path.join(UPLOAD_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(contents)

    try:
        logger.info(f"Processing resume for user: {user.username}")
        # Generate portfolio data via LLM
        data = await process_resume(filepath, api_key, username=user.username)
        logger.info(f"Resume processing successful for user: {user.username}")
        logger.info(f"Generated data keys: {list(data.keys())}")
    except Exception as e:
        logger.error("Resume processing failed for user %s: %s", user.username, str(e))
        logger.error("Full traceback:", exc_info=True)
        
        # Create fallback portfolio data
        logger.info("Creating fallback portfolio for user: %s", user.username)
        data = {
            "name": user.username.title(),
            "role": "Professional",
            "tagline": "Building the future with AI",
            "bio": "This portfolio was generated from your resume. Please update with your specific details.",
            "skills": ["Python", "JavaScript", "AI", "Web Development"],
            "projects": [],
            "experience": [],
            "education": [],
            "achievements": [],
            "contact": {},
            "_raw_text": "Fallback portfolio created due to processing error"
        }
        logger.info("Fallback portfolio created successfully")
    finally:
        # Clean up uploaded file
        if os.path.exists(filepath):
            os.remove(filepath)

    raw_text = data.pop("_raw_text", "")
    slug = user.username

    # Upsert portfolio
    portfolio = db.query(Portfolio).filter(Portfolio.user_id == user.id).first()
    if portfolio:
        portfolio.name = data.get("name", "")
        portfolio.role = data.get("role", "")
        portfolio.tagline = data.get("tagline", "")
        portfolio.bio = data.get("bio", "")
        portfolio.skills = data.get("skills", [])
        portfolio.projects = data.get("projects", [])
        portfolio.experience = data.get("experience", [])
        portfolio.education = data.get("education", [])
        portfolio.achievements = data.get("achievements", [])
        portfolio.contact = data.get("contact", {})
        portfolio.resume_text = raw_text
        portfolio.profile_image_url = data.get("profile_image_url")
    else:
        portfolio = Portfolio(
            user_id=user.id,
            name=data.get("name", ""),
            role=data.get("role", ""),
            tagline=data.get("tagline", ""),
            bio=data.get("bio", ""),
            skills=data.get("skills", []),
            projects=data.get("projects", []),
            experience=data.get("experience", []),
            education=data.get("education", []),
            achievements=data.get("achievements", []),
            contact=data.get("contact", {}),
            slug=slug,
            resume_text=raw_text,
            profile_image_url=data.get("profile_image_url"),
        )
        db.add(portfolio)

    db.commit()
    db.refresh(portfolio)

    # Index for RAG
    index_resume(slug, raw_text, data)

    return {"message": "Portfolio generated", "slug": slug, "url": f"/p/{slug}"}


@app.delete("/api/portfolio")
async def delete_portfolio(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    portfolio = db.query(Portfolio).filter(Portfolio.user_id == user.id).first()
    if not portfolio:
        raise HTTPException(status_code=404, detail="No portfolio found")
    delete_index(portfolio.slug)
    db.delete(portfolio)
    db.commit()
    return {"message": "Portfolio deleted"}


class PublishToggleRequest(BaseModel):
    is_published: bool


@app.put("/api/portfolio/publish")
async def toggle_portfolio_publish(
    payload: PublishToggleRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    portfolio = db.query(Portfolio).filter(Portfolio.user_id == user.id).first()
    if not portfolio:
        raise HTTPException(status_code=404, detail="No portfolio found")
    
    portfolio.is_published = payload.is_published
    db.commit()
    
    return {
        "message": "Portfolio visibility updated",
        "is_published": portfolio.is_published,
        "url": f"/p/{portfolio.slug}" if portfolio.is_published else None
    }



@app.put("/api/settings/apikey")
@app.post("/api/settings/apikey")  # Also support POST for compatibility
async def update_api_key(
    payload: ApiKeyUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user.openrouter_api_key = payload.openrouter_api_key
    db.commit()
    return {"message": "API key updated"}

# Alternative endpoint that matches frontend expectation
@app.post("/api/user/api-key")
async def update_api_key_alt(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    import json
    body = await request.body()
    data = json.loads(body)
    user.openrouter_api_key = data.get("api_key") or data.get("openrouter_api_key")
    db.commit()
    return {"message": "API key updated"}


# ========================================================================
# Chat API route
# ========================================================================

@app.post("/api/chat/{slug}")
@limiter.limit(CHAT_RATE_LIMIT)
async def chat_endpoint(
    request: Request,
    slug: str,
    payload: ChatRequest,
    db: Session = Depends(get_db),
):
    portfolio = db.query(Portfolio).filter(Portfolio.slug == slug).first()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    owner = db.query(User).filter(User.id == portfolio.user_id).first()
    api_key = (owner.openrouter_api_key if owner else None) or OPENROUTER_API_KEY
    if not api_key:
        raise HTTPException(status_code=400, detail="Portfolio owner has no API key configured")

    try:
        response_data = await rag_chat(
            slug=slug,
            user_message=payload.message,
            api_key=api_key,
            resume_text=portfolio.resume_text or "",
            portfolio_data={
                "name": portfolio.name,
                "role": portfolio.role,
                "bio": portfolio.bio,
                "skills": portfolio.skills,
                "projects": portfolio.projects,
                "experience": portfolio.experience,
                "education": portfolio.education,
                "achievements": portfolio.achievements,
                "contact": portfolio.contact,
            },
            conversation_history=payload.history,
        )
    except Exception as e:
        logger.error("Chat failed for slug=%s: %s", slug, e)
        raise HTTPException(status_code=500, detail="Chat service temporarily unavailable")

    return response_data


@app.get("/api/portfolio/{slug}/export/ppt")
async def export_portfolio_ppt(
    slug: str,
    db: Session = Depends(get_db)
):
    portfolio = db.query(Portfolio).filter(Portfolio.slug == slug).first()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")
        
    owner = db.query(User).filter(User.id == portfolio.user_id).first()
    
    try:
        ppt_path = generate_portfolio_ppt(portfolio, owner)
        if not ppt_path or not os.path.exists(ppt_path):
            raise HTTPException(status_code=500, detail="Failed to generate PPT")
            
        return FileResponse(
            path=ppt_path,
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            headers={"Content-Disposition": f'attachment; filename="{owner.username}_portfolio.pptx"'}
        )
    except Exception as e:
        logger.error("Error generating PPT for slug=%s: %s", slug, e)
        raise HTTPException(status_code=500, detail="Internal error generating presentation")

@app.get("/api/portfolio/{slug}/export/docx")
async def export_portfolio_docx(
    slug: str,
    db: Session = Depends(get_db)
):
    portfolio = db.query(Portfolio).filter(Portfolio.slug == slug).first()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")
        
    owner = db.query(User).filter(User.id == portfolio.user_id).first()
    api_key = owner.openrouter_api_key or OPENROUTER_API_KEY
    if not api_key:
        raise HTTPException(status_code=400, detail="Please set your OpenRouter API key to generate ATS resume")
        
    if not portfolio.resume_text:
        raise HTTPException(status_code=400, detail="No resume text found. Please re-upload your resume.")
        
    try:
        from generator import generate_ats_resume_data
        from exporter import generate_ats_resume_docx_from_data
        
        ats_data = await generate_ats_resume_data(portfolio.resume_text, api_key)
        docx_path = generate_ats_resume_docx_from_data(ats_data, slug)
        
        if not docx_path or not os.path.exists(docx_path):
            raise HTTPException(status_code=500, detail="Failed to generate DOCX")
            
        return FileResponse(
            path=docx_path,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{slug}_ATS_Resume.docx"'}
        )
    except Exception as e:
        logger.error("Error generating DOCX for slug=%s: %s", slug, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal error generating ATS resume. Please try again.")

@app.get("/api/portfolio/{slug}/jobs")
@limiter.limit("10/minute")
async def fetch_job_recommendations(
    request: Request,
    slug: str,
    location: Optional[str] = None,
    level: Optional[str] = None,
    remote: Optional[bool] = None,
    salary_min: Optional[int] = None,
    what: Optional[str] = None,
    db: Session = Depends(get_db)
):
    portfolio = db.query(Portfolio).filter(Portfolio.slug == slug).first()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")
        
    owner = db.query(User).filter(User.id == portfolio.user_id).first()
    api_key = (owner.openrouter_api_key if owner else None) or OPENROUTER_API_KEY
    if not api_key:
        raise HTTPException(status_code=400, detail="Portfolio owner has no API key configured")
        
    filters = JobFilter(
        location=location,
        level=level,
        remote=remote,
        salary_min=salary_min,
        what=what
    )
    
    try:
        jobs = await get_recommended_jobs(portfolio, api_key, filters)
        return {"jobs": jobs}
    except Exception as e:
        logger.error("Job recommendations failed for slug=%s: %s", slug, e)
        raise HTTPException(status_code=500, detail="Job fetching service temporarily unavailable")
