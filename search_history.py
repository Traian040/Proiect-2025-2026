from collections import Counter

class SearchObserver:
    def on_search_executed(self, raw_query, parsed_criteria):
        pass

    def on_result_selected(self, query, file_path):
        #called when a result is selected in the search results
        pass


class SearchSubject:
    def __init__(self):
        self._observers = []

    def attach(self, observer: SearchObserver):
        self._observers.append(observer)

    def notify_search(self, raw_query, parsed_criteria):
        for observer in self._observers:
            observer.on_search_executed(raw_query, parsed_criteria)

    def notify_selection(self, query, file_path):
        for observer in self._observers:
            observer.on_result_selected(query, file_path)
#implementing the observer pattern
class SearchHistoryManager(SearchObserver):
    def __init__(self):
        #save the frequency with which a qurey is searched
        self.query_history = Counter()
        #save the frequency with which a file is clicked
        self.click_history = Counter()

    def on_search_executed(self, raw_query, parsed_criteria):
        if raw_query.strip():
            self.query_history[raw_query] += 1
            print(f"[Tracker] Tracked query: '{raw_query}'. Total searches: {self.query_history[raw_query]}")

    def on_result_selected(self, query, file_path):
        if query.strip():
            self.click_history[(query, file_path)] += 1
            print(f"[Tracker] Tracked click on: '{file_path}' for query '{query}'")

    def get_popular_queries(self, prefix="", limit=5):
        #return the most popular queries that contain with the given prefix
        matches = [q for q, count in self.query_history.most_common() if prefix in q and prefix != q]
        return matches[:limit]
