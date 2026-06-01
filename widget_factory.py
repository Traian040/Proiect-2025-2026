from collections import Counter
from pathlib import Path


class WidgetStrategy:
    def evaluate(self, results, ext_counts, query, total_results):
        raise NotImplementedError("Strategies must implement evaluate method.")

    def get_button_data(self):
        raise NotImplementedError("Strategies must return button text and command.")


class GalleryWidgetStrategy(WidgetStrategy):
    def evaluate(self, results, ext_counts, query, total_results):
        image_exts = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'}
        img_count = sum(ext_counts.get(ext, 0) for ext in image_exts)

        #if more then 30% of the results are images, or the query contains 'image' or 'color:'
        return total_results > 0 and (
                img_count / total_results > 0.3 or
                'image' in query.lower() or
                'color:' in query.lower()
        )

    def get_button_data(self):
        return "Gallery view", lambda: print("[Widget Activated] Opening Gallery View...")


class LogAnalyzerWidgetStrategy(WidgetStrategy):
    def evaluate(self, results, ext_counts, query, total_results):
        log_count = ext_counts.get('.log', 0)

        #make visible if more then 40% of the results are logs
        return total_results > 0 and (log_count / total_results >= 0.4)

    def get_button_data(self):
        return "Analyze logs", lambda: print("[Widget Activated]Opening Log Analyzer...")


class WidgetFactory:
    def __init__(self):
        #register the strategies, more cna be added here
        self.strategies = [
            GalleryWidgetStrategy(),
            LogAnalyzerWidgetStrategy()
        ]

    def get_active_widgets(self, results, raw_query):
        if not results:
            return []

        #precalculate the extension counts once to maintain performance
        ext_counts = Counter(Path(res[1]).suffix.lower() for res in results)
        total_results = len(results)

        active_widgets = []
        for strategy in self.strategies:
            if strategy.evaluate(results, ext_counts, raw_query, total_results):
                active_widgets.append(strategy.get_button_data())

        return active_widgets