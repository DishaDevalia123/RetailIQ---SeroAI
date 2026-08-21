# intent_conversation.py (MAIN file)

import time
import pandas as pd
import numpy as np
from excel_query_executor import SQLDatabaseConnector
from utils import detect_query_tags, build_cleaned_query, split_year_month, build_col_metadata, standardize_metric_column_names
from llm_sql_generator import LLMSQLGenerator
from graph_generator import display_chart_for_query_result
import json
import re
from llm_handler import call_gpt 
import hashlib
from explanations_suggestions import llm_dynamic_postprocess

_tag_cache = {} 
def detect_query_tags_cached(query_text):
    """
    Cached version of detect_query_tags to avoid re-processing same queries
    """
    # Create a cache key (normalize the text)
    cache_key = re.sub(r'\s+', ' ', query_text.lower().strip())
    
    if cache_key in _tag_cache:
        #print(f"[CACHE HIT] Using cached tags for: {query_text[:50]}...")
        return _tag_cache[cache_key].copy()  # Return copy to avoid mutations
    
    #print(f"[CACHE MISS] Computing tags for: {query_text[:50]}...") 
    tags = detect_query_tags(query_text)
    _tag_cache[cache_key] = tags.copy()
    return tags 



def get_constant_context(user_tags: dict) -> dict:
    entity_column_map = {
        'sub_brand': 'Sub Brand',
        'brand': 'Brand',
        'store': 'Store',
        'pattern': 'Pattern',
        'item_division': 'Item Division',
        'color': 'Color',
        'size': 'Size',
        'sleeve': 'Sleeve'
    }
    context = {}
    for tag_key, col_name in entity_column_map.items():
        values = user_tags.get(tag_key, [])
        if isinstance(values, str):
            values = [values]
        if len(values) == 1 and values[0]:
            context[col_name] = values[0]
    festivals = user_tags.get('festivals', [])
    if len(festivals) == 1 and festivals[0].get('festival'):
        fest = festivals[0]
        fest_str = fest['festival'].capitalize()
        if fest.get('year'):
            fest_str += f" {fest['year']}"
        context['Festival'] = fest_str
    return context

def add_context_columns_if_missing(result_df: pd.DataFrame, user_tags: dict, add_columns_to_table: bool = False) -> pd.DataFrame:
    if not add_columns_to_table:
        return result_df
    context = get_constant_context(user_tags)
    for col_name, value in context.items():
        if col_name not in result_df.columns:
            result_df.insert(len(result_df.columns), col_name, value)
    return result_df
'''
def reorder_result_columns(result_df):
    preferred_order = [
        'Sub Brand', 'Brand', 'Store', 'Pattern', 'Item Division', 'Color', 'Size', 'Sleeve', 'Festival'
    ]
    context_cols = [col for col in preferred_order if col in result_df.columns]
    rest_cols = [col for col in result_df.columns if col not in context_cols]
    return result_df[context_cols + rest_cols]'''

def reorder_result_columns(result_df, group_order=None):
    # Optional: group_order is a list like ['Store_Name', 'Brand', 'year', 'month']
    # Infer known column types
    categorical_cols = ['Store_Name', 'Brand', 'Sub_Brand', 'Pattern', 'Color', 'Item_Division', 'Size', 'Sleeve', 'Festival']
    temporal_cols = ['Month', 'Year', 'month', 'year', 'BILL_DATE', 'DATE', 'date', 'month_year']

    cat_present = [col for col in categorical_cols if col in result_df.columns]
    temp_present = [col for col in temporal_cols if col in result_df.columns]
    rest_cols = [col for col in result_df.columns if col not in cat_present + temp_present]

    metric_first = [col for col in rest_cols if pd.api.types.is_numeric_dtype(result_df[col])]
    metric_rest = [col for col in rest_cols if col not in metric_first]

    # Smart order: use group_order if provided
    if group_order:
        group_order = [col for col in group_order if col in result_df.columns]
        new_order = group_order + [col for col in result_df.columns if col not in group_order]
    else:
        # fallback to standard logic
        new_order = cat_present + temp_present + metric_first + metric_rest

    return result_df[new_order]

