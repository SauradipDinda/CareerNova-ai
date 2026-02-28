import psycopg2
import sys

def test_conn():
    # Attempt 1: Direct hostname without .c-4 but with endpoint option
    dsn1 = "postgresql://neondb_owner:npg_SqO8VZT1aeCm@ep-hidden-mode-ai8yf9cy-pooler.us-east-1.aws.neon.tech/genaidb?sslmode=require&options=endpoint%3Dep-hidden-mode-ai8yf9cy-pooler"
    
    # Attempt 2: Using IP directly with endpoint option
    dsn2 = "postgresql://neondb_owner:npg_SqO8VZT1aeCm@54.86.249.90/genaidb?sslmode=require&options=endpoint%3Dep-hidden-mode-ai8yf9cy-pooler"

    for idx, dsn in enumerate([dsn1, dsn2]):
        print(f"Testing DSN {idx+1}...")
        try:
            conn = psycopg2.connect(dsn)
            print(f"DSN {idx+1} SUCCESS!")
            conn.close()
            sys.exit(0)
        except Exception as e:
            print(f"DSN {idx+1} FAILED: {str(e).strip()}")

if __name__ == "__main__":
    test_conn()
