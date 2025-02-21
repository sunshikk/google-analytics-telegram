import sqlite3

conn = sqlite3.connect('/data/database.db')
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    website INT,
    site TEXT,
    subscribe INT
)
""")

conn.commit()
