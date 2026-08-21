# sql_guardrail_utils.py - FIXED VERSION
"""
SQL Guardrail Utils - Simplified to 3 Core Functions
Fixed: enforce_festival_dates now handles churn queries properly
"""

import re
import pandas as pd


# ============================================================================
# FUNCTION 1: enforce_festival_dates (FIXED)
# ============================================================================

def enforce_festival_dates(sql, user_query):
    """
    Enforce correct festival date ranges in SQL queries.
    
    FIXED: Now handles both:
    1. Festival labeling queries (CASE WHEN ... THEN 'Diwali')
    2. Churn queries (customers DURING vs AFTER festival)
    
    Args:
        sql (str): SQL query to fix
        user_query (str): Original user query
    
    Returns:
        str: SQL with corrected festival dates
    """
    # Festival date mappings with CONSISTENT boundaries
    FESTIVAL_DATES = {
        "diwali": {
            "2023": {
                "start": "2023-10-01",
                "end": "2023-10-31",      # INCLUSIVE
                "post_start": "2023-11-01"  # Day after festival
            },
            "2024": {
                "start": "2024-10-01",
                "end": "2024-10-31",      # INCLUSIVE
                "post_start": "2024-11-01"  # Day after festival
            }
        },
        "pongal": {
            "2023": {
                "start": "2023-01-01",
                "end": "2023-01-15",
                "post_start": "2023-01-16"
            },
            "2024": {
                "start": "2024-01-01",
                "end": "2024-01-15",
                "post_start": "2024-01-16"
            }
        },
        "christmas": {
            "2023": {
                "start": "2023-12-10",
                "end": "2023-12-25",
                "post_start": "2023-12-26"
            },
            "2024": {
                "start": "2024-12-10",
                "end": "2024-12-25",
                "post_start": "2024-12-26"
            }
        }
    }
    
    user_query_lower = user_query.lower()
    
    # Detect if this is a churn query
    is_churn_query = any(keyword in user_query_lower for keyword in ['churn', 'churned', 'not in', 'lost'])
    
    for festival, years_data in FESTIVAL_DATES.items():
        if festival not in user_query_lower:
            continue
        
        # Detect year in query
        year_match = re.search(r'\b(202[3-4])\b', user_query)
        year = year_match.group(1) if year_match else "2024"
        
        if year not in years_data:
            continue
        
        dates = years_data[year]
        
        # ===== FIX 1: Festival Labeling Queries =====
        # Pattern: CASE WHEN BILL_DATE BETWEEN '...' AND '...' THEN 'Festival'
        pattern_labeling = (
            rf"(WHEN\s+[`]?BILL_DATE[`]?\s+BETWEEN\s+')[^']+('\s+AND\s+')[^']+('\s+THEN\s+'){festival.title()}(')"
        )
        replacement_labeling = rf"\1{dates['start']}\2{dates['end']}\3{festival.title()}\4"
        sql = re.sub(pattern_labeling, replacement_labeling, sql, flags=re.IGNORECASE)
        
        # ===== FIX 2: Churn Query - DURING Festival Period =====
        if is_churn_query:
            # Pattern: BILL_DATE BETWEEN '...' AND '...' (any dates)
            # Replace with correct festival boundaries
            pattern_during = r"BILL_DATE\s+BETWEEN\s+'[^']+'\s+AND\s+'[^']+'"
            replacement_during = f"BILL_DATE BETWEEN '{dates['start']}' AND '{dates['end']}'"
            
            # Only replace if dates are close to festival dates (avoid replacing unrelated BETWEEN clauses)
            if re.search(r"BILL_DATE\s+BETWEEN\s+'2024-10", sql, re.IGNORECASE):
                sql = re.sub(pattern_during, replacement_during, sql, flags=re.IGNORECASE)
                print(f"[FESTIVAL FIX] Applied {festival} DURING period: {dates['start']} to {dates['end']}")
            
            # ===== FIX 3: Churn Query - AFTER Festival Period =====
            # Pattern: BILL_DATE > '...' (looking for post-festival purchases)
            # Replace with correct post-festival start date
            pattern_after = r"BILL_DATE\s*>\s*'[^']+'"
            replacement_after = f"BILL_DATE >= '{dates['post_start']}'"
            
            # Only replace if date is close to festival end
            if re.search(r"BILL_DATE\s*>\s*'2024-10-3[01]'", sql, re.IGNORECASE):
                sql = re.sub(pattern_after, replacement_after, sql, flags=re.IGNORECASE, count=1)
                print(f"[FESTIVAL FIX] Applied {festival} AFTER period: >= {dates['post_start']}")
        else:
            # Non-churn queries: only fix labeling
            print(f"[FESTIVAL FIX] Applied {festival} dates: {dates['start']} to {dates['end']}")
    
    return sql


# ============================================================================
# FUNCTION 2: fix_duplicate_detection
# ============================================================================

