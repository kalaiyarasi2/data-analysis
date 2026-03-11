import pyodbc
import os
from dotenv import load_dotenv

load_dotenv('pg-agent/.env')

server = os.getenv("DB_HOST")
port = os.getenv("DB_PORT", "1433")
database = os.getenv("DB_NAME")
user = os.getenv("DB_USER")
password = os.getenv("DB_PASSWORD")

conn_str = f'DRIVER={{SQL Server}};SERVER={server};PORT={port};DATABASE={database};UID={user};PWD={password}'

try:
    conn = pyodbc.connect(conn_str, autocommit=True)
    cursor = conn.cursor()
    print("Refreshing view: dbo.View_Report_pipiline")
    cursor.execute("EXEC sp_refreshview 'dbo.View_Report_pipiline'")
    print("Successfully refreshed view metadata.")
except Exception as e:
    print(f"Failed to refresh view: {e}")
finally:
    if 'conn' in locals():
        conn.close()
