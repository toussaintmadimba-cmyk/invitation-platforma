import sqlite3

DB_PATH = "app.db"  # ⚠️ adapte selon ton config.py si nécessaire

def col_exists(cur, table, col):
    cur.execute(f"PRAGMA table_info({table})")
    return any(r[1] == col for r in cur.fetchall())

con = sqlite3.connect(DB_PATH)
cur = con.cursor()

# guest: civility, partner_name
if not col_exists(cur, "guest", "civility"):
    cur.execute("ALTER TABLE guest ADD COLUMN civility TEXT NOT NULL DEFAULT 'MME'")
if not col_exists(cur, "guest", "partner_name"):
    cur.execute("ALTER TABLE guest ADD COLUMN partner_name TEXT")

# rsvp table
cur.execute("""
CREATE TABLE IF NOT EXISTS rsvp (
    id INTEGER PRIMARY KEY,
    invitation_id INTEGER NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'pending',
    message TEXT,
    responded_at DATETIME,
    created_at DATETIME,
    FOREIGN KEY(invitation_id) REFERENCES invitation(id)
)
""")

con.commit()
con.close()
print("✅ Migration OK")
