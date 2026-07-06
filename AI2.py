import sqlite3
conn = sqlite3.connect("instance/supplier_portal.db")
c = conn.cursor()

# 看一下这个 TR 的附件情况
c.execute("""
    SELECT d.id, d.original_name, d.doc_type 
    FROM tr_document d 
    JOIN trouble_report t ON d.tr_id = t.id 
    WHERE t.tr_no = 'TR-EDC-201631774'
""")
for row in c.fetchall():
    print(row)

conn.close()