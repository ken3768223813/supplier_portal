import sqlite3

db_path = r"D:\supplier_portal_data\db\app.sqlite3"
conn = sqlite3.connect(db_path)
cur = conn.cursor()

cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
print("Tables:", cur.fetchall())