def apply_month_mapping_to_results(df, user_tags):
    """
    Quick function to apply month mapping to existing results
    """
    if df is None or df.empty:
        return df
    
    # Check if query involves monthly analysis
    involves_monthly = (
        "monthly" in str(user_tags.get("additionals", {})).lower() or
        "month" in str(user_tags.get("group_by", [])).lower() or
        user_tags.get("temporal_granularity") == "month"
    )
    
    if not involves_monthly:
        return df
    
    # Look for month column
    month_col = None
    for col in df.columns:
        if col.lower() == 'month':
            month_col = col
            break
    
    if month_col is None:
        return df
    
    # Apply month mapping
    month_names = {
        1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun',
        7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'
    }
    
    df[month_col] = df[month_col].map(month_names)
    
    return df

def should_standardize(df, user_tags):
    entity_count = 0
    for ent_type in ['store', 'brand', 'sub_brand', 'pattern', 'item_division', 'color', 'size', 'sleeve']:
        entity_count += len(user_tags.get(ent_type, []))
    return entity_count <= 1

_result_cache = {}  # Global result cache
_semantic_cache = {} 

def normalize_festivals(festivals_list):
    """Normalize festival names and years"""
    if not festivals_list: 
        return []
    
    normalized = []
    for fest in festivals_list:
        if isinstance(fest, dict):
            festival_name = fest.get('festival', '').lower().strip()
            year = fest.get('year', '')
            normalized.append({'festival': festival_name, 'year': str(year)})
        else:
            normalized.append({'festival': str(fest).lower().strip(), 'year': ''})
    
    return sorted(normalized, key=lambda x: (x['festival'], x['year']))

def normalize_date_ranges(date_range):
    """Normalize date ranges to consistent format"""
    if not date_range:
        return None
    
    if isinstance(date_range, dict):
        start = date_range.get('start', '')
        end = date_range.get('end', '')
        return {'start': str(start), 'end': str(end)}
    
    return None

def extract_semantic_components(user_tags, cleaned_query):
    """Extract semantic components that define query meaning"""
    components = {
        # Core intent and metrics
        'intent': user_tags.get('intent', '').lower(),
        'metrics': sorted([m.lower() for m in user_tags.get('metric', [])]),
        
        # Entity filters (sorted for consistency)
        'stores': sorted([s.upper() for s in user_tags.get('store', [])]),
        'brands': sorted([b.lower() for b in user_tags.get('brand', [])]),
        'sub_brands': sorted([sb.lower() for sb in user_tags.get('sub_brand', [])]),
        'patterns': sorted([p.lower() for p in user_tags.get('pattern', [])]),
        'colors': sorted([c.lower() for c in user_tags.get('color', [])]),
        'divisions': sorted([d.lower() for d in user_tags.get('item_division', [])]),
        'sizes': sorted([s.lower() for s in user_tags.get('size', [])]),
        'sleeves': sorted([s.lower() for s in user_tags.get('sleeve', [])]),
        
        # Time-based filters
        'festivals': normalize_festivals(user_tags.get('festivals', [])),
        'month_years': user_tags.get('month_years', []),
        'date_range': normalize_date_ranges(user_tags.get('date_range')),
        
        # Query type indicators
        'is_comparison': 'vs' in cleaned_query.lower() or 'compare' in cleaned_query.lower() or 'versus' in cleaned_query.lower(),
        'grouping': sorted(user_tags.get('group_by', [])) if isinstance(user_tags.get('group_by'), list) else [user_tags.get('group_by', '')] if user_tags.get('group_by') else []
    }
    
    return components

def create_semantic_cache_key(user_tags, cleaned_query):
    """Create cache key based on semantic meaning, not exact wording"""
    
    semantic_components = extract_semantic_components(user_tags, cleaned_query)
    
    # Create deterministic hash from semantic components
    key_string = json.dumps(semantic_components, sort_keys=True, default=str)
    return hashlib.md5(key_string.encode()).hexdigest()

