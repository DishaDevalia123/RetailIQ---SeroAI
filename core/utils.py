# utils.py

import re
from datetime import datetime
import rapidfuzz
from spellchecker import SpellChecker
from rapidfuzz import fuzz
import pandas as pd

SALE_QTY_SQL_ALIASES = ['sale_qty', 'qty', 'quantity', 'sale_quantity', 'total_qty']
AMOUNT_SQL_ALIASES = ['amount', 'total_amount', 'sale_amount', 'revenue', 'value']

GLOBAL_SPELLCHECKER = SpellChecker()

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    "january": 1, "february": 2, "march": 3, "april": 4, "june": 6, "july": 7,
    "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}

VALID_PATTERNS = ['Checks', 'Print', 'Plain']
VALID_COLORS = ["Red", "Blue", "Green", "Black", "White", "Grey"]
VALID_BRANDS = ["Sero", 'Freezone', 'HV', 'Sero Trousers','Fairdeal']
VALID_SUB_BRANDS = ['HV', 'Formals','Freezone Casuals','Freezone Boys','Uth','Premium','White Gold','Marry Me','Cotton Trousers','Denim', 'Formal Trousers', 'Fairdeal']
VALID_STORES = ["PRFRS", "PRFCO", "PRFT", "MEM"]
VALID_ITEM_DIVISIONS = ["Shirt", "Trousers"] 
VALID_SLEEVES = ["F", 'H', 'P']
VALID_SIZES = [36, 37, 38, 39, 40, 41, 42] 
VALID_FESTIVALS = ["diwali", "pongal", "christmas"]

VALUE_TO_ENTITY = {}   
# Brands
for brand in VALID_BRANDS:
    VALUE_TO_ENTITY[brand.lower()] = "brand"
    if not brand.lower().endswith('s'):
        VALUE_TO_ENTITY[brand.lower() + 's'] = "brand"

# Sub-brands
for sub_brand in VALID_SUB_BRANDS:
    VALUE_TO_ENTITY[sub_brand.lower()] = "sub_brand"
    if not sub_brand.lower().endswith('s'):
        VALUE_TO_ENTITY[sub_brand.lower() + 's'] = "sub_brand"
    elif sub_brand.lower().endswith('s'):
        # Handle cases where official name ends with 's' but user might enter without it
        VALUE_TO_ENTITY[sub_brand.lower()[:-1]] = "sub_brand" 

# Stores
for store in VALID_STORES:
    VALUE_TO_ENTITY[store.lower()] = "store"
    if not store.lower().endswith('s'):
        VALUE_TO_ENTITY[store.lower() + 's'] = "store"

# Patterns
for pattern in VALID_PATTERNS:
    VALUE_TO_ENTITY[pattern.lower()] = "pattern"
    if not pattern.lower().endswith('s'):
        VALUE_TO_ENTITY[pattern.lower() + 's'] = "pattern"

# Colors
for color in VALID_COLORS:
    VALUE_TO_ENTITY[color.lower()] = "color"
    if not color.lower().endswith('s'):
        VALUE_TO_ENTITY[color.lower() + 's'] = "color"

# Item divisions
for item_division in VALID_ITEM_DIVISIONS:
    VALUE_TO_ENTITY[item_division.lower()] = "item_division"
    if not item_division.lower().endswith('s'):
        VALUE_TO_ENTITY[item_division.lower() + 's'] = "item_division"

# Sleeves - these are single letters so no pluralization
for sleeve in VALID_SLEEVES:
    VALUE_TO_ENTITY[sleeve.lower()] = "sleeve"

# Sizes - these are numbers so no pluralization
for size in VALID_SIZES:    
    VALUE_TO_ENTITY[str(size)] = "size" 

def find_synonym(query, synonyms):
    query = query.lower()
    # Try longest phrases first to avoid partial matches
    for s in sorted(synonyms, key=lambda x: -len(x)):
        s = s.lower()
        if " " in s:
            # Exact phrase match for multi-word
            if s in query:
                return True
        else:
            # Single word: check if present as a standalone word, but not as part of a longer word/phrase
            if re.search(rf"\b{s}\b", query):
                return True
    return False

def get_df_col_case_insensitive(df, colname):
    """
    Case-insensitive column matching.
    Returns the actual column name if found, None otherwise.
    """
    for col in df.columns:
        if col.lower() == colname.lower():
            return col
    return None  # ← Return None instead of raising KeyError

def split_year_month(df):
    """
    If there is a column named 'month' with values like 'YYYY-MM',
    split it into integer columns 'year' and 'month_num', and drop the original 'month' column.
    """
    if 'month' in df.columns:
        sample = str(df['month'].iloc[0])
        if '-' in sample:
            df[['year', 'month_num']] = df['month'].str.split('-', expand=True).astype(int)
            df = df.drop(columns=['month'])
    return df

