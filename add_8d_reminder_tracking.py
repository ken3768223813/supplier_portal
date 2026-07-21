import sqlite3

from app.config import Config


def add_column(conn, table, column, ddl):
    columns = {
        row[1]
        for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
    }
    if column in columns:
        print(f"{table}.{column} already exists.")
        return
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
    print(f"Added {table}.{column}.")


def main():
    conn = sqlite3.connect(Config.DB_PATH)
    try:
        add_column(conn, "suppliers", "reminder_cc_emails", "TEXT")
        add_column(conn, "trouble_reports", "eight_d_reminder_count", "INTEGER NOT NULL DEFAULT 0")
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
