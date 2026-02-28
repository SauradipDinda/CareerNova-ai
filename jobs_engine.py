"""Functions for fetching jobs from Adzuna API and matching them using LLM."""

import json
import logging
import urllib.parse
from typing import Any, Dict, List, Optional
import asyncio

import httpx
from pydantic import BaseModel
from cachetools import TTLCache
from fastapi import HTTPException

from config import ADZUNA_APP_ID, ADZUNA_APP_KEY, OPENROUTER_API_KEY, OPENROUTER_BASE_URL, DEFAULT_LLM_MODEL
from models import Portfolio

logger = logging.getLogger(__name__)

# Cache job search results for 10 minutes (TTL=600s), max 100 entries.
# Format: { "{slug}_{filters_hash}": [...jobs...] }
jobs_cache = TTLCache(maxsize=100, ttl=600)

class JobFilter(BaseModel):
    location: Optional[str] = None
    level: Optional[str] = None      # "entry_level", "mid_level", "senior"
    remote: Optional[bool] = None
    salary_min: Optional[int] = None
    what: Optional[str] = None       # Tech stack search


async def _fetch_adzuna_jobs(skills: List[str], filters: JobFilter, user_country: str = "us") -> List[Dict[str, Any]]:
    """Fetch raw job listings from the Adzuna API based on skills and filters."""
    
    if not ADZUNA_APP_ID or not ADZUNA_APP_KEY:
        logger.error("Adzuna API credentials not configured in environment.")
        raise ValueError("Job search integration is not configured (missing Adzuna keys).")

    # Combine top 3 skills into the "what" parameter, or use from filters
    search_query = filters.what
    if not search_query and skills:
        search_query = " ".join(skills[:3])
    if not search_query:
        search_query = "software engineer" # Fallback
        
    encoded_query = urllib.parse.quote_plus(search_query)
    
    # 50 results max to give the LLM more options to filter from
    url = f"https://api.adzuna.com/v1/api/jobs/{user_country}/search/1?app_id={ADZUNA_APP_ID}&app_key={ADZUNA_APP_KEY}&results_per_page=50&what={encoded_query}"
    
    if filters.location:
        url += f"&where={urllib.parse.quote_plus(filters.location)}"
    if filters.salary_min:
        url += f"&salary_min={filters.salary_min}"
        
    # Attempting to fetch matching jobs
    async with httpx.AsyncClient(timeout=10.0) as client:
        logger.info(f"Fetching jobs from Adzuna: {url.replace(ADZUNA_APP_KEY, 'HIDDEN')}")
        resp = await client.get(url)
        
        if resp.status_code != 200:
            logger.error(f"Adzuna API Error: {resp.status_code} - {resp.text}")
            return []
            
        data = resp.json()
        raw_results = data.get("results", [])
        
    parsed_jobs = []
    for job in raw_results:
        # Check basic remote filter first if requested
        title_desc = f"{job.get('title', '')} {job.get('description', '')}".lower()
        if filters.remote and "remote" not in title_desc and "work from home" not in title_desc:
            continue
            
        parsed_jobs.append({
            "id": job.get("id"),
            "title": job.get("title"),
            "company": job.get("company", {}).get("display_name", "Unknown"),
            "location": job.get("location", {}).get("display_name", "Unknown"),
            "salary_min": job.get("salary_min"),
            "salary_max": job.get("salary_max"),
            "description": job.get("description", ""),
            "url": job.get("redirect_url")
        })
        
    return parsed_jobs


