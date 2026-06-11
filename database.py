import sqlite3
import os
import json

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "autotrader.db")

def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def setup_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Create table for seen adverts
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS seen_adverts (
            advert_id TEXT PRIMARY KEY,
            seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create table for saved searches
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS searches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id INTEGER NOT NULL,
            filters TEXT NOT NULL,
            write_off TEXT DEFAULT 'Exclude'
        )
    ''')
    
    conn.commit()
    conn.close()

def is_advert_seen(advert_id: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM seen_adverts WHERE advert_id = ?', (advert_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def mark_advert_seen(advert_id: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO seen_adverts (advert_id) VALUES (?)', (advert_id,))
    conn.commit()
    conn.close()

def add_search(channel_id: int, filters: dict, write_off: str = "Exclude") -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO searches (channel_id, filters, write_off) VALUES (?, ?, ?)', (channel_id, json.dumps(filters), write_off))
    search_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return search_id

def get_all_searches() -> list:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM searches')
    rows = cursor.fetchall()
    conn.close()
    
    results = []
    for row in rows:
        results.append({
            "id": row["id"],
            "channel_id": row["channel_id"],
            "filters": json.loads(row["filters"]),
            "write_off": row["write_off"]
        })
    return results

def get_searches_for_channel(channel_id: int) -> list:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM searches WHERE channel_id = ?', (channel_id,))
    rows = cursor.fetchall()
    conn.close()
    
    results = []
    for row in rows:
        results.append({
            "id": row["id"],
            "channel_id": row["channel_id"],
            "filters": json.loads(row["filters"]),
            "write_off": row["write_off"]
        })
    return results

def remove_search(search_id: int, channel_id: int) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM searches WHERE id = ? AND channel_id = ?', (search_id, channel_id))
    rows_affected = cursor.rowcount
    conn.commit()
    conn.close()
    return rows_affected > 0
