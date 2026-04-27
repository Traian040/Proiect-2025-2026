import tkinter as tk
from tkinter import ttk, filedialog
from datetime import datetime
import threading
import re


def query_parser(query):
    query_list = query.split()
    queries = {}
    for item in query_list:
        if ':' in item:
            command = item.split(':', 1)
            if command[0] in ['path', 'content']:
                queries[command[0]] = command[1]
    return queries


class SearchUI:
    def __init__(self, root, crawler, db):
        self.root, self.crawler, self.db = root, crawler, db
        self.root.title("FlashSearch Pro v1.5")
        self.root.geometry("1200x850")

        self.filter_vars = {}

        main_container = ttk.Frame(root, padding="15")
        main_container.pack(fill=tk.BOTH, expand=True)

        # controls
        ctrl_frame = ttk.Frame(main_container)
        ctrl_frame.pack(fill=tk.X, pady=(0, 10))



        self.filter_btn = ttk.Menubutton(ctrl_frame, text="Filter Extensions")
        self.filter_btn.pack(side=tk.RIGHT)
        self.filter_menu = tk.Menu(self.filter_btn, tearoff=False)
        self.filter_btn.config(menu=self.filter_menu)

        # search bar

        self.query_var = tk.StringVar()
        self.query_var.trace_add("write", lambda *args: self.perform_search())
        self.search_entry = ttk.Entry(ctrl_frame, textvariable=self.query_var, font=('Segoe UI', 11))
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        self.search_entry.focus_set()

        self.index_btn = ttk.Button(ctrl_frame, text="Index Folder", command=self.run_crawler)
        self.index_btn.pack(side=tk.RIGHT, padx=(5, 0))


        #scroll bar
        table_container = ttk.Frame(main_container)
        table_container.pack(fill=tk.BOTH, expand=True)

        cols = ("File", "Size", "Date Modified", "Path")
        self.tree = ttk.Treeview(table_container, columns=cols, show='headings')

        #scrollbar
        table_scroll = ttk.Scrollbar(table_container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=table_scroll.set)

        for col in cols: self.tree.heading(col, text=col)
        self.tree.column("File", width=200)
        self.tree.column("Size", width=80, anchor=tk.E)
        self.tree.column("Date Modified", width=150)
        self.tree.column("Path", width=400)

        table_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.tree.bind("<<TreeviewSelect>>", self.show_content)

        # read view
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
        raw_query = self.query_var.get()
        if not raw_query:
            for item in self.tree.get_children(): self.tree.delete(item)
            self.status_var.set("Ready")
            return

        #tag parsing
        parsed_criteria = query_parser(raw_query)

        #if no tags, use default content search
        if not parsed_criteria:
            parsed_criteria = {'content': raw_query}

        allowed = [ext for ext, var in self.filter_vars.items() if var.get()]

        #clear the table every time a new search is performed
        for item in self.tree.get_children():
            self.tree.delete(item)

        #perform search using parsed criteria
        self.results_data = self.db.search(criteria=parsed_criteria, allowed_exts=allowed)

        #insert results into table
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