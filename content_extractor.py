import re
import json
from pathlib import Path
from bs4 import BeautifulSoup
from PIL import Image
import colorsys
#content extractor, data handler


class ContentExtractorStrategy:
    def extract(self, file_path, stats):
        raise NotImplementedError("Strategies must implement the extract method.")


class TextExtractionStrategy(ContentExtractorStrategy):
    def extract(self, file_path, stats):
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                raw_text = f.read()

            if Path(file_path).suffix.lower() in ['.html', '.htm']:
                soup = BeautifulSoup(raw_text, 'html.parser')
                for j in soup(['script', 'style']): j.decompose()
                raw_text = soup.get_text(separator=' ')

            clean_text = re.sub(r'\s+', ' ', raw_text).strip()
            preview = (clean_text[:150] + "...") if len(clean_text) > 150 else clean_text

            #return empyt json for meta
            return clean_text, preview, stats.st_size, "{}"
        except:
            return None, None, None, "{}"


class ImageExtractionStrategy(ContentExtractorStrategy):
    #map color names to their hue values
    #S and V are handled separately
    HUES = {
        "red": 0.0,  # or 1.0 (it wraps around)
        "orange": 0.08,
        "yellow": 0.16,
        "green": 0.33,
        "blue": 0.66,
        "purple": 0.83,
        "pink": 0.91
    }

    def _get_dominant_color(self, img_path):
        try:
            with Image.open(img_path) as img:
                img = img.convert("RGB")
                img.thumbnail((50, 50))

                colors = img.getcolors(maxcolors=2500)
                if colors:
                    most_common_rgb = max(colors, key=lambda item: item[0])[1]
                else:
                    img_small = img.resize((1, 1))
                    most_common_rgb = img_small.getpixel((0, 0))

                #normlize RGB values to 0-1
                r, g, b = [x / 255.0 for x in most_common_rgb]
                h, s, v = colorsys.rgb_to_hsv(r, g, b)

                #handle grayscale
                if v < 0.15: return "black"
                if s < 0.15 and v > 0.85: return "white"
                if s < 0.15: return "gray"

                #check for dominant colors
                if 0.05 <= h <= 0.15 and v < 0.6: return "brown"

                #find the closest hue to the dominant color
                #min distance since HUE is a circular value
                min_dist = float('inf')
                closest_name = None

                for name, target_hue in self.HUES.items():
                    #calculate circular distance between the two hues
                    dist = min(abs(h - target_hue), 1.0 - abs(h - target_hue))
                    if dist < min_dist:
                        min_dist = dist
                        closest_name = name

                return closest_name
        except Exception:
            return None

    def extract(self, file_path, stats):
        dom_color = self._get_dominant_color(file_path)
        meta = json.dumps({"color": dom_color}) if dom_color else "{}"
        #index color as name for fts index
        content = dom_color or "image"
        preview = f"[Image File] Dominant Color: {dom_color}" if dom_color else "[Image File]"

        return content, preview, stats.st_size, meta


class ContentExtractor:
    def __init__(self):
        self.text_strategy = TextExtractionStrategy()
        self.image_strategy = ImageExtractionStrategy()
        self.image_exts = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'}

    def extract(self, file_path):
        try:
            path_obj = Path(file_path)
            stats = path_obj.stat()

            #select the appropriate strategy based on file extension
            if path_obj.suffix.lower() in self.image_exts:
                return self.image_strategy.extract(file_path, stats)
            else:
                return self.text_strategy.extract(file_path, stats)
        except:
            return None, None, None, "{}"