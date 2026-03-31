import re
from pathlib import Path
from bs4 import BeautifulSoup

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

