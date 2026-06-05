import sqlite3
conn = sqlite3.connect(r"D:\supplier_portal_data\db\app.sqlite3")
c = conn.cursor()
cols = {r[1] for r in c.execute("PRAGMA table_info(trouble_reports)").fetchall()}
for col in ["debit_ref VARCHAR(100)", "debit_amount FLOAT", "debit_currency VARCHAR(10)", "debit_date VARCHAR(20)"]:
    name = col.split()[0]
    if name in cols:
        print(f"  OK {name} exists")
    else:
        c.execute(f"ALTER TABLE trouble_reports ADD COLUMN {col}")
        print(f"  Added {name}")
conn.commit()
conn.close()
print("Done!")