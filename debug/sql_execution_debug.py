"""
SQL Execution Pipeline Debugger
Tests the exact SQL query path used by your LLM system
"""

import pandas as pd
from excel_query_executor import SQLDatabaseConnector
import sys

def print_header(title):
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80)

def print_section(title):
    print(f"\n{'─'*80}")
    print(f"► {title}")
    print(f"{'─'*80}")

# The exact SQL that your LLM generated
TEST_SQL = """
SELECT
  YEAR(BILL_DATE) AS year,
  MONTH(BILL_DATE) AS month,
  SUM(SALE_QUANTITY) AS total_units,
  SUM(Total_Amount) AS total_revenue,
  COUNT(DISTINCT BILL_No) AS transaction_count,
  ROUND(SUM(Total_Amount) / COUNT(DISTINCT BILL_No), 2) AS avg_sale
FROM Bill_Date_Sale
GROUP BY
  YEAR(BILL_DATE),
  MONTH(BILL_DATE)
ORDER BY
  year,
  month;
"""

print_header("SQL EXECUTION PIPELINE DEBUGGER")
print("Testing the exact query path your LLM uses\n")

# Step 1: Test Direct Connection
print_section("Step 1: Test Raw SQL Execution")

try:
    connector = SQLDatabaseConnector()
    print("✓ Connector initialized successfully")
    
    # List all available methods
    methods = [m for m in dir(connector) if not m.startswith('_') and callable(getattr(connector, m))]
    print(f"✓ Available methods: {', '.join(methods)}")
    
except Exception as e:
    print(f"✗ Failed to initialize connector: {e}")
    sys.exit(1)

# Step 2: Test Table Exists
print_section("Step 2: Verify Table Exists")

try:
    tables_result = connector.execute_query("SHOW TABLES LIKE 'Bill_Date_Sale'")
    
    if tables_result:
        print("✓ Table 'Bill_Date_Sale' exists")
        print(f"   Result type: {type(tables_result)}")
        print(f"   Result: {tables_result}")
    else:
        print("✗ Table 'Bill_Date_Sale' NOT found")
        
        # Try to find similar tables
        all_tables = connector.execute_query("SHOW TABLES")
        if all_tables:
            print(f"   All tables result: {all_tables}")
        
        sys.exit(1)
        
