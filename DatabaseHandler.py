import os
import sqlite3
import json
import re
import tkinter as tk
from tkinter import ttk, filedialog
from pathlib import Path
from bs4 import BeautifulSoup
from datetime import datetime
import threading


# database handler
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


# content extractor, data handler
class ContentExtractor:
    def extract(self, file_path):
        try:
            path_obj = Path(file_path)
            stats = path_obj.stat()
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                raw_text = f.read()

            if path_obj.suffix.lower() in ['.html', '.htm']:
                soup = BeautifulSoup(raw_text, 'html.parser')
                for j in soup(['script', 'style']): j.decompose()
                raw_text = soup.get_text(separator=' ')

            clean_text = re.sub(r'\s+', ' ', raw_text).strip()
            preview = (clean_text[:150] + "...") if len(clean_text) > 150 else clean_text
            return clean_text, preview, stats.st_size
        except:
            return None, None, None


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


# user interface
class SearchUI:
    def __init__(self, root, crawler, db):
        self.root, self.crawler, self.db = root, crawler, db
        self.root.title("FlashSearch Pro v1.5")
        self.root.geometry("1200x850")

        self.filter_vars = {}

        main_container = ttk.Frame(root, padding="15")
        main_container.pack(fill=tk.BOTH, expand=True)

        # controles
        ctrl_frame = ttk.Frame(main_container)
        ctrl_frame.pack(fill=tk.X, pady=(0, 10))

        self.search_mode = tk.StringVar(value="content")
        ttk.Radiobutton(ctrl_frame, text="Search Content", variable=self.search_mode, value="content",
                        command=self.perform_search).pack(side=tk.LEFT)
        ttk.Radiobutton(ctrl_frame, text="Search Name/Path", variable=self.search_mode, value="name",
                        command=self.perform_search).pack(side=tk.LEFT, padx=15)

        self.filter_btn = ttk.Menubutton(ctrl_frame, text="Filter Extensions")
        self.filter_btn.pack(side=tk.RIGHT)
        self.filter_menu = tk.Menu(self.filter_btn, tearoff=False)
        self.filter_btn.config(menu=self.filter_menu)

        # search bar
        search_frame = ttk.Frame(main_container)
        search_frame.pack(fill=tk.X, pady=5)
        self.query_var = tk.StringVar()
        self.query_var.trace_add("write", lambda *args: self.perform_search())
        self.search_entry = ttk.Entry(search_frame, textvariable=self.query_var, font=('Segoe UI', 11))
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        self.search_entry.focus_set()

        self.index_btn = ttk.Button(search_frame, text="Index Folder", command=self.run_crawler)
        self.index_btn.pack(side=tk.RIGHT)

        # table display
        cols = ("File", "Size", "Date Modified", "Path")
        self.tree = ttk.Treeview(main_container, columns=cols, show='headings')
        for col in cols: self.tree.heading(col, text=col)
        self.tree.column("File", width=200)
        self.tree.column("Size", width=80, anchor=tk.E)
        self.tree.column("Date Modified", width=150)
        self.tree.column("Path", width=400)
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.show_content)

        # reading
        view_frame = ttk.LabelFrame(main_container, text="Full File Content", padding="10")
        view_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        scrollbar = ttk.Scrollbar(view_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.content_text = tk.Text(view_frame, wrap=tk.WORD, font=('Consolas', 10),
                                    state=tk.DISABLED, bg="#ffffff", yscrollcommand=scrollbar.set)
        self.content_text.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.content_text.yview)

        # status bar
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W).pack(side=tk.BOTTOM, fill=tk.X)

        self.results_data = []
        self.update_filter_menu()

    def format_size(self, size_bytes):
        if not size_bytes: return "0 B"
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:3.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:3.1f} TB"

    def update_filter_menu(self):
        self.filter_menu.delete(0, tk.END)
        for ext in self.db.get_all_extensions():
            if ext not in self.filter_vars: self.filter_vars[ext] = tk.BooleanVar(value=False)
            self.filter_menu.add_checkbutton(label=ext, variable=self.filter_vars[ext], command=self.perform_search)

    def perform_search(self):
        query = self.query_var.get()
        allowed = [ext for ext, var in self.filter_vars.items() if var.get()]

        for item in self.tree.get_children(): self.tree.delete(item)
        self.results_data = self.db.search(query, mode=self.search_mode.get(), allowed_exts=allowed)

        for i, (name, path, mtime, size, content) in enumerate(self.results_data):
            date_str = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M')
            size_str = self.format_size(size)
            self.tree.insert("", tk.END, iid=i, values=(name, size_str, date_str, path))

        self.status_var.set(f"Found {len(self.results_data)} matches")

    def run_crawler(self):
        directory = filedialog.askdirectory()
        if directory:
            self.index_btn.config(state=tk.DISABLED)
            self.status_var.set("Indexing started...")

            thread = threading.Thread(
                target=self.crawler.crawl,
                args=(directory,),
                kwargs={
                    'progress_callback': lambda f: self.root.after(0, self.status_var.set, f"Indexing: {f}"),
                    'complete_callback': lambda: self.root.after(0, self.on_crawl_complete)
                },
                daemon=True
            )
            thread.start()

    def on_crawl_complete(self):
        self.status_var.set("Indexing Complete.")
        self.index_btn.config(state=tk.NORMAL)
        self.update_filter_menu()

    def show_content(self, event):
        selected = self.tree.selection()
        if not selected: return
        idx = int(selected[0])

        full_content = self.results_data[idx][4]

        self.content_text.config(state=tk.NORMAL)
        self.content_text.delete(1.0, tk.END)
        self.content_text.insert(tk.END, full_content)
        self.content_text.config(state=tk.DISABLED)


if __name__ == "__main__":
    db_inst = DatabaseHandler()
    #in case the database information is changed(names of columns, added columns, etc)
    #set the flag tpt to true to wipe the database and start fresh
    db_inst.init_db(fresh_start=False)

    crawler_inst = FileSystemCrawler(db_inst, ContentExtractor())
    win = tk.Tk()
    app = SearchUI(win, crawler_inst, db_inst)
    win.mainloop()