def find_matching_semantic_results(user_tags, cleaned_query):
    """Find cached results that match semantically, including partial matches"""
    
    current_components = extract_semantic_components(user_tags, cleaned_query)
    
    # Look for exact semantic match first
    exact_key = create_semantic_cache_key(user_tags, cleaned_query)
    if exact_key in _result_cache:
        return _result_cache[exact_key], "exact_match"
    
    # Look for partial matches (subset queries)
    for cached_key, cached_result in _result_cache.items():
        if cached_key in _semantic_cache:
            cached_components = _semantic_cache[cached_key]
            
            # Check if current query is a subset of cached query
            if is_query_subset(current_components, cached_components):
                # Filter the cached results to match current query
                filtered_result = filter_cached_results(cached_result, current_components, cached_components)
                if filtered_result:
                    return filtered_result, "subset_match"
    
    return None, "no_match"

def should_skip_deduplication(result_df):
    """Check if this is a multi-level aggregation result"""
    if result_df is None or result_df.empty:
        return False
    
    # Check for GRAND_TOTAL or ALL_STORES indicators
    if 'Store_Name' in result_df.columns:
        if 'GRAND_TOTAL' in result_df['Store_Name'].values:
            print("[DEDUP] Detected multi-level aggregation - skipping dedup")
            return True
    
    return False

def fix_duplicate_detection(result_df, user_tags):
    """
    Fixed deduplication: Only aggregate rows where ALL categorical columns are identical
    """
    if result_df is None or result_df.empty:
        return result_df
    
    # Define temporal/dimensional columns (case-insensitive matching)
    TEMPORAL_DIMS = {'year', 'month', 'quarter', 'week', 'day', 'date'}
    DIMENSION_COLS = {'store_name', 'brand', 'sub_brand', 'pattern', 'color', 
                      'item_division', 'size', 'sleeve', 'festival'}
    
    # 1. Identify categorical vs metric columns (case-insensitive)
    categorical_cols = []
    metric_cols = []
    
    for col in result_df.columns:
        col_lower = col.lower()
        
        # Check if column is temporal or dimensional (case-insensitive)
        if col_lower in TEMPORAL_DIMS or col_lower in DIMENSION_COLS:
            categorical_cols.append(col)
        # Or if it's a string type (already converted)
        elif result_df[col].dtype == 'object' or result_df[col].dtype == 'string':
            categorical_cols.append(col)
        # Otherwise, it's a metric
        else:
            metric_cols.append(col)
    
    print(f"[DEBUG] Categorical columns: {categorical_cols}")
    print(f"[DEBUG] Metric columns: {metric_cols}")
    
    # 2. Check for TRUE duplicates (all categorical columns identical)
    if categorical_cols:
        true_duplicates = result_df.duplicated(subset=categorical_cols, keep=False)
        
        if true_duplicates.any():
            print(f"[DEDUP] Found {true_duplicates.sum()} TRUE duplicate rows")
            
            # 3. Aggregate only if we have duplicates
            if metric_cols:
                result_df = result_df.groupby(categorical_cols, as_index=False).agg({
                    col: 'sum' for col in metric_cols
                })
                print(f"[DEDUP] Aggregated {len(metric_cols)} metric columns")
            else:
                result_df = result_df.drop_duplicates(subset=categorical_cols)
                print(f"[DEDUP] Dropped duplicate rows (no metrics)")
        else:
            print(f"[DEBUG] No true duplicates found")
    
    return result_df

def is_query_subset(current_components, cached_components):
    """Check if current query is a semantic subset of cached query"""
    
    # Must have same intent and metrics
    if (current_components['intent'] != cached_components['intent'] or 
        current_components['metrics'] != cached_components['metrics']):
        return False
    
    # Current query entities must be subset of cached query entities
    entity_fields = ['stores', 'brands', 'sub_brands', 'patterns', 'colors', 'divisions', 'sizes', 'sleeves']
    
    for field in entity_fields:
        current_entities = set(current_components.get(field, []))
        cached_entities = set(cached_components.get(field, []))
        
        # If current has entities, they must be subset of cached
        if current_entities and not current_entities.issubset(cached_entities):
            return False
    
    # Time-based filters must match exactly or current must be subset
    if current_components['festivals']:
        cached_festivals = {(f['festival'], f['year']) for f in cached_components.get('festivals', [])}
        current_festivals = {(f['festival'], f['year']) for f in current_components['festivals']}
        if not current_festivals.issubset(cached_festivals):
            return False
    
    return True

