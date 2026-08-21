# excel_query_executor.py - FINAL FIXED VERSION
import pandas as pd
import mysql.connector
from mysql.connector import Error

class SQLDatabaseConnector:
    def __init__(self, host="localhost", user="root", password="root", database="RetailDB"):
        """Initialize SQL database connector."""
        self.connection_params = {
            "host": host,
            "user": user,
            "password": password,
            "database": database
        }
        self.connection = None
        self.connect_to_database()
    
    def connect_to_database(self):
        """Connect to MySQL database"""
        try:
            self.connection = mysql.connector.connect(**self.connection_params)
            if self.connection.is_connected():
                print(f"Successfully connected to MySQL database: {self.connection_params['database']}")
                
                # Test query to verify schema
                cursor = self.connection.cursor(dictionary=True)
                cursor.execute("SHOW COLUMNS FROM Bill_Date_Sale")
                columns = cursor.fetchall()
                
                # Check critical columns
                column_names = [col['Field'] for col in columns]
                
                if 'Total_Amount' in column_names:
                    cursor.execute("SELECT Total_Amount FROM Bill_Date_Sale LIMIT 3")
                    sample_data = cursor.fetchall()
                    print("Total_Amount exists, sample values:", [row['Total_Amount'] for row in sample_data])
                else:
                    print("WARNING: 'Total_Amount' column not found!")
                    similar_cols = [col['Field'] for col in columns if 'amount' in col['Field'].lower() or 'sale' in col['Field'].lower()]
                    if similar_cols:
                        print("  Similar columns found:", similar_cols)
                
                if 'BILL_DATE' in column_names:
                    cursor.execute("SELECT BILL_DATE FROM Bill_Date_Sale LIMIT 3")
                    sample_data = cursor.fetchall()
                    print("BILL_DATE exists, sample values:", [row['BILL_DATE'] for row in sample_data])
                    
                    # Check date range
                    cursor.execute("SELECT MIN(BILL_DATE), MAX(BILL_DATE) FROM Bill_Date_Sale")
                    date_range = cursor.fetchone()
                    print("  Date range:", date_range['MIN(BILL_DATE)'], "to", date_range['MAX(BILL_DATE)'])
                else:
                    print("WARNING: 'BILL_DATE' column not found!")
                    date_cols = [col['Field'] for col in columns if 'date' in col['Field'].lower() or 'time' in col['Field'].lower()]
                    if date_cols:
                        print("  Similar date columns found:", date_cols)
                
                cursor.close()
                return True
            else:
                print("Failed to connect to MySQL database")
                return False
        except Error as e:
            print(f"Error connecting to MySQL database: {e}")
            return False
    
    def execute_query(self, sql_query):

        if not self.connection or not self.connection.is_connected():
            print("[ERROR] Connection lost, reconnecting...")
            self.connect_to_database()
        
        print(f"[DEBUG] Connection ID: {self.connection.connection_id}")
        print(f"[DEBUG] Database: {self.connection.database}")

        
        try:
            # Execute query
            cursor = self.connection.cursor(dictionary=True)
            cursor.execute(sql_query)
            rows = cursor.fetchall()
            
            if len(rows) == 0:
                cursor.close()
                return pd.DataFrame(), None
            
            # Convert to DataFrame
            result_df = pd.DataFrame(rows)
            
            # Handle duplicate column names
            if result_df.columns.duplicated().any():
                new_columns = []
                col_counts = {}
                
                for col in result_df.columns:
                    if col in col_counts:
                        col_counts[col] += 1
                        new_columns.append(f"{col}_{col_counts[col]}")
                    else:
                        col_counts[col] = 0
                        new_columns.append(col)
                
                result_df.columns = new_columns
            
            cursor.close()
            return result_df, None
                    
        except Exception as e:
            error_msg = f"Error executing query: {str(e)}"
            return pd.DataFrame(), error_msg
    
    def test_simple_query(self):
        """Test with a simple query to verify connection works"""
        try:
            test_query = "SELECT COUNT(*) as total_rows FROM Bill_Date_Sale"
            result_df, error = self.execute_query(test_query)
            
            if error:
                print(f"Test query failed: {error}")
                return False
            else:
                if not result_df.empty:
                    print(f"Test query successful. Total rows: {result_df.iloc[0, 0]}")
                    return True
                else:
                    print("Test query returned empty DataFrame")
                    return False
        except Exception as e:
            print(f"Test query exception: {e}")
            return False
    
    def format_results(self, result_df, max_rows=10):
        """
        Format query results as a readable string
        
        Args:
            result_df (DataFrame): Query result DataFrame
            max_rows (int): Maximum number of rows to include
            
        Returns:
            str: Formatted result string
        """
        if result_df is None or result_df.empty:
            return "No results found."
        
        # Limit to max_rows
        if len(result_df) > max_rows:
            display_df = result_df.head(max_rows)
            footer = f"\n... and {len(result_df) - max_rows} more rows"
        else:
            display_df = result_df
            footer = ""
        
        # Format as string
        result_str = display_df.to_string(index=False)
        
        return result_str + footer
    
    def close_connection(self):
        """Close the database connection"""
        if self.connection and self.connection.is_connected():
            self.connection.close()
            print("MySQL connection closed")