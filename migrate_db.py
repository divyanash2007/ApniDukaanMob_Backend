import asyncio
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:2007@localhost:5432/apnidukaan")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

def migrate():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        # Check if column exists
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='users' AND column_name='has_lifetime_subscription';
        """)
        
        if not cur.fetchone():
            print("Adding has_lifetime_subscription column to users table...")
            cur.execute("ALTER TABLE users ADD COLUMN has_lifetime_subscription BOOLEAN DEFAULT FALSE;")
            conn.commit()
            print("Migration successful.")
        else:
            print("Column already exists.")
            
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error during migration: {e}")

if __name__ == "__main__":
    migrate()
