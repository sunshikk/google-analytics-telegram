import sqlite3

DATABASE_NAME = 'database.db'

conn = sqlite3.connect(f'data/{DATABASE_NAME}')
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