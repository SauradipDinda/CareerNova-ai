"""SQLAlchemy ORM models for Users and Portfolios."""

import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey, JSON, Boolean
)
from sqlalchemy.orm import relationship

from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(120), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    openrouter_api_key = Column(String(512), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    portfolios = relationship("Portfolio", back_populates="owner", cascade="all, delete-orphan")


class Portfolio(Base):
    __tablename__ = "portfolios"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(120), nullable=True)
    role = Column(String(120), nullable=True)
    tagline = Column(String(255), nullable=True)
    bio = Column(Text, nullable=True)
    skills = Column(JSON, nullable=True)
    projects = Column(JSON, nullable=True)
    experience = Column(JSON, nullable=True)
    education = Column(JSON, nullable=True)
    achievements = Column(JSON, nullable=True)
    contact = Column(JSON, nullable=True)
    slug = Column(String(60), unique=True, nullable=False, index=True)
    is_published = Column(Boolean, default=False, nullable=False)
    resume_text = Column(Text, nullable=True)
    profile_image_url = Column(String(512), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    owner = relationship("User", back_populates="portfolios")