def standardize_metric_column_names(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df

    col_map = {}
    for col in df.columns:
        col_lower = col.lower()
        if col_lower in SALE_QTY_SQL_ALIASES:
            col_map[col] = 'SALE_QUANTITY'
        elif col_lower in AMOUNT_SQL_ALIASES:
            col_map[col] = 'TOTAL_AMOUNT'
        # Fuzzy mapping as last resort:
        elif re.search(r'sale.*qty|qty.*sale|quantity.*sold|total.*qty|sale.*quantity|quantity.*sale', col_lower):
            col_map[col] = 'SALE_QUANTITY'
        elif re.search(r'amount|total.*sale|sale.*amount|revenue|value|amt|worth', col_lower):
            col_map[col] = 'TOTAL_AMOUNT'
    if col_map:
        df = df.rename(columns=col_map)
    return df

def build_col_metadata(df, user_tags):
    """
    Returns a mapping from column name to entity/metric info, generic for all entity types.
    """
    mapping = {}
    for col in df.columns:
        col_lower = col.lower()
        entity_type = None
        entity = None
        metric = None
        # Infer entity type and value from user_tags
        for ent_type in ['brand', 'sub_brand', 'store', 'pattern', 'item_division', 'color', 'size', 'sleeve']:
            for ent in user_tags.get(ent_type, []):
                if ent.lower().replace(" ", "_") in col_lower or ent.lower().replace(" ", "") in col_lower:
                    entity_type = ent_type
                    entity = ent
        # Infer metric
        if 'qty' in col_lower or 'quantity' in col_lower:
            metric = 'SALE_QUANTITY'
        elif 'amt' in col_lower or 'amount' in col_lower:
            metric = 'TOTAL_AMOUNT'
        mapping[col] = {'entity_type': entity_type, 'entity': entity, 'metric': metric}
    return mapping

def extract_explicit_date_range(user_query):
    """
    Extracts explicit date ranges from user query.
    Returns dict: {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}, or None if not found.
    Handles formats like: "from 10th October to 30th October 2024", "from 2024-10-10 to 2024-10-30"
    """
    # Accepts: 10th October 2024, October 10, 2024, 2024-10-10, and partials (year only once)
    # Try case: from <Dth Month> to <Dth Month> <YYYY>
    m = re.search(
        r"from\s+(\d{1,2}(?:st|nd|rd|th)?\s+\w+)\s+to\s+(\d{1,2}(?:st|nd|rd|th)?\s+\w+)\s+(\d{4})",
        user_query, re.IGNORECASE)
    if m:
        d1 = parse_natural_date(f"{m.group(1)} {m.group(3)}")
        d2 = parse_natural_date(f"{m.group(2)} {m.group(3)}")
        if d1 and d2:
            return {"start": d1, "end": d2}
    # Try case: from <Month D, YYYY> to <Month D, YYYY>
    m = re.search(
        r"from\s+([a-zA-Z]+\s+\d{1,2},?\s+\d{4})\s+to\s+([a-zA-Z]+\s+\d{1,2},?\s+\d{4})",
        user_query, re.IGNORECASE)
    if m:
        d1 = parse_natural_date(m.group(1))
        d2 = parse_natural_date(m.group(2))
        if d1 and d2:
            return {"start": d1, "end": d2}
    # Try case: from <YYYY-MM-DD> to <YYYY-MM-DD>
    m = re.search(
        r"from\s+(\d{4}-\d{1,2}-\d{1,2})\s+to\s+(\d{4}-\d{1,2}-\d{1,2})",
        user_query, re.IGNORECASE)
    if m:
        d1 = parse_natural_date(m.group(1))
        d2 = parse_natural_date(m.group(2))
        if d1 and d2:
            return {"start": d1, "end": d2}
    # Try case: from <Dth Month YYYY> to <Dth Month YYYY>
    m = re.search(
        r"from\s+(\d{1,2}(?:st|nd|rd|th)?\s+\w+\s+\d{4})\s+to\s+(\d{1,2}(?:st|nd|rd|th)?\s+\w+\s+\d{4})",
        user_query, re.IGNORECASE)
    if m:
        d1 = parse_natural_date(m.group(1))
        d2 = parse_natural_date(m.group(2))
        if d1 and d2:
            return {"start": d1, "end": d2}
    return None


def parse_natural_date(date_str):
    """
    Converts natural date strings (e.g., '10th October 2024', 'October 10 2024', '2024-10-10') to 'YYYY-MM-DD'
    """
    date_str = date_str.strip().replace(',', '')
    # Try YYYY-MM-DD
    m = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})", date_str)
    if m:
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    # Try Dth Month YYYY
    m = re.match(r"(\d{1,2})(?:st|nd|rd|th)?\s+([a-zA-Z]+)\s+(\d{4})", date_str)
    if m:
        day = int(m.group(1))
        month = MONTHS[m.group(2)[:3].lower()]
        year = int(m.group(3))
        return f"{year:04d}-{month:02d}-{day:02d}"
    # Try Month D YYYY
    m = re.match(r"([a-zA-Z]+)\s+(\d{1,2})\s+(\d{4})", date_str)
    if m:
        month = MONTHS[m.group(1)[:3].lower()]
        day = int(m.group(2))
        year = int(m.group(3))
        return f"{year:04d}-{month:02d}-{day:02d}"
    return None

