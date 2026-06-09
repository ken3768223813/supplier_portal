import sqlite3

conn = sqlite3.connect(r"D:\supplier_portal_data\db\app.sqlite3")
cursor = conn.cursor()

# 添加字段
cursor.execute("""
ALTER TABLE trouble_reports
ADD COLUMN case_no VARCHAR(32)
""")

# 添加索引
cursor.execute("""
CREATE INDEX ix_trouble_reports_case_no
ON trouble_reports(case_no)
""")

conn.commit()
conn.close()

print("Done")