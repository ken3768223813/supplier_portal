import sqlite3

from app.config import Config


def main():
    conn = sqlite3.connect(Config.DB_PATH)
    try:
        columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(suppliers)").fetchall()
        }
        if "reminder_emails" in columns:
            print("suppliers.reminder_emails already exists.")
            return

        conn.execute("ALTER TABLE suppliers ADD COLUMN reminder_emails TEXT")
        conn.commit()
        print("Added suppliers.reminder_emails.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