def filter_cached_results(cached_result, current_components, cached_components):
    """Filter cached DataFrame results to match current query constraints"""
    
    if not cached_result or not isinstance(cached_result.get('results'), str):
        return None
    
    # For now, return the cached result as-is
    # TODO: Implement actual DataFrame filtering based on components difference
    # This would require parsing the formatted results back to DataFrame
    
    return cached_result

def cache_semantic_result(user_tags, cleaned_query, result):
    """Cache result with semantic components for future matching"""
    
    semantic_key = create_semantic_cache_key(user_tags, cleaned_query)
    semantic_components = extract_semantic_components(user_tags, cleaned_query)
    
    # Store both result and semantic components
    _result_cache[semantic_key] = result
    _semantic_cache[semantic_key] = semantic_components
    
    print(f"[SEMANTIC CACHE] Stored result for key: {semantic_key[:8]}...")
    
    clean_old_cache_entries()

def clean_old_cache_entries(max_size=100):
    """Keep cache size manageable"""
    if len(_result_cache) > max_size:
        # Remove oldest 20% of entries
        keys_to_remove = list(_result_cache.keys())[:20]
        for key in keys_to_remove:
            if key in _result_cache:
                del _result_cache[key]
            if key in _semantic_cache:
                del _semantic_cache[key]
        print(f"[SEMANTIC CACHE] Cleaned {len(keys_to_remove)} old entries")

def debug_semantic_components(user_tags, cleaned_query, label=""):
    """Debug helper to see what semantic components are extracted"""
    components = extract_semantic_components(user_tags, cleaned_query)
    cache_key = create_semantic_cache_key(user_tags, cleaned_query)
    
    print(f"\n=== SEMANTIC DEBUG {label} ===")
    print(f"Query: {cleaned_query}")
    print(f"Cache Key: {cache_key[:8]}...")
    print(f"Components: {json.dumps(components, indent=2)}")
    print("=" * 30)


def build_conversation_context(conversation_history, current_query):
    """
    Build conversation context from last 2 turns for Claude.
    
    Args:
        conversation_history (list): List of previous conversation turns
        current_query (str): The current user query
    
    Returns:
        str: Formatted context string
    """
    if not conversation_history:
        return ""
    
    # Take last 2 turns
    recent_turns = conversation_history[-2:]
    
    context_parts = []
    
    for i, turn in enumerate(recent_turns, 1):
        user_input = turn.get("user_input", "")
        results = turn.get("results")
        
        # Build turn summary
        turn_summary = f"Previous Query {i}: {user_input}\n"
        
        # Add result summary if available
        if results is not None and isinstance(results, pd.DataFrame) and not results.empty:
            row_count = len(results)
            turn_summary += f"Showed: {row_count} results"
            
            # Extract key entities from results (stores, brands, etc.)
            key_entities = []
            if 'Store_Name' in results.columns:
                stores = results['Store_Name'].unique()
                if len(stores) <= 3:
                    key_entities.append(f"stores: {', '.join(stores)}")
            if 'Brand' in results.columns:
                brands = results['Brand'].unique()
                if len(brands) <= 3:
                    key_entities.append(f"brands: {', '.join(brands)}")
            if 'Sub_Brand' in results.columns:
                sub_brands = results['Sub_Brand'].unique()
                if len(sub_brands) <= 3:
                    key_entities.append(f"sub brands: {', '.join(sub_brands)}")
            
            if key_entities:
                turn_summary += f" for {', '.join(key_entities)}"
        
        context_parts.append(turn_summary)
    
    # Add current query
    context_parts.append(f"\nCurrent Query: {current_query}")
    
    return "\n".join(context_parts)



