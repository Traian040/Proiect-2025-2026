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

    def search(self, criteria, allowed_exts=None, sort_type="alphabetically"):
        cursor = self.conn.cursor()
        where_clauses = []
        params = []
        join_fts = False

        # criteria is now a list of dictionaries: [{"path": "val"}, {"content": "val"}, {"path": "word1 word2"}]
        # to allow for multiple criteria
        for criterion in criteria:
            for key, value in criterion.items():
                if not value:
                    continue

                if key == 'content':
                    #clean and format
                    words = re.sub(r'[^\w\s]', '', value).split()
                    fts_query = " AND ".join([f"{w}*" for w in words])
                    if fts_query:
                        #multiple matches
                        where_clauses.append("documents_fts MATCH ?")
                        params.append(fts_query)
                        join_fts = True

                elif key == 'path':
                    where_clauses.append("d.file_path LIKE ?")
                    params.append(f"%{value}%")

        #filter extension
        if allowed_exts:
            placeholders = ",".join(["?"] * len(allowed_exts))
            where_clauses.append(f"d.extension IN ({placeholders})")
            params.extend(allowed_exts)

        #base version of the sql query with no values or filtering
        sql = "SELECT d.file_name, d.file_path, d.last_modified, d.file_size, d.content FROM documents d"

        #fts join
        if join_fts:
            sql += " JOIN documents_fts f ON d.id = f.rowid"

        if where_clauses:
            sql += " WHERE " + " AND ".join(where_clauses)

        #sorting logic at the end
        if sort_type == "alphabetically":
            sql += " ORDER BY LOWER(d.file_name) ASC"
        elif sort_type == "date":
            sql += " ORDER BY d.last_modified DESC"

        try:
            cursor.execute(sql, params)
            return cursor.fetchall()
        except Exception as e:
            print(f"Database Error: {e}")
            return []