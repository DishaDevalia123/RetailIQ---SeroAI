"""
Insight Generation with Comprehensive Business Analysis
Uses Claude Sonnet 4.5 for detailed retail business insights
"""
# explanations_suggestions.py
import pandas as pd
from llm_handler import call_gpt

def classify_query_type(user_query):
    query_lower = user_query.lower()
    
    # Simple fact queries
    if any(word in query_lower for word in ["show", "what is", "what are", "total", "how many", "how much"]):
        return "SIMPLE"
    
    # Analytical queries
    if any(word in query_lower for word in ["how's", "analyze", "why", "what's working", "concerns", "opportunities"]):
        return "ANALYTICAL"
    
    # Comparison queries
    if any(word in query_lower for word in ["vs", "versus", "compare", "between"]):
        return "COMPARISON"
    
    # Default to overview
    return "OVERVIEW"

def llm_dynamic_postprocess(user_query, sql, result_df, user_tags):
    """Generate comprehensive business analysis using complete dataset"""
    
    with open("business_prompt.txt", "r") as f:
        business_context = f.read()
    
    #  Prepare COMPLETE result data
    if result_df is None or result_df.empty:
        result_sample = "No results found"
        row_count = 0
        data_summary = ""
    else:
        row_count = len(result_df)
        
        # Show complete data for reasonable dataset sizes
        if row_count <= 100:
            result_sample = result_df.to_string(index=False, max_rows=None, max_cols=None)
        else:
            # For large datasets, show strategically
            result_sample = f"{result_df.head(30).to_string(index=False)}\n\n... ({row_count - 40} rows omitted) ...\n\n{result_df.tail(10).to_string(index=False)}"
        
        #  Build data summary with validation info
        data_summary = f"\nDATASET INFO:\n- Total rows: {row_count}\n- Columns: {list(result_df.columns)}\n"
        
        # Special handling for temporal data
        if 'month' in result_df.columns:
            months_present = sorted(result_df['month'].unique())
            data_summary += f"- Months in dataset: {months_present}\n"
            data_summary += f"- Month range: {min(months_present)} to {max(months_present)}\n"
            data_summary += f"\n⚠️ CRITICAL: Analyze ALL {len(months_present)} months. Do not stop at month 10.\n"
        
        if 'year' in result_df.columns:
            years = sorted(result_df['year'].unique())
            data_summary += f"- Years in dataset: {years}\n"
    
    # Build prompt
    prompt = f"""You are a business analyst. Match your response depth to the query complexity.

{business_context}

QUERY: {user_query}
{data_summary}

COMPLETE DATA ({row_count} rows):
{result_sample}

CRITICAL: This dataset has {row_count} rows. Your analysis MUST cover all {row_count} data points.
DO NOT truncate your analysis at row 10 or any arbitrary cutoff.

RESPONSE GUIDELINES:

**For SIMPLE queries** (specific facts, single metrics):
- 2-3 sentence direct answer with key numbers
- Brief context (is this good/bad/normal?)
- 2-3 follow-up questions to explore further
- NO recommendations, NO deep analysis

**For OVERVIEW queries** (broad questions like "total sales", "overall performance"):
- Direct answer with key highlights (3-4 sentences)
- 2-3 notable patterns or standouts
- 2-3 follow-up questions
- Light recommendations only if something clearly needs attention

**For ANALYTICAL queries** (comparisons, trends, "how's business", "what's working"):
- Comprehensive 5-section analysis:
  1. Direct Answer
  2. Interpretation (what do numbers mean)
  3. Key Insights (2-4 bullet points)
  4. Light Recommendations (specific actions)
  5. Follow-up Questions

**For COMPARISON queries** ("A vs B"):
- Direct comparison (who's ahead, by how much)
- Key difference (what explains the gap)
- 2-3 follow-up questions

CRITICAL: Use the business context above to interpret results. Don't ask questions about known seasonal patterns (Diwali, Pongal, etc.) - explain them.

CURRENT QUERY TYPE: {classify_query_type(user_query)}

Respond accordingly. Be concise for simple queries, comprehensive for complex ones.
"""
    
    response = call_gpt(
        user_message=prompt,
        use_system_prompt=False,
        include_examples=False
    )
    
    #  Post-generation validation (optional but recommended)
    if result_df is not None and 'month' in result_df.columns and row_count == 12:
        max_month = result_df['month'].max()
        # Check if response mentions later months
        if not any(str(m) in response or month_name in response.lower() 
                   for m in [11, 12] 
                   for month_name in ['november', 'nov', 'december', 'dec']):
            print(f"⚠️ WARNING: Analysis may not cover all 12 months. Max month in data: {max_month}")
    
    return response


def extract_suggestions_from_insight(insight):
    """
    Parse follow-up suggestions from the insight string.
    
    Args:
        insight (str): Full insight text from llm_dynamic_postprocess
    
    Returns:
        list: List of suggestion strings
    """
    if not insight or not isinstance(insight, str):
        return []
    
    suggestions = []
    lines = insight.splitlines()
    in_suggestions = False
    
    for line in lines:
        line_lower = line.strip().lower()
        
        # Detect start of suggestions section
        if "follow-up" in line_lower or "follow up" in line_lower:
            in_suggestions = True
            continue
        
        # Stop at next section or empty line
        if in_suggestions:
            if line.strip() == "" or (":" in line and not line.strip().startswith(("-", "•", "1", "2", "3"))):
                break
            
            # Extract suggestion lines (bullets, numbers, etc.)
            if line.strip().startswith(("-", "•")):
                suggestions.append(line.strip()[1:].strip())
            elif re.match(r'^\d+\.', line.strip()):
                # Numbered list
                suggestions.append(re.sub(r'^\d+\.\s*', '', line.strip()))
    
    return suggestions


def get_entities_from_tags(user_tags):
    """
    Extract entities and their values from user_tags dict for LLM context.
    Helper function if needed for future enhancements.
    
    Args:
        user_tags (dict): Tags extracted from query
    
    Returns:
        dict: Entities with their values
    """
    entities = {}
    for k, v in user_tags.items():
        if k.endswith('_present') and v:
            entity = k.replace('_present', '')
            values = user_tags.get(entity, [])
            if values:
                entities[entity] = values
    return entities


# For backward compatibility with imports
import re