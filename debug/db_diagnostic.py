"""
Database Diagnostic Script - FIXED FOR execute_query() TUPLE RETURN
Comprehensive testing for SQL connection, schema, and data availability
"""

import pandas as pd
from excel_query_executor import SQLDatabaseConnector
import sys
from datetime import datetime

class DatabaseDiagnostics:
    def __init__(self):
        self.connector = None
        self.issues = []
        self.warnings = []
        
    def print_header(self, title):
        print("\n" + "="*70)
        print(f"  {title}")
        print("="*70)
    
    def print_section(self, title):
        print(f"\n{'─'*70}")
        print(f"► {title}")
        print(f"{'─'*70}")
    
    def execute_sql(self, query):
        """
        Execute SQL and handle the tuple return (DataFrame, error)
        Returns list of dicts for compatibility
        """
        result_df, error = self.connector.execute_query(query)
        
        if error:
            raise Exception(error)
        
        if result_df is None or result_df.empty:
            return []
        
        # Convert DataFrame to list of dicts
        return result_df.to_dict('records')
    
    def run_all_diagnostics(self):
        """Run complete diagnostic suite"""
        print("\n" + "🔍 DATABASE DIAGNOSTICS SUITE" + "\n")
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # Test 1: Database Connection
        if not self.test_connection():
            print("\n❌ CRITICAL: Cannot connect to database. Stopping diagnostics.")
            return False
        
        # Test 2: List All Tables
        self.list_all_tables()
        
        # Test 3: Check Primary Table
        primary_table = self.identify_primary_table()
        
        if not primary_table:
            print("\n❌ CRITICAL: No suitable transaction table found.")
            return False
        
        # Test 4: Analyze Table Schema
        self.analyze_table_schema(primary_table)
        
        # Test 5: Check Data Availability
        self.check_data_availability(primary_table)
        
        # Test 6: Validate Key Columns
        self.validate_key_columns(primary_table)
        
        # Test 7: Test Sample Queries
        self.test_sample_queries(primary_table)
        
        # Test 8: Check Date Ranges
        self.check_date_ranges(primary_table)
        
        # Final Summary
        self.print_summary()
        
        return len(self.issues) == 0
    
    def test_connection(self):
        """Test 1: Database Connection"""
        self.print_section("Test 1: Database Connection")
        
        try:
            self.connector = SQLDatabaseConnector()
            print("✓ Connection established successfully")
            
            # Try to get database name
            try:
                result = self.execute_sql("SELECT DATABASE() as db_name")
                if result:
                    db_name = result[0].get('db_name', 'Unknown')
                    print(f"✓ Connected to database: {db_name}")
            except:
                print("✓ Connected to database (name unknown)")
            
            return True
            
        except Exception as e:
            print(f"✗ Connection failed: {e}")
            self.issues.append(f"Database connection failed: {e}")
            return False
    
    def list_all_tables(self):
        """Test 2: List All Tables"""
        self.print_section("Test 2: Available Tables")
        
        try:
            result = self.execute_sql("SHOW TABLES")
            
            if not result:
                print("✗ No tables found in database")
                self.issues.append("Database has no tables")
                return []
            
            # Extract table names (result is list of dicts)
            tables = [list(row.values())[0] for row in result]
            print(f"✓ Found {len(tables)} table(s):\n")
            
            for i, table in enumerate(tables, 1):
                # Get row count for each table
                try:
                    count_result = self.execute_sql(f"SELECT COUNT(*) as count FROM `{table}`")
                    row_count = count_result[0]['count'] if count_result else 0
                    print(f"   {i}. {table:30s} ({row_count:,} rows)")
                except:
                    print(f"   {i}. {table:30s} (unable to count rows)")
            
            return tables
            
        except Exception as e:
            print(f"✗ Failed to list tables: {e}")
            self.issues.append(f"Cannot list tables: {e}")
            return []
    
    def identify_primary_table(self):
        """Test 3: Identify Primary Transaction Table"""
        self.print_section("Test 3: Identifying Primary Table")
        
        # Common table name patterns
        likely_names = [
            'Bill_Date_Sale',
            'sales',
            'transactions',
            'bill_details',
            'sales_data',
            'retail_sales'
        ]
        
        try:
            all_tables_result = self.execute_sql("SHOW TABLES")
            if not all_tables_result:
                return None
            
            all_tables = [list(row.values())[0] for row in all_tables_result]
            
            # Check for exact matches first
            for name in likely_names:
                if name in all_tables:
                    print(f"✓ Found primary table: {name}")
                    return name
            
            # Check for case-insensitive matches
            for table in all_tables:
                for name in likely_names:
                    if name.lower() == table.lower():
                        print(f"✓ Found primary table (case mismatch): {table}")
                        return table
            
            # If no match, use the first table with most rows
            max_rows = 0
            primary_table = None
            
            for table in all_tables:
                try:
                    count_result = self.execute_sql(f"SELECT COUNT(*) as count FROM `{table}`")
                    row_count = count_result[0]['count'] if count_result else 0
                    
                    if row_count > max_rows:
                        max_rows = row_count
                        primary_table = table
                except:
                    continue
            
            if primary_table:
                print(f"⚠ Using largest table as primary: {primary_table} ({max_rows:,} rows)")
                self.warnings.append(f"Primary table name doesn't match expected patterns. Using: {primary_table}")
                return primary_table
            
            print("✗ Cannot identify primary table")
            self.issues.append("No suitable primary table found")
            return None
            
        except Exception as e:
            print(f"✗ Failed to identify primary table: {e}")
            self.issues.append(f"Cannot identify primary table: {e}")
            return None
    
    def analyze_table_schema(self, table_name):
        """Test 4: Analyze Table Schema"""
        self.print_section(f"Test 4: Schema Analysis for '{table_name}'")
        
        try:
            result = self.execute_sql(f"SHOW COLUMNS FROM `{table_name}`")
            
            if not result:
                print(f"✗ Cannot retrieve schema for {table_name}")
                self.issues.append(f"Cannot read schema for {table_name}")
                return
            
            print(f"✓ Table has {len(result)} columns:\n")
            print(f"{'Column Name':<30} {'Type':<20} {'Null':<8} {'Key':<8}")
            print("─" * 70)
            
            columns = []
            for row in result:
                col_name = row.get('Field', '')
                col_type = row.get('Type', '')
                nullable = row.get('Null', '')
                key = row.get('Key', '')
                
                columns.append(col_name)
                print(f"{col_name:<30} {col_type:<20} {nullable:<8} {key:<8}")
            
            # Check for expected columns
            expected_columns = {
                'date': ['BILL_DATE', 'DATE', 'date', 'bill_date', 'transaction_date'],
                'amount': ['Total_Amount', 'TOTAL_AMOUNT', 'amount', 'sale_amount', 'revenue'],
                'quantity': ['SALE_QUANTITY', 'Sale_Quantity', 'quantity', 'qty'],
                'store': ['Store_Name', 'STORE_NAME', 'store', 'store_name'],
                'brand': ['Brand', 'BRAND', 'brand', 'brand_name']
            }
            
            print("\n\nColumn Validation:")
            for col_type, possible_names in expected_columns.items():
                found = False
                for name in possible_names:
                    if name in columns:
                        print(f"   ✓ {col_type.upper()} column found: {name}")
                        found = True
                        break
                
                if not found:
                    print(f"   ⚠ {col_type.upper()} column NOT found (expected one of: {possible_names[:3]})")
                    self.warnings.append(f"Missing expected {col_type} column")
            
        except Exception as e:
            print(f"✗ Schema analysis failed: {e}")
            self.issues.append(f"Cannot analyze schema: {e}")
    
    def check_data_availability(self, table_name):
        """Test 5: Check Data Availability"""
        self.print_section(f"Test 5: Data Availability in '{table_name}'")
        
        try:
            # Total row count
            count_result = self.execute_sql(f"SELECT COUNT(*) as total_rows FROM `{table_name}`")
            
            if not count_result:
                print(f"✗ Cannot count rows in {table_name}")
                self.issues.append(f"Cannot query {table_name}")
                return
            
            total_rows = count_result[0]['total_rows']
            
            if total_rows == 0:
                print(f"✗ Table '{table_name}' is EMPTY (0 rows)")
                self.issues.append(f"Primary table {table_name} has no data")
                return
            
            print(f"✓ Table has {total_rows:,} rows")
            
            # Sample data
            sample_result = self.execute_sql(f"SELECT * FROM `{table_name}` LIMIT 3")
            
            if sample_result:
                print(f"\n✓ Sample data (first 3 rows):\n")
                # Convert to DataFrame for better display
                df = pd.DataFrame(sample_result)
                print(df.to_string(index=False))
            
        except Exception as e:
            print(f"✗ Data availability check failed: {e}")
            self.issues.append(f"Cannot read data from {table_name}: {e}")
    
    def validate_key_columns(self, table_name):
        """Test 6: Validate Key Columns"""
        self.print_section(f"Test 6: Key Column Validation for '{table_name}'")
        
        # Get column list
        try:
            schema = self.execute_sql(f"SHOW COLUMNS FROM `{table_name}`")
            if not schema:
                return
            
            columns = [row.get('Field', '') for row in schema]
            
            # Find date column
            date_columns = [col for col in columns if 'date' in col.lower() or 'bill' in col.lower()]
            
            if not date_columns:
                print("✗ No date column found")
                self.issues.append("Missing date column")
                return
            
            date_col = date_columns[0]
            print(f"✓ Using date column: {date_col}")
            
            # Test date column
            test_query = f"SELECT MIN({date_col}) as min_date, MAX({date_col}) as max_date, COUNT(DISTINCT {date_col}) as unique_dates FROM `{table_name}`"
            result = self.execute_sql(test_query)
            
            if result:
                min_date = result[0]['min_date']
                max_date = result[0]['max_date']
                unique_dates = result[0]['unique_dates']
                
                print(f"   Date range: {min_date} to {max_date}")
                print(f"   Unique dates: {unique_dates:,}")
            
            # Find amount column
            amount_columns = [col for col in columns if 'amount' in col.lower() or 'total' in col.lower()]
            
            if amount_columns:
                amount_col = amount_columns[0]
                print(f"\n✓ Using amount column: {amount_col}")
                
                # Test amount column
                test_query = f"SELECT MIN({amount_col}) as min_amt, MAX({amount_col}) as max_amt, AVG({amount_col}) as avg_amt FROM `{table_name}`"
                result = self.execute_sql(test_query)
                
                if result:
                    print(f"   Min amount: {result[0]['min_amt']}")
                    print(f"   Max amount: {result[0]['max_amt']}")
                    print(f"   Avg amount: {result[0]['avg_amt']:.2f}")
            else:
                print("\n⚠ No amount column found")
                self.warnings.append("Missing amount column")
            
        except Exception as e:
            print(f"✗ Column validation failed: {e}")
            self.issues.append(f"Cannot validate columns: {e}")
    
    def test_sample_queries(self, table_name):
        """Test 7: Test Sample Queries"""
        self.print_section(f"Test 7: Sample Query Testing for '{table_name}'")
        
        # Get schema
        try:
            schema = self.execute_sql(f"SHOW COLUMNS FROM `{table_name}`")
            if not schema:
                return
            
            columns = [row.get('Field', '') for row in schema]
            
            # Find key columns
            date_col = next((col for col in columns if 'date' in col.lower()), None)
            amount_col = next((col for col in columns if 'amount' in col.lower() or 'total' in col.lower()), None)
            
            if not date_col or not amount_col:
                print("⚠ Cannot run sample queries - missing key columns")
                return
            
            # Test 1: Monthly aggregation (the failing query)
            print("\n1. Testing Monthly Aggregation:")
            try:
                query = f"""
                SELECT 
                    YEAR({date_col}) as year,
                    MONTH({date_col}) as month,
                    SUM({amount_col}) as total_amount,
                    COUNT(*) as transaction_count
                FROM `{table_name}`
                GROUP BY YEAR({date_col}), MONTH({date_col})
                ORDER BY year, month
                LIMIT 5
                """
                
                result = self.execute_sql(query)
                
                if result:
                    print(f"   ✓ Query successful - returned {len(result)} rows")
                    df = pd.DataFrame(result)
                    print(f"\n   Preview:\n{df.to_string(index=False)}")
                else:
                    print("   ✗ Query returned no results")
                    self.issues.append("Monthly aggregation query returns empty results")
                    
            except Exception as e:
                print(f"   ✗ Query failed: {e}")
                self.issues.append(f"Monthly aggregation query error: {e}")
            
            # Test 2: Store-based aggregation (if store column exists)
            store_col = next((col for col in columns if 'store' in col.lower()), None)
            
            if store_col:
                print("\n2. Testing Store Aggregation:")
                try:
                    query = f"""
                    SELECT 
                        {store_col} as store,
                        COUNT(*) as transactions,
                        SUM({amount_col}) as total_sales
                    FROM `{table_name}`
                    GROUP BY {store_col}
                    LIMIT 5
                    """
                    
                    result = self.execute_sql(query)
                    
                    if result:
                        print(f"   ✓ Query successful - found {len(result)} stores")
                        df = pd.DataFrame(result)
                        print(f"\n   Preview:\n{df.to_string(index=False)}")
                    else:
                        print("   ✗ Query returned no results")
                        
                except Exception as e:
                    print(f"   ✗ Query failed: {e}")
            
        except Exception as e:
            print(f"✗ Sample query testing failed: {e}")
    
    def check_date_ranges(self, table_name):
        """Test 8: Check Date Ranges and Coverage"""
        self.print_section(f"Test 8: Date Range Analysis for '{table_name}'")
        
        try:
            schema = self.execute_sql(f"SHOW COLUMNS FROM `{table_name}`")
            if not schema:
                return
            
            columns = [row.get('Field', '') for row in schema]
            date_col = next((col for col in columns if 'date' in col.lower()), None)
            
            if not date_col:
                print("⚠ No date column found")
                return
            
            # Check for data in 2024
            query = f"""
            SELECT 
                YEAR({date_col}) as year,
                COUNT(*) as records
            FROM `{table_name}`
            GROUP BY YEAR({date_col})
            ORDER BY year DESC
            """
            
            result = self.execute_sql(query)
            
            if result:
                print("✓ Data distribution by year:\n")
                df = pd.DataFrame(result)
                for _, row in df.iterrows():
                    print(f"   {row['year']}: {row['records']:,} records")
                
                # Check if 2024 data exists
                years = [row['year'] for row in result]
                if 2024 not in years:
                    print("\n⚠ WARNING: No data found for year 2024")
                    self.warnings.append("No 2024 data - queries for current year will return empty")
                else:
                    print("\n✓ 2024 data is present")
            
        except Exception as e:
            print(f"✗ Date range analysis failed: {e}")
    
    def print_summary(self):
        """Print Final Summary"""
        self.print_header("DIAGNOSTIC SUMMARY")
        
        if not self.issues and not self.warnings:
            print("\n✓ ALL TESTS PASSED - Database is healthy!\n")
            return
        
        if self.issues:
            print(f"\n❌ CRITICAL ISSUES FOUND ({len(self.issues)}):\n")
            for i, issue in enumerate(self.issues, 1):
                print(f"   {i}. {issue}")
        
        if self.warnings:
            print(f"\n⚠️  WARNINGS ({len(self.warnings)}):\n")
            for i, warning in enumerate(self.warnings, 1):
                print(f"   {i}. {warning}")
        
        print("\n" + "─"*70)
        
        if self.issues:
            print("\n🔧 RECOMMENDED ACTIONS:")
            print("   1. Fix critical issues before running queries")
            print("   2. Update system_prompt.txt with correct table/column names")
            print("   3. Verify database contains expected data")
            print("   4. Re-run diagnostics after fixes\n")


if __name__ == "__main__":
    print("""
╔════════════════════════════════════════════════════════════════════╗
║                                                                    ║
║              DATABASE DIAGNOSTIC TOOL v1.2 (FINAL FIX)             ║
║              Handles execute_query() tuple return properly         ║
║                                                                    ║
╚════════════════════════════════════════════════════════════════════╝
    """)
    
    diagnostics = DatabaseDiagnostics()
    success = diagnostics.run_all_diagnostics()
    
    print("\n" + "="*70)
    if success:
        print("✓ Diagnostics completed successfully - Database is ready")
    else:
        print("✗ Diagnostics found issues - Review output above")
    print("="*70 + "\n")
    
    sys.exit(0 if success else 1)