def route_query_with_tags(user_query, user_tags, conversation_history=None, conversation_context=""):
    """
    Route query to SQL generation with conversation context.
    
    REMOVED PARAMETERS:
        - turn_type (deleted)
    
    NEW PARAMETERS:
        - conversation_context (string): Context from last 2 turns
    """
    t0 = time.time()
    print(f"[TIMING] route_query_with_tags: started")
    
    # Semantic result matching (unchanged)
    cleaned_query = build_cleaned_query(user_tags, user_query)
    debug_semantic_components(user_tags, cleaned_query, "CURRENT QUERY")
    
    cached_result, match_type = find_matching_semantic_results(user_tags, cleaned_query)
    
    if cached_result:
        print(f"[SEMANTIC CACHE {match_type.upper()}] Returning similar result for: {user_query[:50]}...")
        print(f"[TIMING] route_query_with_tags: {time.time()-t0:.2f}s (CACHED)")
        return cached_result
    
    print(f"[SEMANTIC CACHE MISS] Processing new query: {user_query[:50]}...")
    
    # Use LLM with conversation context
    print("Using LLM for query processing...")
    print(f"Extracted tags: {user_tags}")
    
    try:
        
        cleaned_query = build_cleaned_query(user_tags, user_query)
        
        # REMOVED: similar_templates retrieval (now handled in llm_handler)
        # REMOVED: turn_type logic
        # REMOVED: pipeline_query logic
        llm_sql_gen = LLMSQLGenerator(system_prompt_path="system_prompt.txt")
        # Pass conversation_context to enhanced_process_query
        result = llm_sql_gen.enhanced_process_query(
            user_query, 
            conversation_context=conversation_context  # NEW PARAMETER
        )

        # === FIX: Prevent year/month from being treated as metrics ===
        
        if result["results"] is not None and isinstance(result["results"], pd.DataFrame):
            TEMPORAL_COLS = ['year', 'month', 'quarter', 'week', 'day', 'Year', 'Month']
            
            for col in TEMPORAL_COLS:
                if col in result["results"].columns:
                    if pd.api.types.is_numeric_dtype(result["results"][col]):
                        result["results"][col] = result["results"][col].astype(str)
                        print(f"[FIX] Converted '{col}' to string BEFORE dedup")

        # Enhanced duplicate handling (SINGLE CALL ONLY)
        if result["results"] is not None and not should_skip_deduplication(result["results"]):
            result["results"] = fix_duplicate_detection(result["results"], user_tags)

        # Handle clarification requests
        if (isinstance(result["results"], dict) and 
            result["results"].get("clarification_needed")):
            print("\n--- Clarification Needed ---")
            print(result["results"]["clarification_prompt"])
            return {
                "intent": user_tags.get("intent"),
                "action": "clarification_needed",
                "clarification_prompt": result["results"]["clarification_prompt"],
                "suggestions": [],
            }

        # Standardize metrics if needed
        if should_standardize(result["results"], user_tags):
            result["results"] = standardize_metric_column_names(result["results"])

        print("\n--- LLM SQL Generated ---\n", result["sql"])

        # Post-processing
        if result["results"] is not None and isinstance(result["results"], pd.DataFrame) and not result["results"].empty:
            result["results"] = add_context_columns_if_missing(result["results"], user_tags)
            result["results"] = reorder_result_columns(result["results"])
            if result["results"].duplicated().any():
                print("[WARNING] Duplicate rows found. Removing before display.")
                result["results"] = result["results"].drop_duplicates()
            result["results"] = drop_constant_columns(result["results"])

        if result["results"] is not None:
            print("\n--- Query Results (raw DataFrame) ---\n", result["results"])
        else:
            print("\n--- Query Results: None ---")

        # Chart display (NO deduplication here - already done above!)
        if result["results"] is not None and isinstance(result["results"], pd.DataFrame) and not result["results"].empty:
            try:
                # Get HTML instead of opening browser
                chart_html = display_chart_for_query_result(
                    result["results"], 
                    user_query, 
                    user_tags, 
                    show_in_browser=False,  # ← Don't open browser
                    return_html=True         # ← Return HTML string
                )
                result["chart_html"] = chart_html  # Store in result
            except Exception as chart_error:
                print(f"[ERROR] Chart display failed: {chart_error}")
                print("[INFO] Continuing without chart display...")
                result["chart_html"] = None
        
        # Generate insights (with updated call signature)
        insight_result = llm_dynamic_postprocess(
            user_query=user_query,
            sql=result["sql"],
            result_df=result["results"],
            user_tags=user_tags
        )
        
        print("\n--- Answer Explanation, Insights & Suggestions ---\n")
        print(insight_result)
        
        print(f"[TIMING] route_query_with_tags: {time.time()-t0:.2f}s (COMPLETE)")
        
        suggestions = extract_suggestions_from_insight(insight_result)
        
        # SIMPLIFIED conversation history structure
        final_result = {
            "intent": user_tags.get("intent"),
            "action": "run_sql",
            "sql": result.get("sql"),
            "results": result.get("results"),
            "insight": insight_result,
            "suggestions": suggestions,
            # REMOVED: turn_type, pipeline_query, detailed_intent
        }
        
        # Cache result
        cache_semantic_result(user_tags, cleaned_query, final_result)
        
        return final_result
    
    except Exception as e:
        print(f"Error in query processing: {e}")
        print(f"[TIMING] route_query_with_tags: {time.time()-t0:.2f}s (ERROR)")
        return {"intent": "fallback", "action": "error", "error": str(e)}

