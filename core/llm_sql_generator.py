"""
LLM SQL Generator - COMPLETE FIX
Fixed: ORDER BY logic, method signatures, CTE detection
"""

import pandas as pd
import re
from llm_handler import call_gpt
from excel_query_executor import SQLDatabaseConnector
from utils import detect_query_tags, build_extracted_tags_block, build_cleaned_query
from sql_guardrail_utils import enforce_festival_dates, fix_duplicate_detection, repair_sql_with_llm

class LLMSQLGenerator:
    def __init__(self, system_prompt_path="system_prompt.txt"):
        """Initialize with proper connector"""
        self.connector = SQLDatabaseConnector()
        self.system_prompt = self._load_system_prompt(system_prompt_path)
        self.sql_examples = self._load_sql_examples()
    
    def retrieve_similar_templates(self, user_query, top_k=3, user_tags=None):
        """DEPRECATED: Returns empty list for backward compatibility."""
        return []
    
    def execute_sql(self, sql):
        """
        Execute SQL and return (DataFrame, error) tuple
        NO MONKEY PATCH - Just call connector directly
        """
        try:
            result_df, error = self.connector.execute_query(sql)
            return result_df, error
        except Exception as e:
            print(f"[ERROR] Exception in execute_sql: {e}")
            return None, str(e)
    
    def safe_add_order_by(self, sql):
        """
        Safely add ORDER BY clause only when it makes semantic sense.
        
        CRITICAL RULES:
        1. Never add ORDER BY if column isn't in final SELECT
        2. For CTEs, order by position (safe fallback)
        3. Only reference columns that exist in scope
        """
        if "order by" in sql.lower():
            return sql  # Already has ORDER BY
        
        # Detect if query uses CTEs (WITH clause)
        has_cte = bool(re.search(r'\bWITH\b', sql, re.IGNORECASE))
        
        if has_cte:
            # CTEs: always use position-based ORDER BY (safest)
            print("[ORDER BY] Detected CTE - using ORDER BY 1")
            return sql.rstrip().rstrip(';') + " ORDER BY 1;"
        
        # Extract final SELECT clause (for non-CTE queries)
        final_select_match = re.search(
            r'SELECT\s+(.*?)\s+FROM', 
            sql, 
            re.IGNORECASE | re.DOTALL
        )
        
        if not final_select_match:
            print("[ORDER BY] Could not parse SELECT - using ORDER BY 1")
            return sql.rstrip().rstrip(';') + " ORDER BY 1;"
        
        final_select = final_select_match.group(1).lower()
        
        # Check what columns are available in final SELECT
        has_year_month = ('year' in final_select and 'month' in final_select)
        has_bill_date = 'bill_date' in final_select
        
        # Decision tree for ORDER BY
        if has_year_month:
            print("[ORDER BY] Detected year/month - using chronological order")
            return sql.rstrip().rstrip(';') + " ORDER BY year, MONTH(BILL_DATE);"  # Use MONTH() not month string
        
        elif has_bill_date:
            print("[ORDER BY] Detected BILL_DATE - using date order")
            return sql.rstrip().rstrip(';') + " ORDER BY BILL_DATE;"
        
        else:
            print("[ORDER BY] Using safe fallback - ORDER BY 1")
            return sql.rstrip().rstrip(';') + " ORDER BY 1;"
    
    def guarded_execute_sql(self, sql, user_query):
        """
        FIXED: Proper error handling that always returns results.
        
        Returns: (result_df, final_sql, error_message)
        """
        # Step 1: Apply festival date enforcement
        sql = enforce_festival_dates(sql, user_query)
        
        # Step 2: Try execute
        result_df, error = self.execute_sql(sql)
        
        # Step 3: Handle empty results (NOT AN ERROR!)
        if result_df is not None and isinstance(result_df, pd.DataFrame) and result_df.empty:
            print(f"[INFO] Query returned 0 rows. Checking database...")
            
            # Diagnose why no results
            test_sql = "SELECT DISTINCT Store_Name FROM Bill_Date_Sale LIMIT 10"
            test_df, _ = self.execute_sql(test_sql)
            
            if test_df is not None and not test_df.empty:
                available_stores = test_df['Store_Name'].tolist()
                print(f"[INFO] Available stores: {available_stores}")
                
                # Check if query filters by store
                if 'Store_Name' in sql:
                    store_match = re.search(r"Store_Name\s*=\s*'([^']+)'", sql, re.IGNORECASE)
                    if store_match:
                        queried_store = store_match.group(1)
                        print(f"[INFO] Query looking for: '{queried_store}'")
                        
                        if queried_store not in available_stores:
                            print(f"[ERROR] Store '{queried_store}' not found in database!")
                            print(f"[HINT] Available stores are: {available_stores}")
                            
                            # Try to find case-insensitive match
                            matching_store = None
                            for store in available_stores:
                                if store.upper() == queried_store.upper():
                                    matching_store = store
                                    break
                            
                            if matching_store:
                                print(f"[FIX] Found matching store with different case: '{matching_store}'")
                                sql = re.sub(
                                    rf"Store_Name\s*=\s*'{queried_store}'",
                                    f"Store_Name = '{matching_store}'",
                                    sql,
                                    flags=re.IGNORECASE
                                )
                                print(f"[FIX] Retrying with corrected store name...")
                                result_df, error = self.execute_sql(sql)
            
            # If still empty after fix attempt, return empty DataFrame (valid result!)
            if result_df is not None and result_df.empty:
                print(f"[INFO] Query is correct but returned 0 rows (no data matches filters)")
                return result_df, sql, None
        
        # Step 4: If execution succeeded, apply deduplication
        if not error and result_df is not None:
            result_df = fix_duplicate_detection(result_df, user_query)
            return result_df, sql, None
        
        # Step 5: If failed, repair with LLM once
        if error:
            print(f"[SQL REPAIR] Initial execution failed: {error}")
            repaired_sql = repair_sql_with_llm(sql, user_query, error, call_gpt)
            
            # Retry with repaired SQL
            result_df, error = self.execute_sql(repaired_sql)
            
            if not error and result_df is not None:
                result_df = fix_duplicate_detection(result_df, user_query)
                return result_df, repaired_sql, None
            
            print(f"[SQL REPAIR] Repair attempt failed: {error}")
            return None, repaired_sql, error
        
        return None, sql, "Unknown error occurred"
    
    def validate_sql_completeness(self, sql):
        """Validate SQL is complete and has table name."""
        if not sql or not sql.strip():
            return False, "SQL is empty"
        
        sql_upper = sql.upper()
        
        if 'SELECT' not in sql_upper:
            return False, "SQL missing SELECT clause"
        
        if 'FROM' not in sql_upper:
            return False, "SQL missing FROM clause"
        
        # Check FROM is not empty
        from_match = re.search(r'FROM\s*([;\s]|$)', sql, re.IGNORECASE)
        if from_match:
            return False, "SQL has FROM clause but missing table name"
        
        # Check table name exists
        table_match = re.search(r'FROM\s+([a-zA-Z_][a-zA-Z0-9_]*)', sql, re.IGNORECASE)
        if not table_match:
            return False, "SQL has FROM clause but no valid table name found"
        
        table_name = table_match.group(1)
        
        if table_name.lower() != 'bill_date_sale':
            return False, f"SQL uses wrong table name '{table_name}'. Must use 'Bill_Date_Sale'"
        
        return True, None
    
    def validate_column_aliases(self, sql):
        """Validate that SQL doesn't have problematic column aliases."""
        select_match = re.search(r'SELECT\s+(.*?)\s+FROM', sql, re.IGNORECASE | re.DOTALL)
        if not select_match:
            return True, None
        
        select_clause = select_match.group(1)
        aliases = re.findall(r'\bAS\s+([a-zA-Z_][a-zA-Z0-9_]*)', select_clause, re.IGNORECASE)
        
        # Check duplicates
        aliases_lower = [a.lower() for a in aliases]
        if len(aliases_lower) != len(set(aliases_lower)):
            duplicates = [a for a in set(aliases_lower) if aliases_lower.count(a) > 1]
            return False, f"Duplicate column aliases detected: {duplicates}"
        
        # Check problematic patterns
        problematic_patterns = ['Total_Amount', 'SALE_QUANTITY', 'Discount_Amount', 
                                'BILL_No', 'Customer_Contact', 'Customer_Name']
        
        for alias in aliases:
            for pattern in problematic_patterns:
                if pattern.lower() in alias.lower() and alias.lower() != pattern.lower():
                    return False, f"Alias '{alias}' contains column name '{pattern}'"
        
        return True, None
    
    def enhanced_process_query(self, user_query, user_clarification_input=None, 
                           conversation_context=""):
        """
        FIXED: Single enhanced_process_query method with proper error handling.
        """
        combined_query = f"{user_query} {user_clarification_input}" if user_clarification_input else user_query
        
        tags = detect_query_tags(combined_query)
        tags_block = build_extracted_tags_block(tags)
        cleaned_query = build_cleaned_query(tags, combined_query)
        
        # Build enhanced prompt
        prompt_parts = []
        
        if conversation_context:
            prompt_parts.append("=== CONVERSATION CONTEXT ===")
            prompt_parts.append(conversation_context)
            prompt_parts.append("")
        
        if tags_block:
            prompt_parts.append("=== EXTRACTED ENTITIES ===")
            prompt_parts.append(tags_block)
            prompt_parts.append("")
        
        prompt_parts.append("=== TASK ===")
        prompt_parts.append(f"User Query: {combined_query}")
        prompt_parts.append("")
        prompt_parts.append("Generate a SQL query to answer the above request.")
        prompt_parts.append("")
        prompt_parts.append("CRITICAL REQUIREMENTS:")
        prompt_parts.append("1. Table name: Bill_Date_Sale (this is the ONLY table)")
        prompt_parts.append("2. Use proper column aliases: total_revenue, total_units, avg_sale")
        prompt_parts.append("3. Return ONLY the SQL query in a code block")
        prompt_parts.append("4. For time queries: YEAR(BILL_DATE) AS year, DATE_FORMAT(BILL_DATE, '%b') AS month")
        prompt_parts.append("5. GROUP BY all non-aggregated columns")
        prompt_parts.append("6. Do NOT add ORDER BY - it will be added automatically")
        prompt_parts.append("")
        prompt_parts.append("Return format:")
        prompt_parts.append("```sql")
        prompt_parts.append("SELECT ... FROM Bill_Date_Sale WHERE ... GROUP BY ...;")
        prompt_parts.append("```")
        
        prompt = "\n".join(prompt_parts)
        
        # Call LLM
        llm_response = call_gpt(
            user_message=prompt,
            context="",
            use_system_prompt=True,
            include_examples=True
        )
        
        # Extract SQL
        sql = self.extract_sql_from_response(llm_response)

        # POST-PROCESS SQL
        if sql:
            # 1) Ensure month is returned as short name
            sql = re.sub(
                r"MONTH\s*\(\s*BILL_DATE\s*\)",
                "DATE_FORMAT(BILL_DATE, '%b')",
                sql,
                flags=re.IGNORECASE
            )
            sql = re.sub(
                r"EXTRACT\s*\(\s*MONTH\s*FROM\s*BILL_DATE\s*\)",
                "DATE_FORMAT(BILL_DATE, '%b')",
                sql,
                flags=re.IGNORECASE
            )

            # 2) Remove unwanted auto-injected metrics
            sql = re.sub(
                r",\s*COUNT\s*\(\s*\*\s*\)\s+AS\s+transaction_count\b",
                "",
                sql,
                flags=re.IGNORECASE
            )
            sql = re.sub(
                r",\s*COUNT\s*\(\s*DISTINCT\s+[A-Za-z0-9_.]+\s*\)\s+AS\s+\w*count\b",
                "",
                sql,
                flags=re.IGNORECASE
            )

            # 3) Add ORDER BY safely
            sql = self.safe_add_order_by(sql)
        
        if not sql:
            return {
                "sql": None,
                "results": None,
                "clarifications": [],
                "llm_response": llm_response,
                "error": "Could not extract SQL from LLM response",
                "suggestions": []
            }
        
        # Validate completeness
        is_complete, completeness_error = self.validate_sql_completeness(sql)
        if not is_complete:
            print(f"[SQL VALIDATION ERROR] {completeness_error}")
            print(f"[SQL VALIDATION] Attempting to repair incomplete SQL...")
            
            repair_prompt = f"""The following SQL is incomplete:
{sql}

Error: {completeness_error}

Please rewrite the SQL query following these rules:
1. Use table name: Bill_Date_Sale
2. Include all required clauses (SELECT ... FROM Bill_Date_Sale ...)
3. Use proper column aliases: total_revenue, total_units, avg_sale
4. Do NOT add ORDER BY clause
5. Make it a complete, executable SQL query

Return ONLY the corrected SQL query in a code block."""

            repaired_response = call_gpt(
                user_message=repair_prompt,
                use_system_prompt=True
            )
            
            sql = self.extract_sql_from_response(repaired_response)
            print(f"[SQL VALIDATION] Repaired SQL:\n{sql}")
            
            # Apply same post-processing
            if sql:
                sql = re.sub(r"MONTH\s*\(\s*BILL_DATE\s*\)", "DATE_FORMAT(BILL_DATE, '%b')", sql, flags=re.IGNORECASE)
                sql = re.sub(r"EXTRACT\s*\(\s*MONTH\s*FROM\s*BILL_DATE\s*\)", "DATE_FORMAT(BILL_DATE, '%b')", sql, flags=re.IGNORECASE)
                sql = re.sub(r",\s*COUNT\s*\(\s*\*\s*\)\s+AS\s+transaction_count\b", "", sql, flags=re.IGNORECASE)
                sql = re.sub(r",\s*COUNT\s*\(\s*DISTINCT\s+[A-Za-z0-9_.]+\s*\)\s+AS\s+\w*count\b", "", sql, flags=re.IGNORECASE)
                sql = self.safe_add_order_by(sql)
        
        # Validate aliases
        is_valid, validation_error = self.validate_column_aliases(sql)
        if not is_valid:
            print(f"[SQL VALIDATION ERROR] {validation_error}")
            print(f"[SQL VALIDATION] Attempting to repair SQL aliases...")
            
            repair_prompt = f"""The following SQL has an alias problem:
{sql}

Error: {validation_error}

Please rewrite the SQL with proper column aliases:
- Use descriptive names: total_revenue, avg_sale, transaction_count
- Never include the original column name in the alias
- Make all aliases unique and lowercase with underscores
- Do NOT add ORDER BY clause

Return ONLY the corrected SQL query."""

            repaired_response = call_gpt(
                user_message=repair_prompt,
                use_system_prompt=True
            )
            
            sql = self.extract_sql_from_response(repaired_response)
            print(f"[SQL VALIDATION] Repaired SQL:\n{sql}")
            
            # Apply same post-processing
            if sql:
                sql = re.sub(r"MONTH\s*\(\s*BILL_DATE\s*\)", "DATE_FORMAT(BILL_DATE, '%b')", sql, flags=re.IGNORECASE)
                sql = re.sub(r"EXTRACT\s*\(\s*MONTH\s*FROM\s*BILL_DATE\s*\)", "DATE_FORMAT(BILL_DATE, '%b')", sql, flags=re.IGNORECASE)
                sql = re.sub(r",\s*COUNT\s*\(\s*\*\s*\)\s+AS\s+transaction_count\b", "", sql, flags=re.IGNORECASE)
                sql = re.sub(r",\s*COUNT\s*\(\s*DISTINCT\s+[A-Za-z0-9_.]+\s*\)\s+AS\s+\w*count\b", "", sql, flags=re.IGNORECASE)
                sql = self.safe_add_order_by(sql)
        
        # Execute with guardrails
        results, fixed_sql, error = self.guarded_execute_sql(sql, combined_query)
        
        # Log result status
        if results is not None and isinstance(results, pd.DataFrame):
            if results.empty:
                print(f"[SUCCESS] Query executed successfully but returned 0 rows")
            else:
                print(f"[SUCCESS] Query returned {len(results)} rows")
        elif error:
            print(f"[ERROR] Query failed: {error}")
        
        return {
            "sql": fixed_sql if fixed_sql else sql,
            "results": results,
            "clarifications": [],
            "llm_response": llm_response,
            "error": error,
            "suggestions": []
        }
    
    def extract_sql_from_response(self, llm_response):
        """Extract SQL from LLM response."""
        # Try code block
        sql_match = re.search(r"```(?:sql)?(.*?)```", llm_response, re.DOTALL)
        if sql_match:
            return sql_match.group(1).strip()
        
        # Try inline SELECT
        select_match = re.search(r"(SELECT[\s\S]*?FROM[\s\S]*?;?)", llm_response, re.IGNORECASE)
        if select_match:
            sql = select_match.group(1).strip()
            if not sql.endswith(';'):
                sql += ';'
            return sql
        
        return None
    
    def _load_system_prompt(self, path):
        """Load system prompt from file"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        except:
            return "You are a SQL query generator."
    
    def _load_sql_examples(self):
        """Load SQL examples"""
        return []


if __name__ == "__main__":
    generator = LLMSQLGenerator()
    
    test_sql = """
    WITH diwali_customers AS (
      SELECT DISTINCT Customer_Contact
      FROM Bill_Date_Sale
      WHERE Store_Name = 'PRFT'
        AND BILL_DATE BETWEEN '2024-10-01' AND '2024-10-31'
    ),
    post_diwali_customers AS (
      SELECT DISTINCT Customer_Contact
      FROM Bill_Date_Sale
      WHERE Store_Name = 'PRFT'
        AND BILL_DATE > '2024-10-31'
    )
    SELECT COUNT(*) AS churned_customers
    FROM diwali_customers dc
    LEFT JOIN post_diwali_customers pc ON dc.Customer_Contact = pc.Customer_Contact
    WHERE pc.Customer_Contact IS NULL
    """
    
    print("Testing ORDER BY fix...")
    fixed_sql = generator.safe_add_order_by(test_sql)
    print("\nFixed SQL:")
    print(fixed_sql)
    
    print("\n" + "="*50)
    print("Expected: ORDER BY 1 (safe for CTEs)")
    print("="*50)