def resolve_entity_key(word, valid_keys):
    for k in valid_keys:
        if word.lower() == k.lower():
            return k
    match = get_best_fuzzy_match(word, valid_keys, threshold=85, short_word_threshold=90)
    if match:
        return match
    match = spell_correct(word, valid_keys)
    if match:
        return match
    return None

def extract_month_years(user_query):
    """
    Extracts explicit month-year pairs from user query.
    Returns list of dicts: [{"month": int, "year": int}]
    """
    matches = re.findall(
        r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|january|february|march|april|may|june|july|august|september|october|november|december)[a-z]*[\s,]*(\d{2,4})",
        user_query, re.IGNORECASE)
    results = []
    for month_str, year in matches:
        year = year.strip()
        if len(year) == 2:
            year = "20" + year
        try:
            results.append({"month": MONTHS[month_str[:3].lower()], "year": int(year)})
        except Exception:
            results.append({"month": MONTHS[month_str[:3].lower()], "year": None})
    return results

def extract_all_festivals_and_years(user_query):
    festival_names = re.findall(r"(diwali|pongal|christmas)", user_query, re.IGNORECASE)
    
    # Handle generic "festival" keyword
    if re.search(r"\bfestival", user_query, re.IGNORECASE) and not festival_names:
        # When user says "festival wise" without specifying, include all
        festival_names = ["diwali", "christmas", "pongal"]
    
    # Fuzzy matching for missed festivals
    words = re.findall(r'\b([a-zA-Z]+)\b', user_query)
    for word in words:
        if word.lower() not in [f.lower() for f in festival_names]:
            match = resolve_entity(word, VALID_FESTIVALS, "festival")
            if match and match.lower() not in [f.lower() for f in festival_names]:
                festival_names.append(match)
    
    year_matches = re.findall(r"\b(\d{2,4})\b", user_query)
    years = ["20" + y if len(y) == 2 else y for y in year_matches]
    
    results = []
    for i, festival in enumerate(festival_names):
        year = years[0] if years else None  # Use first year found for all festivals
        results.append({"festival": festival.lower(), "year": int(year) if year else None})
    
    return results


def validate_attribute_values(values, valid_list):
    """
    Validates extracted attribute values against a list of valid values.
    Handles plural forms and common variations.
    Returns list of only valid values (in their canonical form).
    """
    valid_values = []
    
    for val in values:
        val_lower = val.lower()
        
        # Direct match
        if any(val_lower == valid_val.lower() for valid_val in valid_list):
            # Find the correctly capitalized version
            for valid_val in valid_list:
                if val_lower == valid_val.lower():
                    valid_values.append(valid_val)
                    break
            continue
            
        # Try removing trailing 's' (plural form)
        if val_lower.endswith('s'):
            singular = val_lower[:-1]
            for valid_val in valid_list:
                if singular == valid_val.lower():
                    valid_values.append(valid_val)
                    break
            continue
            
        # Try adding trailing 's' (in case valid list has plurals but user entered singular)
        plural = val_lower + 's'
        for valid_val in valid_list:
            if plural == valid_val.lower():
                valid_values.append(valid_val)
                break
                
    return valid_values

def get_best_fuzzy_match(word, valid_list, threshold=80, short_word_threshold=80):
    """
    Return best fuzzy match from valid_list for word, with heuristics to avoid false positives.
    """
    word = word.lower()
    valid_list_lc = [v.lower() for v in valid_list]

    # Use higher threshold for short words
    thres = short_word_threshold if len(word) < 5 else threshold

    matches = rapidfuzz.process.extract(
        word,
        valid_list_lc,
        scorer=rapidfuzz.fuzz.ratio,
        limit=2
    )

    if matches:
        best, best_score = matches[0][0], matches[0][1]

        # Reject if length difference is large
        if best_score >= thres and abs(len(best) - len(word)) <= 2:

            # Ambiguity: second best is too close → reject
            if len(matches) == 2 and matches[1][1] >= best_score - 5:
                return None

            # Return canonical value from valid_list
            idx = valid_list_lc.index(best)
            return valid_list[idx]

    return None


def spell_correct(word, valid_list):
    # Use global spellchecker for speed
    suggestion = GLOBAL_SPELLCHECKER.correction(word)
    if suggestion and suggestion.lower() in [v.lower() for v in valid_list]:
        idx = [v.lower() for v in valid_list].index(suggestion.lower())
        return valid_list[idx]
    return None

def additional_spell_correct(word):
    corrected = GLOBAL_SPELLCHECKER.correction(word)
    if corrected:
        return corrected
    return word

def metric_spell_correct(word):
    return GLOBAL_SPELLCHECKER.correction(word) or word


def resolve_entity(word, valid_list, entity_type):
    """
    Try to resolve a possibly misspelled or fuzzy entity to its canonical form.
    Returns canonical value or None.
    """
    # 1. Direct match
    for v in valid_list:
        if word.lower() == v.lower():
            return v
    # 2. Fuzzy match
    match = get_best_fuzzy_match(word, valid_list)
    if match:
        return match
    # 3. Spell correct
    match = spell_correct(word, valid_list)
    if match:
        return match
    return None