except Exception as e:
    print(f"✗ Table check failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Step 3: Test Simple SELECT
print_section("Step 3: Test Simple SELECT")

try:
    simple_sql = "SELECT * FROM Bill_Date_Sale LIMIT 5"
    result = connector.execute_query(simple_sql)
    
    print(f"Result type: {type(result)}")
    print(f"Result value: {result}")
    
    if result:
        print(f"✓ Simple query returned data")
        
        # Check what format it's in
        if isinstance(result, list):
            print(f"   Format: List with {len(result)} items")
            if result:
                print(f"   First item type: {type(result[0])}")
                print(f"   First item: {result[0]}")
            
            # Try to convert to DataFrame
            df = pd.DataFrame(result)
            print(f"\n✓ Converted to DataFrame:")
            print(df.head())
            
        elif isinstance(result, pd.DataFrame):
            print(f"   Format: DataFrame with {len(result)} rows")
            print(result.head())
            
        elif isinstance(result, str):
            print(f"   Format: String (possibly formatted output)")
            print(f"   First 200 chars: {result[:200]}")
            
        else:
            print(f"   Format: {type(result)}")
            print(f"   Value: {result}")
    else:
        print("✗ Simple query returned no data")
        
        # Check row count
        count_result = connector.execute_query("SELECT COUNT(*) as count FROM Bill_Date_Sale")
        print(f"Count result: {count_result}")
        
except Exception as e:
    print(f"✗ Simple query failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Step 4: Test the LLM's Exact Query
print_section("Step 4: Test LLM's Exact SQL Query")

print("Query to execute:")
print(TEST_SQL)

try:
    result = connector.execute_query(TEST_SQL)
    
    print(f"\nResult type: {type(result)}")
    print(f"Result value (first 500 chars): {str(result)[:500]}")
    
    if result:
        print(f"\n✓ Query executed successfully")
        
        # Try to understand the format
        if isinstance(result, pd.DataFrame):
            print(f"   ✓ Returns DataFrame with {len(result)} rows")
            print(f"\nResult preview:\n{result}")
            print(f"\nColumn types:\n{result.dtypes}")
            
        elif isinstance(result, list):
            print(f"   Format: List with {len(result)} items")
            if result:
                df = pd.DataFrame(result)
                print(f"   ✓ Converted to DataFrame: {len(df)} rows")
                print(f"\nResult preview:\n{df}")
        
        elif isinstance(result, str):
            print(f"   ⚠ Returns STRING (formatted output, not data)")
            print(f"   This is the problem - LLM expects DataFrame, gets string")
            print(f"\nString output:\n{result[:1000]}")
            
        elif result is None:
            print(f"   ✗ Returns None")
            
        else:
            print(f"   ⚠ Unexpected type: {type(result)}")
        
    else:
        print("\n✗ Query returned None/empty")
        print("\n🔍 DEBUGGING: Let's break down the query...")
        
        # Test each component
        print("\n1. Testing YEAR/MONTH functions:")
        test1 = connector.execute_query("SELECT YEAR(BILL_DATE) as y, MONTH(BILL_DATE) as m FROM Bill_Date_Sale LIMIT 5")
        print(f"   Result: {test1}")
        
        print("\n2. Testing aggregations:")
        test2 = connector.execute_query("SELECT SUM(SALE_QUANTITY) as total FROM Bill_Date_Sale")
        print(f"   Result: {test2}")
        
        print("\n3. Testing GROUP BY:")
        test3 = connector.execute_query("""
            SELECT YEAR(BILL_DATE) as year, COUNT(*) as count 
            FROM Bill_Date_Sale 
            GROUP BY YEAR(BILL_DATE)
        """)
        print(f"   Result: {test3}")
        
except Exception as e:
    print(f"\n✗ Query execution failed with error:")
    print(f"   {e}")
    import traceback
    print("\nFull traceback:")
    traceback.print_exc()
    sys.exit(1)

# Step 5: Test How LLMSQLGenerator Calls It
print_section("Step 5: Test LLMSQLGenerator Execution Path")

try:
    from llm_sql_generator import LLMSQLGenerator
    
    print("✓ LLMSQLGenerator imported successfully")
    
    # Check what method it uses to execute SQL
    llm_gen = LLMSQLGenerator(system_prompt_path="system_prompt.txt")
    
    # Find the execute method
    if hasattr(llm_gen, 'execute_query'):
        print("✓ Found execute_query method")
        method_name = 'execute_query'
    elif hasattr(llm_gen, 'run_query'):
        print("✓ Found run_query method")
        method_name = 'run_query'
    elif hasattr(llm_gen, 'execute_sql'):
        print("✓ Found execute_sql method")
        method_name = 'execute_sql'
    else:
        print("⚠ Cannot find execution method in LLMSQLGenerator")
        method_name = None
    
    if method_name:
        print(f"\nTesting {method_name} with our SQL...")
        
        # Get the method
        execute_method = getattr(llm_gen, method_name)
        
        # Execute the test SQL
        result = execute_method(TEST_SQL)
        
        print(f"\nResult type: {type(result)}")
        print(f"Result: {result}")
        
        if result is None:
            print("\n❌ PROBLEM FOUND: LLMSQLGenerator execution returns None")
            print("   Even though direct connector.run_sql() works!")
            print("\n   This means the issue is in LLMSQLGenerator's execute method")
        elif isinstance(result, pd.DataFrame):
            if result.empty:
                print("\n❌ PROBLEM FOUND: Returns empty DataFrame")
            else:
                print(f"\n✓ Returns DataFrame with {len(result)} rows")
                print(result)
        else:
            print(f"\n⚠ Unexpected result type: {type(result)}")
            print(f"   Result: {result}")
    
except ImportError as e:
    print(f"✗ Cannot import LLMSQLGenerator: {e}")
except Exception as e:
    print(f"✗ LLMSQLGenerator test failed: {e}")
    import traceback
    traceback.print_exc()

# Step 6: Summary
print_section("DIAGNOSIS SUMMARY")

print("""
If you see:
1. ✓ Simple query works, but LLM query returns None
   → Problem is in the SQL query itself (column names, syntax)

2. ✓ Direct run_sql() works, but LLMSQLGenerator returns None
   → Problem is in how LLMSQLGenerator executes queries

3. ✗ Table is empty (0 rows)
   → Your database has no data

4. ⚠ Column case mismatches
   → SQL is looking for wrong column names
""")

print("\n" + "="*80)
print("Diagnostic complete - review output above")
print("="*80 + "\n")