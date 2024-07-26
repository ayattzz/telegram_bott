import sqlite3

conn = sqlite3.connect('users.db')
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE,
                trial_end TEXT,
                subscribed BOOLEAN,
                subscription_start TEXT)''')
conn.commit()
conn.close()