def resolve_entity_phrase(phrase, valid_list):
    """
    For double-word (or multi-word) values, fuzzy and spell correct as a phrase.
    Returns canonical value or None.
    """
    phrase = phrase.lower()
    
    # 1. Direct match
    for v in valid_list:
        if phrase == v.lower():
            return v
    
    # 2. Fuzzy match
    best = get_best_fuzzy_match(phrase, valid_list)
    if best:
        return best
    
    # 3. Word-by-word spell correct then join and match
    # FIXED: Use GLOBAL_SPELLCHECKER instead of creating new instance
    corrected = " ".join([
        GLOBAL_SPELLCHECKER.correction(w) if GLOBAL_SPELLCHECKER.correction(w) else w 
        for w in phrase.split()
    ])
    for v in valid_list:
        if corrected.lower() == v.lower():
            return v
    
    # 4. Try spell correct on joined phrase
    suggestion = GLOBAL_SPELLCHECKER.correction(phrase.replace(" ", ""))
    if suggestion:
        for v in valid_list:
            if suggestion.lower() == v.replace(" ", "").lower():
                return v
    
    return None

def extract_group_by(user_query):
    group_by_map = {
        "sub brand": "sub_brand",
        "brand": "brand",
        "store": "store",
        "pattern": "pattern",
        "item division": "item_division",
        "color": "color",
        "size": "size",
        "sleeve": "sleeve"
    }
    group_bys = []
    user_query_lc = user_query.lower()
    for entity, tag in group_by_map.items():
        if (
            re.search(rf"\bby\s+{entity}\b", user_query_lc)
            or re.search(rf"\b{entity}[\s\-]?wise\b", user_query_lc)
            or re.search(rf"\bfor each {entity}\b", user_query_lc)
        ):
            group_bys.append(tag)
    if "sub_brand" in group_bys and "brand" in group_bys:
        group_bys.remove("brand")
    return group_bys


def extract_intent(user_query):
    q = user_query.lower()
    
    # Define entity types to check against
    entities = ['brand', 'sub_brand', 'store', 'pattern', 'color', 'size', 'sleeve', 'item_division']
    
    # Common phrases that indicate segmentation/grouping
    grouping_patterns = [
        r"\b{}\s*wise\b",           # brandwise, store wise
        r"\bby\s+{}\b",             # by brand, by store
        r"\bfor\s+each\s+{}\b",     # for each brand, for each store
        r"\bgroup\s+by\s+{}\b",     # group by brand
        r"\b{}\s+breakdown\b",       # brand breakdown
        r"\bfor\s+all\s+{}\b",       # for all brand, for all store
    ]
    
    # Check if any entity with any grouping pattern is found
    for entity in entities:
        # Handle special cases with underscores or spaces
        entity_variants = [entity, entity.replace('_', ' ')]
        
        for variant in entity_variants:
            for pattern in grouping_patterns:
                if re.search(pattern.format(variant), q):
                    return "segmentation"
    
    # Other intents remain the same
    if re.search(r"(compare|vs|versus|trend|increase|decrease|change|growth|drop|spike)", q):
        return "comparison_trend"
    if re.search(r"(should i|recommend|advice|suggest|what should i do)", q):
        return "advice"
    
    return "data_query"

# Optimized version of extract_specific_entities with multiple performance improvements

