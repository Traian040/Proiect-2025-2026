import sqlite3
import re
from pathlib import Path

class DatabaseHandler:
    def __init__(self, db_name="search_engine.db"):
        self.db_name = db_name
        self.conn = sqlite3.connect(self.db_name, check_same_thread=False)
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.execute("PRAGMA synchronous = NORMAL")
        self.conn.execute("PRAGMA cache_size = -10000")

    def init_db(self, fresh_start=False):
        cursor = self.conn.cursor()
        if fresh_start:
            cursor.execute('DROP TABLE IF EXISTS documents')
            cursor.execute('DROP TABLE IF EXISTS documents_fts')

        # updated table structure. added extension column and file_size column
        cursor.execute('''
                       CREATE TABLE IF NOT EXISTS documents
                       (
                           id INTEGER PRIMARY KEY AUTOINCREMENT,
                           file_path TEXT UNIQUE,
                           file_name TEXT,
                           content TEXT,
                           preview TEXT,
                           meta_json TEXT,
                           last_modified REAL,
                           extension TEXT,
                           file_size INTEGER
                       )
                       ''')
        cursor.execute('''
            CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts 
            USING fts5(content, content='documents', content_rowid='id')
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_file_path ON documents (file_path)')
        self.conn.commit()

    def get_stored_mtime(self, file_path):
        cursor = self.conn.cursor()
        cursor.execute('SELECT last_modified FROM documents WHERE file_path = ?', (file_path,))
        result = cursor.fetchone()
        return result[0] if result else None

    def get_all_extensions(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT DISTINCT extension FROM documents WHERE extension != "" ORDER BY extension ASC')
        return [r[0] for r in cursor.fetchall()]

    def upsert_document(self, data):
        cursor = self.conn.cursor()
        ext = Path(data['path']).suffix.lower()
        cursor.execute('''
            INSERT OR REPLACE INTO documents 
            (file_path, file_name, content, preview, meta_json, last_modified, extension, file_size)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (data['path'], data['name'], data['content'], data['preview'], data['meta'],
              data['mtime'], ext, data['size']))
        row_id = cursor.lastrowid
        cursor.execute("INSERT INTO documents_fts(rowid, content) VALUES(?, ?)", (row_id, data['content']))

    def search(self, query_text, mode="content", allowed_exts=None, limit=100):
        cursor = self.conn.cursor()
        ext_filter = ""
        params = []
        if allowed_exts:
            placeholders = ",".join(["?"] * len(allowed_exts))
            ext_filter = f"AND d.extension IN ({placeholders})"
            params.extend(allowed_exts)

        if mode == "content":
            words = re.sub(r'[^\w\s]', '', query_text).split()
            fts_query = " AND ".join([f"{w}*" for w in words]) if words else ""
            if not fts_query: return []
            sql = f'''
                SELECT d.file_name, d.file_path, d.last_modified, d.file_size, d.content
                FROM documents d
                JOIN documents_fts f ON d.id = f.rowid
                WHERE documents_fts MATCH ? {ext_filter}
                ORDER BY rank LIMIT ?
            '''
            execute_params = [fts_query] + params + [limit]
        else:
            sql = f'''
                SELECT file_name, file_path, last_modified, file_size, content
                FROM documents d
                WHERE file_path LIKE ? {ext_filter}
                ORDER BY last_modified DESC LIMIT ?
            '''
            execute_params = [f"%{query_text}%"] + params + [limit]

        try:
            cursor.execute(sql, execute_params)
            return cursor.fetchall()
        except sqlite3.OperationalError:
            return []