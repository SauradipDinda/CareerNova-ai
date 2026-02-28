"""Script to migrate DB and add the is_published column."""
import os
from sqlalchemy import create_engine, text
from config import DATABASE_URL

print(f"Migrating database: {DATABASE_URL}")
engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    try:
        # Check if we are on SQLite or PostgreSQL
        if "sqlite" in DATABASE_URL:
            conn.execute(text("ALTER TABLE portfolios ADD COLUMN is_published BOOLEAN DEFAULT 0 NOT NULL;"))
        else:
            conn.execute(text("ALTER TABLE portfolios ADD COLUMN is_published BOOLEAN DEFAULT FALSE NOT NULL;"))
        conn.commit()
        print("Migration successful! Column 'is_published' added.")
    except Exception as e:
        print(f"Migration failed or column already exists: {e}")