def extract_specific_entities(user_query):
    """
    OPTIMIZED: Multiple performance improvements:
    1. Pre-computed lookup tables
    2. Early exit strategies  
    3. Reduced fuzzy matching scope
    4. Word-level caching
    5. Smart filtering
    """
    entities = ['sub_brand', 'brand', 'store', 'pattern', 'item_division', 'color', 'size', 'sleeve']
    entity_values = {e: [] for e in entities}
    entity_counts = {}
    entity_presence = {}

    # Initialize presence flags
    for entity in entities:
        entity_presence[f"{entity}_present"] = False
    entity_presence['festival_present'] = False

    query_lower = user_query.lower()

    # OPTIMIZATION 1: Pre-filter query - skip if too long or has suggestion indicators
    if len(user_query.split()) > 50:  # Skip very long queries
        print("[PERF] Skipping long query entity extraction")
        return entity_values, {f"{e}_count": 0 for e in entities}, entity_presence
    
    # OPTIMIZATION 2: Quick suggestion detection - minimal entity extraction
    suggestion_indicators = ['how does', 'what are', 'compare', 'performance', 'vs', 'versus']
    if any(indicator in query_lower for indicator in suggestion_indicators):
        # Do minimal extraction for suggestions
        return extract_minimal_entities(user_query, entities, entity_values, entity_counts, entity_presence)

    # OPTIMIZATION 3: Pre-computed lookup tables (build once, reuse)
    if not hasattr(extract_specific_entities, '_lookup_cache'):
        extract_specific_entities._lookup_cache = build_lookup_cache()
    
    lookup_cache = extract_specific_entities._lookup_cache

    # OPTIMIZATION 4: Word-level processing with early exits
    words = re.findall(r'\b([a-zA-Z0-9\-]+)\b', query_lower)
    found_phrases = set()
    
    # Step 1: Multi-word phrase extraction (OPTIMIZED)
    valid_phrases = {
        'brand': VALID_BRANDS,
        'sub_brand': VALID_SUB_BRANDS,
        'store': VALID_STORES,
        'pattern': VALID_PATTERNS,
        'color': VALID_COLORS,
        'item_division': VALID_ITEM_DIVISIONS
    }
    
    # Only check common multi-word patterns first
    for entity_type, valid_list in valid_phrases.items():
        # Check only 2-word combinations for performance
        for i in range(0, len(words) - 1):
            phrase = " ".join(words[i:i+2])
            if phrase in lookup_cache.get(f'{entity_type}_exact', {}):
                canon = lookup_cache[f'{entity_type}_exact'][phrase]
                if canon not in entity_values[entity_type]:
                    entity_values[entity_type].append(canon)
                    entity_presence[f"{entity_type}_present"] = True
                    found_phrases.update(w.lower() for w in phrase.split())

    # Step 2: Single word processing (HEAVILY OPTIMIZED)
    for word in words:
        if word in found_phrases or len(word) < 2:  # Skip tiny words
            continue
            
        # OPTIMIZATION 5: Direct lookup first (fastest)
        if word in lookup_cache['direct_mapping']:
            entity_type, value = lookup_cache['direct_mapping'][word]
            if value not in entity_values[entity_type]:
                entity_values[entity_type].append(value)
                entity_presence[f"{entity_type}_present"] = True
            continue
        
        # OPTIMIZATION 6: Entity key detection (optimized)
        if word in lookup_cache['entity_keys']:
            entity_type = lookup_cache['entity_keys'][word]
            if entity_type == 'festival':
                entity_presence['festival_present'] = True
            else:
                entity_presence[f"{entity_type}_present"] = True
            continue
        
        # OPTIMIZATION 7: Limited fuzzy matching (only for unmatched words)
        # Only do fuzzy for likely entity words (length > 3, not common words)
        if len(word) > 3 and word not in COMMON_WORDS:
            match_found = fuzzy_match_limited(word, lookup_cache, entity_values, entity_presence)
            if match_found:
                continue

    # Count entities
    for entity in entities:
        entity_counts[f"{entity}_count"] = len(entity_values[entity])

    return entity_values, entity_counts, entity_presence


def build_lookup_cache():
    """Build pre-computed lookup tables for fast entity matching"""
    cache = {
        'direct_mapping': {},  # word -> (entity_type, canonical_value)
        'entity_keys': {},     # word -> entity_type
        'exact_phrases': {},   # phrase -> canonical_value
    }
    
    # Build direct mappings  
   
    for word, entity_type in VALUE_TO_ENTITY.items():
        cache['direct_mapping'][word] = (entity_type, word)  
    
    # Build entity key mappings
    entity_key_map = {
        'pattern': 'pattern', 'patterns': 'pattern',
        'brand': 'brand', 'brands': 'brand',
        'store': 'store', 'stores': 'store',
        'color': 'color', 'colors': 'color', 'colour': 'color', 'colours': 'color',
        'size': 'size', 'sizes': 'size',
        'sleeve': 'sleeve', 'sleeves': 'sleeve',
        'festival': 'festival', 'festivals': 'festival',
        'sub brand': 'sub_brand', 'subbrand': 'sub_brand', 'subbrands': 'sub_brand', 'sub brands': 'sub_brand',
        'item division': 'item_division', 'itemdivision': 'item_division'
    }
    cache['entity_keys'].update(entity_key_map)
    
    # Pre-compute exact phrase lookups for common entities
    valid_lists = {
        'brand': VALID_BRANDS,
        'sub_brand': VALID_SUB_BRANDS,
        'store': VALID_STORES,
        'pattern': VALID_PATTERNS,
        'color': VALID_COLORS,
    }
    
    for entity_type, valid_list in valid_lists.items():
        cache[f'{entity_type}_exact'] = {}
        for item in valid_list:
            cache[f'{entity_type}_exact'][item.lower()] = item
    
    return cache


def extract_minimal_entities(user_query, entities, entity_values, entity_counts, entity_presence):
    """Minimal entity extraction for suggestions - only extract obvious entities"""
    query_lower = user_query.lower()
    
    # Only extract very obvious entities
    obvious_entities = {
        'diwali': ('festival', 'Diwali'),
        'christmas': ('festival', 'Christmas'),
    }
    
    words = query_lower.split()
    for word in words:
        if word in obvious_entities:
            entity_type, value = obvious_entities[word]
            if entity_type != 'festival':
                entity_values[entity_type].append(value)
                entity_presence[f"{entity_type}_present"] = True
            else:
                entity_presence['festival_present'] = True
    
    # Count entities
    for entity in entities:
        entity_counts[f"{entity}_count"] = len(entity_values[entity])
    
    return entity_values, entity_counts, entity_presence