def extract_best_query_from_llm(llm_response, user_input):
    try:
        llm_json = json.loads(llm_response)
        if llm_json.get("clarification_needed"):
            return None, llm_json
        return llm_json.get("full_query", user_input), llm_json
    except Exception:
        match = re.search(r"```(?:sql)?\s*([\s\S]+?)```", llm_response)
        if match:
            extracted = match.group(1).strip()
            return user_input, None
        return user_input, None
    
def drop_constant_columns(df):
    if df is None or df.empty or len(df) < 2:
        return df
    # Drop columns where all values are the same (ignoring NaNs)
    return df.loc[:, (df.nunique(dropna=False) > 1).values]

import pandas as pd

def extract_suggestions_from_insight(insight):
    """
    Parse suggestions from the insight string returned by llm_dynamic_postprocess.
    Returns a list of suggestions (strings)
    """
    if not insight or not isinstance(insight, str):
        return []
    lines = insight.splitlines()
    suggestions = []
    in_suggestions = False
    for line in lines:
        if line.strip().lower().startswith("suggestions"):
            in_suggestions = True
            continue
        if in_suggestions:
            # End at next section or end of block
            if line.strip() == "" or (":" in line and not line.strip().startswith("-")):
                break
            if line.strip().startswith("-"):
                # Remove "- " and strip
                suggestions.append(line.strip()[2:].strip())
    return suggestions

def llm_conversational_loop():
    """
    SIMPLIFIED conversation loop - leverages Claude's native capabilities.
    
    REMOVED:
        - All turn_type detection logic
        - All query reframing logic
        - pipeline_query variable
    """
    
    conversation_history = []
    
    while True:
        user_input = input("\nYou: ").strip()
        if user_input.lower() in {"quit", "exit"}:
            break
        
        # Build conversation context from last 2 turns
        conversation_context = build_conversation_context(conversation_history, user_input)
        
        # Extract tags (cached for performance)
        user_tags = detect_query_tags_cached(user_input)
        
        # Route query with conversation context
        response = route_query_with_tags(
            user_query=user_input,
            user_tags=user_tags,
            conversation_history=conversation_history,
            conversation_context=conversation_context  # NEW PARAMETER
        )
        
        # Display results
        if response.get("action") == "run_sql":
            results = response.get("results")
            if results is not None and isinstance(results, pd.DataFrame):
                print("\n--- Results ---")
                print(results.to_string(index=False))
            
            print("\n--- Insight ---")
            print(response.get("insight", "No insight available"))
            
            if response.get("suggestions"):
                print("\n--- Suggestions ---")
                for i, sug in enumerate(response["suggestions"], 1):
                    print(f"{i}. {sug}")
        
        elif response.get("action") == "clarification_needed":
            print("\n--- Clarification Needed ---")
            print(response.get("clarification_prompt"))
            continue
        
        elif response.get("action") == "error":
            print("\n--- Error ---")
            print(response.get("error"))
            continue
        
        # SIMPLIFIED: Save to history (removed turn_type, pipeline_query, detailed_intent)
        conversation_history.append({
            "user_input": user_input,
            "sql": response.get("sql"),
            "results": response.get("results"),
            "insight": response.get("insight"),
            "suggestions": response.get("suggestions", [])
        })

if __name__ == "__main__":
    llm_conversational_loop()