import os
import re
from pathlib import Path
from bs4 import BeautifulSoup

# crawler
class FileSystemCrawler:
    def __init__(self, db, extractor):
        self.db, self.extractor = db, extractor
        self.target_exts = {
            ".txt", ".log", ".csv", ".json", ".xml", ".yaml", ".yml", ".ini",
            ".conf", ".cfg", ".env", ".html", ".htm", ".css", ".js", ".jsx",
            ".ts", ".tsx", ".svg", ".py", ".java", ".c", ".cpp", ".h", ".hpp",
            ".cs", ".rb", ".go", ".rs", ".php", ".swift", ".kt", ".sh", ".bash",
            ".ps1", ".bat", ".sql", ".md", ".markdown", ".tex", ".rst", ".asciidoc"
        }

    def crawl(self, root_dir, progress_callback=None, complete_callback=None):
        count = 0
        self.db.conn.execute("BEGIN TRANSACTION")
        try:
            for root, _, files in os.walk(root_dir):
                for file in files:
                    path = os.path.normpath(os.path.join(root, file))
                    if Path(path).suffix.lower() not in self.target_exts: continue
                    mtime = os.path.getmtime(path)
                    if (stored := self.db.get_stored_mtime(path)) and mtime <= stored: continue

                    content, preview, size = self.extractor.extract(path)
                    if content:
                        self.db.upsert_document({
                            'path': path, 'name': file, 'content': content,
                            'preview': preview, 'meta': "{}", 'mtime': mtime, 'size': size
                        })
                        count += 1
                        if count % 500 == 0:
                            self.db.conn.commit()
                            self.db.conn.execute("BEGIN TRANSACTION")
                        if progress_callback:
                            progress_callback(file)
            self.db.conn.commit()
        except Exception as e:
            self.db.conn.rollback()
        finally:
            if complete_callback:
                complete_callback()