def fuzzy_match_limited(word, lookup_cache, entity_values, entity_presence):
    """Limited fuzzy matching - only for high-confidence matches"""
    # Only check against most common entities to limit scope
    priority_entities = ['brand', 'store', 'sub_brand']
    
    for entity_type in priority_entities:
        exact_dict = lookup_cache.get(f'{entity_type}_exact', {})
        
        # Only do fuzzy if word is close to something in the dict
        for candidate in exact_dict.keys():
            if abs(len(word) - len(candidate)) <= 2:  # Length filter
                # Simple similarity check
                if len(word) >= 4 and (word in candidate or candidate in word):
                    canonical = exact_dict[candidate]
                    if canonical not in entity_values[entity_type]:
                        entity_values[entity_type].append(canonical)
                        entity_presence[f"{entity_type}_present"] = True
                    return True
    
    return False


# Common words to skip fuzzy matching
COMMON_WORDS = {
    'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
    'from', 'up', 'about', 'into', 'through', 'during', 'before', 'after', 'above',
    'below', 'between', 'among', 'this', 'that', 'these', 'those', 'how', 'what',
    'when', 'where', 'why', 'which', 'who', 'whom', 'whose', 'does', 'did', 'will',
    'would', 'could', 'should', 'may', 'might', 'can', 'must', 'shall', 'sales',
    'performance', 'compare', 'analysis', 'total', 'amount', 'quantity'
}

def detect_query_tags(user_query):
    """
    Main entry point for extracting all tags from user query.
    
    PURPOSE: Create consistent cache keys for semantic caching.
    NOT for spoon-feeding Claude - Claude extracts entities itself!
    
    Args:
        user_query (str): User's natural language query
    
    Returns:
        dict: Extracted tags for caching
            - Entity values: {brand: [...], store: [...], etc.}
            - Entity counts: {brand_count: N, store_count: N, etc.}
            - Entity presence: {brand_present: bool, store_present: bool, etc.}
            - festivals: [{festival: str, year: int}]
            - date_range: {start: str, end: str} or None
            - month_years: [{month: int, year: int}]
            - intent: str (segmentation, comparison_trend, etc.)
            - metric: [str] (SALE_QUANTITY, TOTAL_AMOUNT, etc.)
            - group_by: [str] (brand, store, etc.)
            - additionals: {top_n: int, compare: bool, etc.}
    """
    tags = {}
    
    # 1. Extract entities (brands, stores, sub_brands, etc.)
    # This ensures "Park Avenue" and "park avenue" map to same cache key
    entity_values, entity_counts, entity_presence = extract_specific_entities(user_query)
    tags.update(entity_values)
    tags.update(entity_counts)
    tags.update(entity_presence)
    
    # 2. Extract festivals and years
    # Ensures "Diwali 2024" and "diwali 2024" map to same cache key
    festivals = extract_all_festivals_and_years(user_query)
    tags['festivals'] = festivals
    tags['festival_count'] = len(festivals)
    if festivals:
        tags['festival_present'] = True
    
    # 3. Extract explicit date ranges
    # e.g., "from Jan 1 to Jan 31 2024"
    date_range = extract_explicit_date_range(user_query)
    tags['date_range'] = date_range
    tags['daterange_present'] = bool(date_range)
    
    # 4. Extract month-year pairs
    # e.g., "January 2024", "Feb 2023"
    month_years = extract_month_years(user_query)
    tags['month_years'] = month_years
    tags['month_present'] = bool(month_years)
    
    # 5. Extract intent
    # segmentation, comparison_trend, advice, data_query
    intent = extract_intent(user_query)
    tags['intent'] = intent
    
    # 6. Extract metrics
    # SALE_QUANTITY, TOTAL_AMOUNT, percent
    metrics = extract_metrics(user_query)
    tags['metric'] = metrics
    
    # 7. Extract group by fields
    # For queries like "sales by brand", "storewise sales"
    group_by = extract_group_by(user_query)
    tags['group_by'] = group_by
    
    # 8. Extract additionals (analytical modifiers)
    # top_n, compare, trend, percent, etc.
    additionals = extract_additionals(user_query)
    tags['additionals'] = additionals
    
    # 9. Infer temporal granularity (for cache grouping)
    tags['temporal_granularity'] = infer_temporal_granularity(user_query)
    
    return tags


def infer_temporal_granularity(user_query):
    """
    Infer the temporal granularity from query.
    Used for cache key generation.
    """
    q = user_query.lower()
    
    # Check in order of specificity (most specific first)
    if any(term in q for term in ['day', 'daily', 'date-wise', 'datewise']):
        return "day"
    elif any(term in q for term in ['week', 'weekly', 'week-wise', 'weekwise']):
        return "week"
    elif any(term in q for term in ['month', 'monthly', 'month-wise', 'monthwise']):
        return "month"
    elif any(term in q for term in ['quarter', 'quarterly', 'quarter-wise', 'quarterwise', 'q1', 'q2', 'q3', 'q4']):
        return "quarter"
    elif any(term in q for term in ['year', 'yearly', 'annual', 'year-wise', 'yearwise']) or re.search(r'\b20\d{2}\b', q):
        return "year"
    else:
        # Default to year if no temporal indicator
        return "year"

