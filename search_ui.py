import tkinter as tk
from tkinter import ttk, filedialog
from datetime import datetime
import threading
import re


def query_parser(query):
    pattern = r'(path|content):(?:"([^"]*)"|([^\s]+))'

    matches = re.findall(pattern, query)#each match in the query is saved and checking
    queries = []

    for key, quoted_val, unquoted_val in matches:
        #if value in quotes, use it, else use the unquoted value
        value = quoted_val if quoted_val else unquoted_val
        queries.append({key: value})

    return queries


class SearchUI:
    def __init__(self, root, crawler, db):
        self.root, self.crawler, self.db = root, crawler, db
        self.root.title("FlashSearch Pro v1.5")
        self.root.geometry("1200x850")
        self.page = 0
        self.filter_vars = {}

        main_container = ttk.Frame(root, padding="15")
        main_container.pack(fill=tk.BOTH, expand=True)

        # controls
        ctrl_frame = ttk.Frame(main_container)
        ctrl_frame.pack(fill=tk.X, pady=(0, 10))


        self.sort_mode = tk.StringVar(value="name")#re-added the buttons for sorting purposes
        ttk.Radiobutton(ctrl_frame, text="Sort alphabetically", variable=self.sort_mode, value="alphabetically",
                        command=self.perform_search).pack(side=tk.LEFT)
        ttk.Radiobutton(ctrl_frame, text="Sort by date accessed", variable=self.sort_mode, value="date",
                        command=self.perform_search).pack(side=tk.LEFT, padx=15)


        #reduce number of results displayed at a time
        self.limit_var = tk.StringVar(value="25")  # Default limit
        ttk.Label(ctrl_frame, text="Show:").pack(side=tk.LEFT, padx=(10, 2))
        self.limit_combo = ttk.Combobox(
            ctrl_frame,
            textvariable=self.limit_var,
            values=("10", "25", "50", "100", "All"),
            width=5,
            state="readonly"
        )
        self.limit_combo.pack(side=tk.LEFT)
        self.limit_combo.bind("<<ComboboxSelected>>", lambda e: self.perform_search())

        #extension filter
        self.filter_btn = ttk.Menubutton(ctrl_frame, text="Filter Extensions")
        self.filter_btn.pack(side=tk.RIGHT)
        self.filter_menu = tk.Menu(self.filter_btn, tearoff=False)
        self.filter_btn.config(menu=self.filter_menu)

        # search bar
        #navigation buttons for the table, takes a lot of time to go display the results
        nav_frame = ttk.Frame(main_container)
        nav_frame.pack(fill=tk.X, pady=(0, 5))

        self.prev_btn = ttk.Button(nav_frame, text="<-", width=5, command=lambda: self.change_page(-1))
        self.prev_btn.pack(side=tk.LEFT)

        self.page_label = ttk.Label(nav_frame, text="0-0 of 0", font=('Segoe UI', 9, 'bold'))
        self.page_label.pack(side=tk.LEFT, padx=20)

        self.next_btn = ttk.Button(nav_frame, text="->", width=5, command=lambda: self.change_page(1))
        self.next_btn.pack(side=tk.LEFT)
        #very useful, can be used to navigate through the results much easier

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
    #function replaces some functionalities of the previously used perform_search function
    def change_page(self, delta):
        limit_str = self.limit_var.get()
        if limit_str == "All":
            return

        limit = int(limit_str)
        new_page = self.page + delta

        # Calculate max possible page
        total_results = len(self.results_data)
        max_page = (total_results - 1) // limit if total_results > 0 else 0

        if 0 <= new_page <= max_page:
            self.page = new_page
            self.update_table_display()

    def update_table_display(self):
        #delete all the items in the table
        for item in self.tree.get_children():
            self.tree.delete(item)

        total = len(self.results_data)
        limit_str = self.limit_var.get()

        if limit_str == "All":
            display_list = self.results_data
            start_idx = 0
            end_idx = total
        else:
            limit = int(limit_str)
            start_idx = self.page * limit
            end_idx = min(start_idx + limit, total)
            display_list = self.results_data[start_idx:end_idx]

        #insert the new items into the table
        for i, (name, path, mtime, size, content) in enumerate(display_list):
            date_str = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M')
            size_str = self.format_size(size)
            actual_idx = start_idx + i
            self.tree.insert("", tk.END, iid=actual_idx, values=(name, size_str, date_str, path))

        #update labels and buttons
        range_text = f"{start_idx + 1}-{end_idx} of {total}" if total > 0 else "0-0 of 0"
        self.page_label.config(text=range_text)

        #disable prev/next buttons if we're at the beginning/end of the list
        self.prev_btn.config(state=tk.NORMAL if self.page > 0 else tk.DISABLED)
        if limit_str == "All":
            self.next_btn.config(state=tk.DISABLED)
        else:
            self.next_btn.config(state=tk.NORMAL if end_idx < total else tk.DISABLED)

    def perform_search(self):
        self.page = 0 #whenever we search reset the page to 0
        raw_query = self.query_var.get()

        if not raw_query:
            for item in self.tree.get_children(): self.tree.delete(item)
            self.status_var.set("Ready")
            self.page_label.config(text="0-0 of 0")
            return
        #if no valid search functions were found default to search by path
        parsed_criteria = query_parser(raw_query) or [{'path': raw_query}]
        allowed = [ext for ext, var in self.filter_vars.items() if var.get()]

        #fetch from db once
        self.results_data = self.db.search(criteria=parsed_criteria, allowed_exts=allowed, sort_type=self.sort_mode.get())

        #use the new display function to update the table
        self.update_table_display()
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