async def _score_and_filter_jobs(jobs: List[Dict[str, Any]], portfolio: Portfolio, api_key: str) -> List[Dict[str, Any]]:
    """Use an LLM to evaluate the relevance of each job against the user portfolio."""
    if not jobs:
        return []

    # Prepare user summary
    user_summary = f"""
    Role: {portfolio.role}
    Experience: {json.dumps(portfolio.experience)}
    Skills: {', '.join(portfolio.skills or [])}
    Bio: {portfolio.bio}
    """
    
    # Prepare prompt for batch scoring to save tokens/time. 
    # We will score up to 15 jobs at a time.
    jobs_to_score = jobs[:15]
    
    jobs_json_str = json.dumps([
        {
            "index": i, 
            "title": j["title"], 
            "company": j["company"], 
            "description": j["description"][:200] + "..." # Truncate description to save tokens
        } for i, j in enumerate(jobs_to_score)
    ])

    prompt = f"""
    You are an expert technical recruiter matching candidates to jobs.
    
    Evaluate these job descriptions against the candidate profile. For each job, provide a relevance score (0-100) and a short 1-sentence explanation of why it matches (or why it doesn't).
    
    Candidate Profile:
    {user_summary}
    
    Jobs to Evaluate:
    {jobs_json_str}
    
    Reply ONLY with a valid JSON array of objects with keys: "index" (integer), "score" (integer 0-100), "reason" (string).
    Keep the explanation "reason" concise, starting like "This role fits your background in..."
    """
    
    headers = {
         "Authorization": f"Bearer {api_key or OPENROUTER_API_KEY}",
         "Content-Type": "application/json",
         "HTTP-Referer": "https://portfoli-ai.app",
         "X-Title": "CareerNova-AI",
    }
    
    payload = {
        "model": DEFAULT_LLM_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2, # Low temperature for more deterministic scoring
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{OPENROUTER_BASE_URL}/chat/completions",
                headers=headers,
                json=payload
            )
            
            if resp.status_code == 200:
                content = resp.json()["choices"][0]["message"]["content"]
                
                # Cleanup markdown and parse
                content = content.replace("```json", "").replace("```", "").strip()
                scores = json.loads(content)
                
                # Merge scores back to jobs
                scored_jobs = []
                for s in scores:
                    idx = s.get("index")
                    if idx is not None and 0 <= idx < len(jobs_to_score):
                        job = jobs_to_score[idx].copy()
                        job["match_score"] = s.get("score", 0)
                        job["match_reason"] = s.get("reason", "Good match for your profile.")
                        
                        # Only include jobs with > 40% match
                        if job["match_score"] >= 40:
                            scored_jobs.append(job)
                            
                # Sort by score descending
                scored_jobs.sort(key=lambda x: x["match_score"], reverse=True)
                return scored_jobs
            else:
                logger.error(f"LLM Scoring Failed: {resp.text}")
                
    except Exception as e:
         logger.error(f"Failed to score jobs with LLM: {e}")
         
    # Fallback: if LLM scoring fails, just return the first few jobs with a dummy score
    fallback_jobs = []
    for i, j in enumerate(jobs[:10]):
        j["match_score"] = 80 - (i * 2) # decreasing dummy score
        j["match_reason"] = "Based on keyword matching with your resume skills."
        fallback_jobs.append(j)
    return fallback_jobs
    
    
async def get_recommended_jobs(portfolio: Portfolio, api_key: str, filters: JobFilter) -> List[Dict[str, Any]]:
    """Main entrypoint to get AI job recommendations with caching."""
    
    filters_hash = f"{filters.location}-{filters.level}-{filters.remote}-{filters.salary_min}-{filters.what}"
    cache_key = f"{portfolio.slug}_{filters_hash}"
    
    if cache_key in jobs_cache:
        logger.info(f"Returning cached jobs for {cache_key}")
        return jobs_cache[cache_key]
        
    # 1. Determine user country heuristic (default 'us')
    # Can expand this by checking portfolio.contact or location if available
    country = "us"
    if portfolio.contact and isinstance(portfolio.contact, dict):
         phone = portfolio.contact.get("phone", "")
         if phone.startswith("+44"): country = "gb"
         elif phone.startswith("+91"): country = "in"
         
    # 2. Fetch from Adzuna
    raw_jobs = await _fetch_adzuna_jobs(portfolio.skills or [], filters, user_country=country)
    
    # 3. AI Score
    scored_jobs = await _score_and_filter_jobs(raw_jobs, portfolio, api_key)
    
    # 4. Cache and return
    jobs_cache[cache_key] = scored_jobs
    return scored_jobs