def safe_detect_query_tags(query):
    print("[DEBUG] safe_detect_query_tags input (first 100):", repr(query[:100]))
    if query.strip().lower().startswith("select "):
        print("[ERROR] Attempted tag extraction on SQL. Skipping.")
        return {}
    return detect_query_tags(query)



    # Define metric keyword phrases
qty_keywords = [
        'qty', 'quantity', 'units', 'pieces', 'sold', 'preferred', 'works best', 'sales figure', 'sale figure', 'sale qty', 'sale quantity'
    ]
amt_keywords = [
        'amt', 'amount', 'revenue', 'value', 'total amount', 'sale amount'
    ]

def extract_metrics(user_query):
        metrics = []
        q = user_query.lower()
        
        FUZZY_THRES = 80
        
        def fuzzy_in_query(keyword):
            score = fuzz.partial_ratio(keyword, q)
            return score >= FUZZY_THRES

        # Check for generic sales terms FIRST
        if any(fuzzy_in_query(keyword) for keyword in ['sale', 'sales', 'performance', 
                'perform', 'performed', 'result', 'results']):
            metrics.extend(['SALE_QUANTITY', 'TOTAL_AMOUNT'])
            return metrics  # Return immediately if sales terms found

        # If no sales terms, check specific metrics
        if any(fuzzy_in_query(keyword) for keyword in qty_keywords):
            metrics.append('SALE_QUANTITY')
        if any(fuzzy_in_query(keyword) for keyword in amt_keywords):
            metrics.append('TOTAL_AMOUNT')
        
        # Percentage check
        if any(fuzzy_in_query(keyword) for keyword in ['percent', '%', 'percentage']):
            if 'percent' not in metrics:
                metrics.append('percent')

        return metrics



def extract_additionals(user_query):
    # Spell correct the entire query for additional analytic keywords
    q = " ".join([additional_spell_correct(w) for w in user_query.split()])
    additionals = {}
    m = re.search(r"\btop\s*(\d+)|\bhighest\b|\bbest selling\b|\bsells the most\b|\bmost preferred\b|\blargest\b", q)
    if m and m.group(1):
        additionals['top_n'] = int(m.group(1))
    if re.search(r"\bcompare\b|\bvs\b|\bversus\b|\bcomparison\b", q):
        additionals['compare'] = True
    if re.search(r"\bincrease\b|\bgrowth\b|\brise\b|\bincrement\b|\bspike\b", q):
        additionals['increase'] = True
    if re.search(r"\btrend\b|\bchange\b", q):
        additionals['trend'] = True
    if re.search(r"\bpercent\b|\bpercentage\b|\bshare\b", q):
        additionals['percent'] = True
    if re.search(r"\breturning users\b", q):
        additionals['returning users'] = True
    if re.search(r"\breturning customers\b", q):
        additionals['returning customers'] = True
    if re.search(r"\bsegment\b|\bsegmentation\b", q):
        additionals['segmentation'] = True
    if re.search(r"\bcombination\b|\bcombo\b", q):
        additionals['combination'] = True
    if re.search(r"\baverage\b|\bmean\b|\bavg\b", q):
        additionals['average'] = True
    return additionals


def canonicalize_entity_values(values, valid_list):
    """
    Given user values and a list of canonical values (e.g., from Excel or VALID_SUB_BRANDS),
    map each user value to the closest valid/canonical value (case-insensitive, singular/plural aware).
    Returns a list of canonical values (as found in valid_list).
    """
    canon = []
    for val in values:
        val_lower = val.lower()
        found = None
        # 1. Exact case-insensitive match
        for valid in valid_list:
            if val_lower == valid.lower():
                found = valid
                break
        # 2. If not found, check singular/plural
        if not found:
            if val_lower.endswith('s'):
                singular = val_lower[:-1]
                for valid in valid_list:
                    if singular == valid.lower():
                        found = valid
                        break
            else:
                plural = val_lower + 's'
                for valid in valid_list:
                    if plural == valid.lower():
                        found = valid
                        break
        # 3. If still not found, try title-case match (for accidental all-lower)
        if not found:
            for valid in valid_list:
                if val_lower == valid.lower():
                    found = valid
                    break
        # 4. Add or skip
        if found:
            canon.append(found)
    return canon


