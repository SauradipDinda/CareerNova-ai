"""RAG engine for CareerNova-AI — answers chat queries using resume context."""

import asyncio
import logging
from typing import Any, Dict, List, Optional

import httpx

from config import (
    OPENROUTER_BASE_URL,
    DEFAULT_LLM_MODEL,
    LLM_TEMPERATURE,
    LLM_MAX_TOKENS,
    GEMINI_API_KEY,
)

logger = logging.getLogger(__name__)


async def _call_gemini(prompt: str) -> str:
    """Helper to call Gemini API"""
    gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"

    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            gemini_url,
            headers={"Content-Type": "application/json"},
            json=payload,
        )
        resp.raise_for_status()
    return resp.json()["candidates"][0]["content"]["parts"][0]["text"]


async def detect_intent(user_message: str) -> str:
    """Classify the user intent into RAG, INTERVIEW, or ATS mode."""
    
    prompt = f"""
    You are an intent classification engine for an AI Career Assistant.
    Analyze the following user message and classify it into exactly one of three categories:
    
    1. "INTERVIEW": The user is asking for interview questions, preparation, or what can be asked from their profile.
       (e.g., "Suggest interview questions", "Important questions for my resume")
       
    2. "ATS": The user is asking to evaluate, score, or check their resume/ATS score.
       (e.g., "Check my ATS score", "Analyze my resume", "Is my resume good?")
       
    3. "RAG": Any other question about the candidate's background, skills, or general chat.
       (e.g., "What are their skills?", "Tell me about them", "Hello")
       
    Reply ONLY with the exact word: INTERVIEW, ATS, or RAG. Do not include any other text.
    
    User message: "{user_message}"
    """
    try:
        response = await _call_gemini(prompt)
        intent = response.strip().upper()
        if intent in ["INTERVIEW", "ATS", "RAG"]:
             return intent
    except Exception as e:
        logger.error("Intent detection failed, falling back to RAG. Error: %s", e)
        
    return "RAG"


async def generate_interview_questions(context: str, user_message: str) -> str:
    """Generate tailored interview questions based on the candidate's resume context."""
    
    prompt = f"""
    You are a Senior Technical Interviewer and AI Career Coach. 
    Based on the following candidate's resume information, generate a customized technical interview.
    
    Requirements:
    1. Generate exactly 5 Technical Questions strictly related to their listed skills.
    2. Generate exactly 2 Project-Specific Questions referencing actual concepts or technologies from their projects.
    3. Generate exactly 2 Scenario-Based Questions relevant to their role and tech stack.
    4. Generate exactly 1 Behavioral Question appropriate for their apparent experience level.
    
    Rules:
    - NO generic textbook questions. Make them practical and challenging.
    - If they list AI/ML, ask about model evaluation, deployment, or data preprocessing.
    - If they list Backend (e.g. FastAPI/Node), ask about API design, scalability, or async.
    - Format output nicely with Markdown: group them under bolded category headers (e.g. **Technical Questions**).
    - Use bullet points.
    - End with a prompt offering to evaluate their answers (e.g., "Would you like me to evaluate your answers to any of these?").
    
    Candidate Info Context:
    {context}
    
    User ask: "{user_message}"
    """
    
    try:
        return await _call_gemini(prompt)
    except Exception as e:
        logger.error("Interview generation failed. Error: %s", e)
        return "Sorry, I couldn't generate interview questions at this time. Please try again."


async def generate_ats_analysis(context: str, user_message: str) -> str:
    """Evaluate candidate's resume context and return an ATS score with suggestions."""
    
    prompt = f"""
    You are an Expert ATS (Applicant Tracking System) Analyzer and Technical Recruiter.
    Evaluate the following candidate's resume context.
    
    Evaluate based on:
    - Keyword relevance and skill density
    - Technical clarity and role alignment
    - Quantified achievements and action verbs
    - Section completeness and project impact
    
    Output Format (Markdown strict):
    - **Overall ATS Score**: [0-100]/100
    - **Category Breakdown**: (Scores for Skills, Experience, Impact, Clarity out of 10)
    - **Strengths**: 2-3 bullet points of what looks great.
    - **Weaknesses/Missing Elements**: 2-3 bullet points.
    
    CRITICAL INSTRUCTION - IF SCORE IS UNDER 85:
    You MUST provide an "**Improvement Suggestions**" section.
    - Identify weak bullet points (e.g. "Developed AI model").
    - Provide a rewritten example emphasizing quantifiable impact (e.g. "Developed & deployed ML model improving accuracy by 23%...").
    - Suggest missing keywords or formatting structural improvements.
    
    Be realistic but constructive. Don't give an automatic 100%. 
    
    Candidate Info Context:
    {context}
    
    User ask: "{user_message}"
    """
    
    try:
        return await _call_gemini(prompt)
    except Exception as e:
        logger.error("ATS analysis failed. Error: %s", e)
        return "Sorry, I couldn't run the ATS analysis at this time. Please try again."


