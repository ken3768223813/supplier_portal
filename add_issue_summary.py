"""
给 trouble_reports 表添加 issue_summary 字段（存 AI 提取的简洁问题）
运行：python add_issue_summary.py
"""
import sqlite3

DB = r"D:\supplier_portal_data\db\app.sqlite3"

conn = sqlite3.connect(DB)
c = conn.cursor()
cols = {r[1] for r in c.execute("PRAGMA table_info(trouble_reports)").fetchall()}

if "issue_summary" in cols:
    print("  OK issue_summary already exists")
else:
    c.execute("ALTER TABLE trouble_reports ADD COLUMN issue_summary TEXT")
    print("  Added issue_summary")

conn.commit()
conn.close()
print("Done!")