def get_festival_date_range(festival, year=None, system_prompt_path="system_prompt.txt"):
    import re
    from datetime import datetime, timedelta

    if not festival:
        return None

    # Read file
    with open(system_prompt_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Find the FESTIVAL_DATES block (allow for '-' or nothing before)
    m = re.search(r"FESTIVAL_DATES:(.*?)(?:\n\s*\n|$)", content, re.DOTALL | re.IGNORECASE)
    if not m:
        return None
    block = m.group(1)

    # Find the festival line (case-insensitive, allow for '- ' or spaces)
    fest_pattern = re.compile(rf"[-\s]*{re.escape(festival.lower())}:\s*([0-9\-,\s]+)", re.IGNORECASE)
    fest_match = None
    for line in block.splitlines():
        match = fest_pattern.match(line.strip().lower())
        if match:
            fest_match = match
            break
    if not fest_match:
        return None

    # Get all dates for this festival
    dates = [d.strip() for d in fest_match.group(1).split(",") if d.strip()]
    if not dates:
        return None

    # If year is given, find the date with that year, else most recent future/past
    chosen_date = None
    if year:
        for d in dates:
            if d.startswith(str(year)):
                chosen_date = d
                break
    if not chosen_date:
        # fallback: find latest date in future, else the last one
        now = datetime.now()
        for d in dates:
            try:
                dt = datetime.strptime(d, "%Y-%m-%d")
                if dt >= now:
                    chosen_date = d
                    break
            except Exception:
                continue
        if not chosen_date:
            chosen_date = dates[-1]

    try:
        dt_fest = datetime.strptime(chosen_date, "%Y-%m-%d")
    except Exception:
        return None

    # Festival window logic
    if festival.strip().lower() == "diwali":
        start = dt_fest - timedelta(days=30)
        end = dt_fest
    else:
        start = dt_fest - timedelta(days=15)
        end = dt_fest
    return {"start": start.strftime("%Y-%m-%d"), "end": end.strftime("%Y-%m-%d")}

def build_cleaned_query(tags, original_query):
    """
    Build a cleaned user query string by REPLACING entities with canonical generic terms
    instead of appending them.
    """
    cleaned = original_query.lower()
    
    # Entity normalization mappings
    entity_mappings = {
        'brand': 'brand',
        'sub_brand': 'sub_brand', 
        'store': 'store',
        'pattern': 'pattern',
        'color': 'color',
        'item_division': 'item_division',
        'sleeve': 'sleeve',
        'size': 'size'
    }
    
    # Replace specific entity values with generic terms
    for entity_type in ['brand', 'sub_brand', 'store', 'pattern', 'color', 'item_division', 'sleeve', 'size']:
        vals = tags.get(entity_type, [])
        if isinstance(vals, str):
            vals = [vals]
        
        for v in vals:
            if v:
                # Replace the actual entity value with generic term
                # Handle both exact and partial matches
                v_lower = v.lower()
                if v_lower in cleaned:
                    cleaned = cleaned.replace(v_lower, entity_mappings[entity_type])
                # Also try with spaces around for better matching
                if f" {v_lower} " in cleaned:
                    cleaned = cleaned.replace(f" {v_lower} ", f" {entity_mappings[entity_type]} ")
                if f" {v_lower}" in cleaned:
                    cleaned = cleaned.replace(f" {v_lower}", f" {entity_mappings[entity_type]}")
                if f"{v_lower} " in cleaned:
                    cleaned = cleaned.replace(f"{v_lower} ", f"{entity_mappings[entity_type]} ")
    
    # Replace festival names with "festival" 
    if tags.get("festivals"):
        for fest in tags["festivals"]:
            if fest["festival"]:
                fest_name = fest["festival"].lower()
                if fest_name in cleaned:
                    cleaned = cleaned.replace(fest_name, "festival")
                # Handle years
                if fest.get("year"):
                    year_str = str(fest["year"])
                    if year_str in cleaned:
                        cleaned = cleaned.replace(year_str, "year")
                    # Handle short years like "24"
                    if year_str.endswith("24") and "24" in cleaned:
                        cleaned = cleaned.replace("24", "year")
    
    # Clean up extra spaces
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    return cleaned

def build_extracted_tags_block(tags):
    """
    Formats canonicalized tags/entities into a block for LLM prompt.
    Excludes metric and additionals.
    """
    lines = ["EXTRACTED_TAGS:"]
    # Entities to include
    entity_keys = [
        'brand', 'sub_brand', 'store', 'pattern', 'color', 'item_division', 'sleeve', 'size'
    ]
    for key in entity_keys:
        vals = tags.get(key, [])
        if vals:
            # Could be a string or list
            if isinstance(vals, str):
                vals = [vals]
            lines.append(f"{key}: {', '.join(map(str, vals))}")

    # Festivals
    if tags.get("festivals"):
        for fest in tags["festivals"]:
            fest_str = f"{fest['festival']}"
            if fest.get("year"):
                fest_str += f", year: {fest['year']}"
            lines.append(f"festival: {fest_str}")

    # Date range
    if tags.get("date_range"):
        dr = tags["date_range"]
        lines.append(f"date_range: {dr['start']} to {dr['end']}")

    # Group by (optional)
    if tags.get("group_by"):
        lines.append(f"group_by: {tags['group_by']}")

    # Month/Year (optional)
    if tags.get("month_years"):
        for my in tags["month_years"]:
            lines.append(f"month_year: {my['month']}-{my['year']}")

    # You may add more if needed, just NOT metric or additionals
    return "\n".join(lines)