async def chat(
    slug: str,
    user_message: str,
    api_key: str,
    resume_text: str,
    portfolio_data: Dict[str, Any],
    conversation_history: Optional[List[Dict]] = None,
) -> Dict[str, str]:
    """Answer a question about a portfolio using context provided from the database."""
    
    # Build a rich context from the structured portfolio data
    context_parts = []
    if portfolio_data.get("name"):
        context_parts.append(f"Name: {portfolio_data['name']}")
    if portfolio_data.get("role"):
        context_parts.append(f"Role: {portfolio_data['role']}")
    if portfolio_data.get("bio"):
        context_parts.append(f"Bio: {portfolio_data['bio']}")
    
    # Skills - handle None and non-list
    skills = portfolio_data.get("skills")
    if skills and isinstance(skills, list):
        context_parts.append(f"Skills: {', '.join(skills)}")
    
    # Experience - handle None and non-list
    experience = portfolio_data.get("experience")
    if experience and isinstance(experience, list):
        exp_lines = []
        for e in experience:
            if isinstance(e, dict):
                exp_lines.append(
                    f"  - {e.get('role', '')} at {e.get('company', '')} ({e.get('duration', '')}): {e.get('description', '')}"
                )
        if exp_lines:
            context_parts.append("Experience:\n" + "\n".join(exp_lines))
        
    # Projects - handle None and non-list
    projects = portfolio_data.get("projects")
    if projects and isinstance(projects, list):
        proj_lines = []
        for p in projects:
            if isinstance(p, dict):
                techs = ", ".join(p.get("technologies", [])) if isinstance(p.get("technologies"), list) else ""
                proj_lines.append(
                    f"  - {p.get('title', '')}: {p.get('description', '')} [Technologies: {techs}]"
                )
        if proj_lines:
            context_parts.append("Projects:\n" + "\n".join(proj_lines))
        
    # Education - handle None and non-list
    education = portfolio_data.get("education")
    if education and isinstance(education, list):
        edu_lines = []
        for ed in education:
            if isinstance(ed, dict):
                edu_lines.append(
                    f"  - {ed.get('degree', '')} from {ed.get('institution', '')} ({ed.get('year', '')})"
                )
        if edu_lines:
            context_parts.append("Education:\n" + "\n".join(edu_lines))
        
    # Achievements - handle None and non-list
    achievements = portfolio_data.get("achievements")
    if achievements and isinstance(achievements, list):
        context_parts.append("Achievements:\n" + "\n".join(f"  - {a}" for a in achievements if a))
        
    # Contact - handle None and non-dict
    contact = portfolio_data.get("contact")
    if contact and isinstance(contact, dict):
        contact_str = ", ".join(f"{k}: {v}" for k, v in contact.items() if v)
        if contact_str:
            context_parts.append(f"Contact Info: {contact_str}")

    # Final context fallback to raw text if structured data is sparse
    if len(context_parts) < 3:
        context = (resume_text or "")[:4000]
    else:
        context = "\n\n".join(context_parts)

    # Detect Intent
    mode = await detect_intent(user_message)
    logger.info("Detected intent for slug '%s': %s", slug, mode)
    
    if mode == "INTERVIEW":
        answer = await generate_interview_questions(context, user_message)
        return {"answer": answer, "mode": mode}
        
    elif mode == "ATS":
        answer = await generate_ats_analysis(context, user_message)
        return {"answer": answer, "mode": mode}
        
    # Default to RAG mode
    system_prompt = (
        "You are an AI assistant representing a professional's portfolio. "
        "Answer questions about the candidate based on their resume information provided below. "
        "Be concise, professional, and helpful. If information is not available, say so politely.\n\n"
        f"=== CANDIDATE PORTFOLIO INFO ===\n{context}\n=== END INFO ==="
    )

    consolidated_prompt = (
        f"{system_prompt}\n\n"
        "--- Conversation History ---\n"
    )
    
    if conversation_history:
        for turn in conversation_history[-6:]:
            role = turn.get("role", "user")
            content = turn.get("content", "")
            if content:
                consolidated_prompt += f"{role.upper()}: {content}\n"
    
    consolidated_prompt += f"\nUSER: {user_message}\nASSISTANT:"

    try:
        answer = await _call_gemini(consolidated_prompt)
        logger.info("Chat response for slug '%s': %d chars", slug, len(answer))
        return {"answer": answer, "mode": mode}
    except Exception as e:
        logger.error("Chat LLM call failed for slug '%s': %s", slug, e)
        return {
            "answer": "I'm sorry, I'm having trouble connecting to my brain right now. Please try again in a few seconds.",
            "mode": mode
        }

# Kept for compatibility but now no-ops as we are stateless
def index_resume(slug: str, raw_text: str, data: Dict[str, Any]) -> bool:
    return True

def delete_index(slug: str) -> bool:
    return True
