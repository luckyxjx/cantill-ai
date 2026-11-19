import re
import pandas as pd
from typing import Optional, Dict, Any, List, Tuple
from difflib import SequenceMatcher
try:
    from rapidfuzz import fuzz
    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False

from .config import ITEM_MASTER_CSV

ALIAS_MAP = {
    'brg': 'bearing',
    'pneu': 'pneumatic',
    'hyd': 'hydraulic',
    'welding rod': 'welding electrode',
    'welding electrodes': 'welding electrode',
    'monitor 24\"': '24 inch monitor',
    '24\" monitor': '24 inch monitor',
    '24 inch led monitor': '24 inch monitor',
    'gloves nitrile': 'nitrile coated gloves',
    'shoes safety': 'safety shoes steel toe',
}

NOISE_WORDS = [
    r'\bas per sample\b',
    r'\burgent\b',
    r'- urgent',
    r'\(repeat\)',
    r'\bfor maintenance\b',
    r'\bimmediate\b',
    r'\brequired\b',
]

def clean_text(text: str) -> str:
    if not text:
        return ""
    text = str(text).lower()
    for noise in NOISE_WORDS:
        text = re.sub(noise, '', text, flags=re.IGNORECASE)
    for k, v in ALIAS_MAP.items():
        text = re.sub(rf'\b{re.escape(k)}\b', v, text, flags=re.IGNORECASE)
    text = re.sub(r'[^a-z0-9\s/.-]', ' ', text)
    return ' '.join(text.split())

class ItemMatcher:
    def __init__(self, item_master_path=ITEM_MASTER_CSV):
        self.df = pd.read_csv(item_master_path)
        self.items = []
        self.item_map = {}
        for _, row in self.df.iterrows():
            code = str(row['item_code']).strip()
            desc = str(row['description']).strip()
            c_desc = clean_text(desc)
            info = {
                'item_code': code,
                'description': desc,
                'clean_description': c_desc,
                'uom': str(row['uom']).strip(),
                'category': str(row['category']).strip(),
                'item_type': str(row['item_type']).strip(),
                'standard_price': float(row['standard_price'])
            }
            self.items.append(info)
            self.item_map[code] = info

    def get_by_code(self, item_code: str) -> Optional[Dict[str, Any]]:
        return self.item_map.get(str(item_code).strip())

    def match(self, description: str, threshold: float = 0.65) -> Tuple[str, Optional[Dict[str, Any]], float]:
        """
        Returns (resolved_code, matched_item_info, confidence)
        If no match above threshold, returns ("NEW", None, confidence)
        """
        if not description or not description.strip():
            return "NEW", None, 0.0

        c_query = clean_text(description)
        tokens_query = set(c_query.split())

        best_score = 0.0
        best_item = None

        for item in self.items:
            c_target = item['clean_description']
            tokens_target = set(c_target.split())
            
            # 1. Exact match
            if c_query == c_target:
                return item['item_code'], item, 1.0

            # 2. Token overlap score
            overlap = len(tokens_query & tokens_target) / max(len(tokens_query), 1)
            
            # 3. Fuzzy similarity
            if HAS_RAPIDFUZZ:
                token_sort = fuzz.token_sort_ratio(c_query, c_target) / 100.0
                token_set = fuzz.token_set_ratio(c_query, c_target) / 100.0
                ratio = fuzz.ratio(c_query, c_target) / 100.0
                fuzzy_score = max(token_sort, 0.5 * token_set + 0.5 * token_sort, ratio)
            else:
                fuzzy_score = SequenceMatcher(None, c_query, c_target).ratio()

            combined_score = max(overlap, fuzzy_score)

            if combined_score > best_score:
                best_score = combined_score
                best_item = item

        if best_score >= threshold and best_item is not None:
            return best_item['item_code'], best_item, round(best_score, 3)
        
        return "NEW", None, round(best_score, 3)

    def find_suggestions(self, query: str, top_n: int = 3) -> List[Dict[str, Any]]:
        """Finds close matches for user suggestions during chat intake."""
        c_query = clean_text(query)
        candidates = []
        for item in self.items:
            c_target = item['clean_description']
            if HAS_RAPIDFUZZ:
                score = fuzz.token_set_ratio(c_query, c_target) / 100.0
            else:
                score = SequenceMatcher(None, c_query, c_target).ratio()
            candidates.append((item, score))
        candidates.sort(key=lambda x: x[1], reverse=True)
        return [c[0] for c in candidates[:top_n] if c[1] >= 0.4]
