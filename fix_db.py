from app import create_app, db

app = create_app()
with app.app_context():
    with db.engine.connect() as conn:
        conn.execute(db.text('PRAGMA foreign_keys=OFF'))
        conn.execute(db.text('''
            CREATE TABLE control_plans_new (
                id INTEGER PRIMARY KEY,
                supplier_id INTEGER NOT NULL,
                part_id INTEGER NOT NULL,
                cp_no VARCHAR(50) NOT NULL UNIQUE,
                revision VARCHAR(20) DEFAULT 'A0',
                status VARCHAR(20) DEFAULT 'active',
                process_type VARCHAR(50),
                audit_date DATE,
                auditor VARCHAR(100),
                notes TEXT,
                created_at DATETIME NOT NULL,
                updated_at DATETIME,
                UNIQUE (supplier_id, part_id, process_type)
            )
        '''))
        conn.execute(db.text('INSERT INTO control_plans_new SELECT * FROM control_plans'))
        conn.execute(db.text('DROP TABLE control_plans'))
        conn.execute(db.text('ALTER TABLE control_plans_new RENAME TO control_plans'))
        conn.execute(db.text('PRAGMA foreign_keys=ON'))
        conn.commit()
    print('done')