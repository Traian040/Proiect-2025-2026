import tkinter as tk
from database_handler import DatabaseHandler
from crawler import FileSystemCrawler
from content_extractor import ContentExtractor
from search_ui import SearchUI
from search_history import SearchHistoryManager

if __name__ == "__main__":
    db_inst = DatabaseHandler()
    #in case the database information is changed(names of columns, added columns, etc)
    #set the flag to true to wipe the database and start fresh
    db_inst.init_db(fresh_start=False)

    crawler_inst = FileSystemCrawler(db_inst, ContentExtractor())
    history_manager = SearchHistoryManager()
    win = tk.Tk()
    app = SearchUI(win, crawler_inst, db_inst, history_manager)
    win.mainloop()