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

    def calculate_path_score(self, file_path):
        #calculate at index time the cost
        path_obj = Path(file_path)
        parts = path_obj.parts
        #base score
        score = 100.0
        flat_increment = 25
        mult_decrement = .1
        #the deeper the file the lower the score
        depth = len(parts)
        score -= (depth * 5)

        #penalties based on the contents of the file path
        path_lower = file_path.lower()
        sep = os.sep

        #for certain directories boost the score
        high_value_dirs = ['src', 'lib', 'docs', 'documents', 'main', 'app', 'downloads']
        for d in high_value_dirs:
            if f"{sep}{d}{sep}" in path_lower or path_lower.endswith(f"{sep}{d}"):
                score += flat_increment
        #for other directories cut the score
        low_value_dirs = ['.git', 'node_modules', 'venv', 'env', '__pycache__', 'build', 'dist', 'out', 'tmp']
        for d in low_value_dirs:
            if f"{sep}{d}{sep}" in path_lower:
                score *= mult_decrement
        #clamp the score
        return max(0.0, score)

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
                        #calculate the score
                        path_score = self.calculate_path_score(path)
                        self.db.upsert_document({
                            'path': path, 'name': file, 'content': content,
                            'preview': preview, 'meta': "{}", 'mtime': mtime, 'size': size,
                            'path_score': path_score
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
            print(f"EROARE: {e}")
        finally:
            if complete_callback:
                complete_callback()