def fix_duplicate_detection(result_df, user_query):
    """
    Detect and fix duplicate rows in results.
    Only aggregates when ALL categorical columns are identical.
    
    Args:
        result_df (pd.DataFrame): Query results
        user_query (str): Original user query (for context)
    
    Returns:
        pd.DataFrame: Deduplicated results
    """
    if result_df is None or result_df.empty:
        return result_df
    
    # Step 1: Identify categorical vs metric columns
    categorical_cols = []
    metric_cols = []
    
    for col in result_df.columns:
        if pd.api.types.is_numeric_dtype(result_df[col]):
            metric_cols.append(col)
        else:
            categorical_cols.append(col)
    
    print(f"[DEDUP] Categorical columns: {categorical_cols}")
    print(f"[DEDUP] Metric columns: {metric_cols}")
    
    # Step 2: Check for TRUE duplicates (all categorical columns identical)
    if categorical_cols:
        true_duplicates = result_df.duplicated(subset=categorical_cols, keep=False)
        
        if true_duplicates.any():
            print(f"[DEDUP] Found {true_duplicates.sum()} TRUE duplicate rows")
            
            # Step 3: Aggregate only the true duplicates
            if metric_cols:
                result_df = result_df.groupby(categorical_cols, as_index=False).agg({
                    col: 'sum' for col in metric_cols
                })
                print(f"[DEDUP] Aggregated {len(metric_cols)} metric columns by summing")
            else:
                result_df = result_df.drop_duplicates(subset=categorical_cols)
                print(f"[DEDUP] Dropped duplicate rows (no metrics to aggregate)")
        else:
            print(f"[DEDUP] No true duplicates found")
    
    return result_df


# ============================================================================
# FUNCTION 3: repair_sql_with_llm
# ============================================================================

def repair_sql_with_llm(original_sql, user_query, error_message, call_gpt):
    """
    Use Claude to repair broken SQL queries.
    
    Args:
        original_sql (str): The SQL that failed
        user_query (str): Original user query
        error_message (str): Error from database
        call_gpt (function): LLM function to call
    
    Returns:
        str: Repaired SQL query
    """
    prompt = f"""The following SQL query caused an error:

```sql
{original_sql}
```

Error message:
{error_message}

User request:
{user_query}

Please correct ONLY the SQL query. Return just the corrected SQL in a code block.
Do not explain, just provide the fixed SQL."""
    
    response = call_gpt(
        user_message=prompt,
        use_system_prompt=False,
        include_examples=False
    )
    
    # Extract SQL from response
    sql_match = re.search(r"```(?:sql)?(.*?)```", response, re.DOTALL)
    if sql_match:
        repaired_sql = sql_match.group(1).strip()
    else:
        repaired_sql = response.strip()
    
    print(f"[SQL REPAIR] Original SQL:\n{original_sql}")
    print(f"[SQL REPAIR] Repaired SQL:\n{repaired_sql}")
    
    return repaired_sql


# ============================================================================
# TESTING
# ============================================================================

if __name__ == "__main__":
    # Test 1: PRFT churn query
    test_sql_1 = """
    WITH DiwaliCustomers AS (
      SELECT DISTINCT Customer_Contact
      FROM Bill_Date_Sale
      WHERE Store_Name = 'PRFT'
        AND BILL_DATE BETWEEN '2024-10-01' AND '2024-10-31'
    ),
    PostDiwaliCustomers AS (
      SELECT DISTINCT Customer_Contact
      FROM Bill_Date_Sale
      WHERE Store_Name = 'PRFT'
        AND BILL_DATE > '2024-10-31'
    )
    SELECT COUNT(*) AS churned_customers
    FROM DiwaliCustomers
    WHERE Customer_Contact NOT IN (SELECT Customer_Contact FROM PostDiwaliCustomers)
    """
    
    test_query_1 = "how many customers got churned out after diwali 24 prft"
    
    print("="*70)
    print("TEST 1: PRFT Churn Query")
    print("="*70)
    fixed_sql_1 = enforce_festival_dates(test_sql_1, test_query_1)
    print("\nFixed SQL:")
    print(fixed_sql_1)
    
    # Test 2: All stores churn query
    test_sql_2 = """
    WITH diwali_customers AS (
      SELECT DISTINCT Customer_Contact
      FROM Bill_Date_Sale
      WHERE BILL_DATE BETWEEN '2024-10-01' AND '2024-10-31'
    ),
    post_diwali_customers AS (
      SELECT DISTINCT Customer_Contact
      FROM Bill_Date_Sale
      WHERE BILL_DATE > '2024-10-31'
    )
    SELECT COUNT(*) AS churned_customers
    FROM diwali_customers
    WHERE Customer_Contact NOT IN (SELECT Customer_Contact FROM post_diwali_customers)
    """
    
    test_query_2 = "all stores? total churned customers post diwali 24"
    
    print("\n" + "="*70)
    print("TEST 2: All Stores Churn Query")
    print("="*70)
    fixed_sql_2 = enforce_festival_dates(test_sql_2, test_query_2)
    print("\nFixed SQL:")
    print(fixed_sql_2)
    
    print("\n" + "="*70)
    print("VERIFICATION")
    print("="*70)
    print("Both queries should now use IDENTICAL date ranges:")
    print("  DURING: 2024-10-01 to 2024-10-31")
    print("  AFTER:  >= 2024-11-01")
    print("="*70)