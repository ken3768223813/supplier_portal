import sqlite3

DB = r"D:\supplier_portal_data\db\app.sqlite3"

conn = sqlite3.connect(DB)
c = conn.cursor()
cols = {r[1] for r in c.execute("PRAGMA table_info(trouble_reports)").fetchall()}

for col in ["eight_d_root_cause TEXT", "eight_d_action TEXT"]:
    name = col.split()[0]
    if name in cols:
        print(f"  OK {name} already exists")
    else:
        c.execute(f"ALTER TABLE trouble_reports ADD COLUMN {col}")
        print(f"  Added {name}")

conn.commit()
conn.close()
print("Done!")