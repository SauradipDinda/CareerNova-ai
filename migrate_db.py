import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), "portfoliai.db")
print(f"Connecting to {db_path}")
conn = sqlite3.connect(db_path)
try:
    conn.execute("ALTER TABLE portfolios ADD COLUMN profile_image_url VARCHAR(512)")
    print("Column added successfully!")
except sqlite3.OperationalError as e:
    print(f"Skipped adding column: {e}")
conn.commit()
conn.close()
