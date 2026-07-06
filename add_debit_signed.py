import sqlite3

from app.config import Config


def main():
    db_path = Config.DB_PATH
    conn = sqlite3.connect(db_path)
    try:
        columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(trouble_reports)").fetchall()
        }
        if "debit_signed" in columns:
            print("debit_signed already exists.")
            return

        conn.execute(
            "ALTER TABLE trouble_reports "
            "ADD COLUMN debit_signed BOOLEAN NOT NULL DEFAULT 0"
        )
        conn.commit()
        print("Added trouble_reports.debit_signed.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
