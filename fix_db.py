import sqlite3

conn = sqlite3.connect(r"D:\supplier_portal_data\db\app.sqlite3")
cursor = conn.cursor()

cursor.execute("PRAGMA table_info(trouble_reports)")

for row in cursor.fetchall():
    print(row)

conn.close()