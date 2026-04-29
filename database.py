import sqlite3

def get_db():
    conn = sqlite3.connect("words.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS words (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            japanese TEXT NOT NULL,
            english TEXT NOT NULL
        )
    """)
    # 初期データ投入（すでにあれば入れない）
    if conn.execute("SELECT COUNT(*) FROM words").fetchone()[0] == 0:
        words = [
            ("こんにちは", "hello"),
            ("りんご", "apple"),
            ("ねこ", "cat"),
            ("いぬ", "dog"),
            ("ありがとう", "thanks"),
        ]
        conn.executemany("INSERT INTO words (japanese, english) VALUES (?, ?)", words)
    conn.commit()
    conn.close()