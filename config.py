"""Application configuration loaded from environment variables."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

# --- Security ---
SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me-in-production")
ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

# --- Database ---
DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'portfoliai.db'}")

# --- OpenRouter ---
OPENROUTER_BASE_URL: str = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
DEFAULT_LLM_MODEL: str = os.getenv("DEFAULT_LLM_MODEL", "google/gemma-3-12b-it:free")
LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.3"))
LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "8192"))

# --- Gemini ---
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

# --- Adzuna ---
ADZUNA_APP_ID: str = os.getenv("ADZUNA_APP_ID", "")
ADZUNA_APP_KEY: str = os.getenv("ADZUNA_APP_KEY", "")

# --- ChromaDB ---
CHROMA_PERSIST_DIR: str = str(BASE_DIR / "chroma_store")

# --- Uploads ---
UPLOAD_DIR: str = str(BASE_DIR / "uploads")
MAX_PDF_SIZE_MB: int = int(os.getenv("MAX_PDF_SIZE_MB", "10"))

# --- Rate Limiting ---
CHAT_RATE_LIMIT: str = os.getenv("CHAT_RATE_LIMIT", "20/minute")
