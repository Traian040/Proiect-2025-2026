import os
import sqlite3
import json
from pathlib import Path
from bs4 import BeautifulSoup
import re


class DatabaseHandler:
    def __init__(self, db_name="search_engine.db"):
        self.db_name = db_name
        self.conn = sqlite3.connect(self.db_name)

    # db setup
    def init_db(self, fresh_start=True):
        cursor = self.conn.cursor()

        # wipe if fresh start
        if fresh_start:
            cursor.execute('DROP TABLE IF EXISTS documents')

        cursor.execute('''
                       CREATE TABLE IF NOT EXISTS documents
                       (
                           id INTEGER PRIMARY KEY AUTOINCREMENT,
                           file_path TEXT UNIQUE,
                           file_name TEXT,
                           content TEXT,
                           preview TEXT,
                           meta_json TEXT
                       )
                       ''')
        self.conn.commit()

    # filtering
    def process_file(self, file_path):
        path_obj = Path(file_path)
        ext = path_obj.suffix.lower()

        # collect metadata
        stats = path_obj.stat()
        metadata = {
            "extension": ext,
            "size_bytes": stats.st_size,
            "last_modified": stats.st_mtime,
            "created": stats.st_ctime
        }

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                raw_text = f.read()

            # html parsing
            if ext in ['.html', '.htm']:
                soup = BeautifulSoup(raw_text, 'html.parser')
                # Remove scripts, styles, and nav to keep "quality" data
                for junk in soup(['script', 'style', 'nav', 'footer', 'header']):
                    junk.decompose()
                clean_text = soup.get_text(separator=' ')
            else:
                clean_text = raw_text

            clean_text = re.sub(r'\s+', ' ', clean_text).strip()

            # have a preview
            lines = [line.strip() for line in clean_text.split('.') if line.strip()]
            preview = ". ".join(lines[:3]) + "..."

            return clean_text, preview, json.dumps(metadata)

        except Exception as e:
            print(f"Error processing {file_path}: {e}")
            return None, None, None

    # crawler
    def crawl(self, directory):
        cursor = self.conn.cursor()
        target_exts = {
            ".txt", ".log",
            ".csv", ".json", ".xml", ".yaml", ".yml", ".ini", ".conf", ".cfg", ".env",
            ".html", ".htm", ".css", ".js", ".jsx", ".ts", ".tsx", ".svg",
            ".py", ".java", ".c", ".cpp", ".h", ".hpp", ".cs", ".rb", ".go", ".rs", ".php", ".swift", ".kt",
            ".sh", ".bash", ".ps1", ".bat", ".sql",
            ".md", ".markdown", ".tex", ".rst", ".asciidoc"
        }

        for root, _, files in os.walk(directory):
            for file in files:
                file_path = os.path.join(root, file)
                if Path(file_path).suffix.lower() in target_exts:
                    content, preview, meta = self.process_file(file_path)

                    if content:
                        cursor.execute('''
                            INSERT OR REPLACE INTO documents 
                            (file_path, file_name, content, preview, meta_json)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (file_path, file, content, preview, meta))

        self.conn.commit()

    def close(self):
        self.conn.close()


if __name__ == "__main__":
    # run setup
    root_to_search = "C:/Users/traia/Documents"
    db_manager = DatabaseHandler()
    db_manager.init_db()
    db_manager.crawl(root_to_search)

    # testing
    cursor = db_manager.conn.cursor()
    cursor.execute("SELECT file_name, preview, meta_json FROM documents ORDER BY file_name ASC LIMIT 20")
    results = cursor.fetchall()

    for name, preview, metadata in results:
        print(f"FILE: {name}\nPREVIEW: {preview}\nMetadata: {metadata}\n{'-' * 20}")

    cursor.execute("SELECT COUNT(*) FROM documents")
    result = cursor.fetchone()
    print(f"Total files indexed: {result[0]}")

    db_manager.close()