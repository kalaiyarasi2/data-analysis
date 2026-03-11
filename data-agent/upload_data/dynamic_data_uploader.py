#!/usr/bin/env python3
"""
Dynamic Data Uploader

A web-based system that allows you to upload Excel files and dynamically create database tables.
Features:
- File upload interface
- Automatic table creation based on Excel structure
- Data validation and preview
- Database integration
"""

from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import pandas as pd
import sqlalchemy
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, Float, Date, Boolean, Text
from sqlalchemy.exc import SQLAlchemyError
import os
import tempfile
import logging
from datetime import datetime
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app setup
app = FastAPI(
    title="Dynamic Data Uploader",
    description="Upload Excel files and dynamically create database tables",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database configuration
class DatabaseConfig:
    def __init__(self):
        self.username = os.getenv('DB_USERNAME', 'postgres')
        self.password = os.getenv('DB_PASSWORD', 'password')
        self.host = os.getenv('DB_HOST', 'localhost')
        self.port = os.getenv('DB_PORT', '5432')
        self.database = os.getenv('DB_NAME', 'data_uploader')
        self.connection_string = f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"

# Global database config
db_config = DatabaseConfig()

class UploadResponse(BaseModel):
    filename: str
    table_name: str
    rows_processed: int
    columns_processed: int
    message: str
    preview_data: List[Dict[str, Any]]

class TableInfo(BaseModel):
    table_name: str
    columns: List[Dict[str, str]]
    row_count: int
    created_at: str

def get_database_engine():
    """Create and return database engine."""
    try:
        engine = create_engine(db_config.connection_string)
        # Test connection
        with engine.connect() as conn:
            conn.execute(sqlalchemy.text("SELECT 1"))
        return engine
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return None

def generate_table_name(filename: str) -> str:
    """Generate a clean table name from filename."""
    # Remove file extension and special characters
    name = filename.replace('.xlsx', '').replace('.xls', '')
    name = ''.join(c for c in name if c.isalnum() or c in ['_', '-'])
    name = name.lower().replace(' ', '_')
    
    # Add timestamp to ensure uniqueness
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{name}_{timestamp}"

def infer_sql_type(series: pd.Series) -> sqlalchemy.types.TypeEngine:
    """Infer SQL type from pandas series."""
    if series.dtype == 'object':
        # Check if it's a date
        try:
            pd.to_datetime(series.dropna())
            return sqlalchemy.Date
        except:
            # Check if it's boolean
            if series.dropna().isin([True, False, 'True', 'False', 'true', 'false']).all():
                return sqlalchemy.Boolean
            # Check if it's numeric but stored as string
            try:
                pd.to_numeric(series.dropna())
                return sqlalchemy.Float
            except:
                # Default to Text for long strings, String for short ones
                max_length = series.astype(str).str.len().max() if not series.empty else 255
                return sqlalchemy.Text if max_length > 255 else sqlalchemy.String(max_length)
    elif series.dtype in ['int64', 'int32']:
        return sqlalchemy.Integer
    elif series.dtype in ['float64', 'float32']:
        return sqlalchemy.Float
    elif series.dtype == 'bool':
        return sqlalchemy.Boolean
    elif series.dtype.name.startswith('datetime'):
        return sqlalchemy.Date
    else:
        return sqlalchemy.Text

def create_table_from_dataframe(df: pd.DataFrame, table_name: str, engine) -> bool:
    """Create database table from DataFrame structure."""
    try:
        metadata = MetaData()
        
        # Create columns based on DataFrame
        columns = []
        for col_name, series in df.items():
            # Clean column name for SQL
            clean_name = ''.join(c for c in col_name if c.isalnum() or c in ['_', '-'])
            clean_name = clean_name.lower().replace(' ', '_')
            
            sql_type = infer_sql_type(series)
            columns.append(Column(clean_name, sql_type))
        
        # Create table
        table = Table(table_name, metadata, *columns)
        metadata.create_all(engine)
        
        logger.info(f"Created table: {table_name} with {len(columns)} columns")
        return True
        
    except Exception as e:
        logger.error(f"Error creating table: {e}")
        return False

def insert_data_to_table(df: pd.DataFrame, table_name: str, engine) -> bool:
    """Insert DataFrame data into database table."""
    try:
        # Clean column names for SQL
        clean_columns = {}
        for col in df.columns:
            clean_name = ''.join(c for c in col if c.isalnum() or c in ['_', '-'])
            clean_name = clean_name.lower().replace(' ', '_')
            clean_columns[col] = clean_name
        
        df_renamed = df.rename(columns=clean_columns)
        
        # Insert data
        df_renamed.to_sql(table_name, engine, if_exists='replace', index=False)
        logger.info(f"Inserted {len(df)} rows into table: {table_name}")
        return True
        
    except Exception as e:
        logger.error(f"Error inserting data: {e}")
        return False

@app.get("/", response_class=HTMLResponse)
async def get_upload_page():
    """Serve the upload interface."""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Dynamic Data Uploader</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
            .container { background: #f5f5f5; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
            .form-group { margin-bottom: 15px; }
            label { display: block; margin-bottom: 5px; font-weight: bold; }
            input[type="file"] { width: 100%; padding: 10px; }
            button { background: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; }
            button:hover { background: #0056b3; }
            .preview { margin-top: 20px; }
            .table-container { overflow-x: auto; }
            table { width: 100%; border-collapse: collapse; margin-top: 10px; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
            th { background-color: #f2f2f2; }
            .status { margin-top: 20px; padding: 15px; border-radius: 4px; }
            .success { background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
            .error { background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
            .info { background-color: #d1ecf1; color: #0c5460; border: 1px solid #bee5eb; }
        </style>
    </head>
    <body>
        <h1>🚀 Dynamic Data Uploader</h1>
        <p>Upload Excel files and automatically create database tables with your data.</p>
        
        <div class="container">
            <form id="uploadForm" enctype="multipart/form-data">
                <div class="form-group">
                    <label for="file">Select Excel File:</label>
                    <input type="file" id="file" name="file" accept=".xlsx,.xls" required>
                </div>
                <button type="submit">Upload & Process</button>
            </form>
        </div>

        <div id="status" class="status" style="display: none;"></div>
        
        <div id="preview" class="preview" style="display: none;">
            <h3>📊 Data Preview</h3>
            <div id="previewContent"></div>
        </div>

        <script>
            document.getElementById('uploadForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                
                const fileInput = document.getElementById('file');
                const file = fileInput.files[0];
                
                if (!file) {
                    showStatus('Please select a file', 'error');
                    return;
                }

                const formData = new FormData();
                formData.append('file', file);

                showStatus('Uploading and processing...', 'info');

                try {
                    const response = await fetch('/upload', {
                        method: 'POST',
                        body: formData
                    });

                    const result = await response.json();

                    if (response.ok) {
                        showStatus(`✅ Success! Table created: ${result.table_name}<br>Rows: ${result.rows_processed}, Columns: ${result.columns_processed}<br>Message: ${result.message}`, 'success');
                        showPreview(result.preview_data, result.columns);
                    } else {
                        showStatus(`❌ Error: ${result.detail}`, 'error');
                    }
                } catch (error) {
                    showStatus(`❌ Network error: ${error}`, 'error');
                }
            });

            function showStatus(message, type) {
                const statusDiv = document.getElementById('status');
                statusDiv.innerHTML = message;
                statusDiv.className = `status ${type}`;
                statusDiv.style.display = 'block';
            }

            function showPreview(data, columns) {
                const previewDiv = document.getElementById('preview');
                const contentDiv = document.getElementById('previewContent');
                
                if (data.length === 0) {
                    contentDiv.innerHTML = '<p>No data to preview</p>';
                } else {
                    let tableHtml = '<table><thead><tr>';
                    // Use original column names for display
                    Object.keys(data[0]).forEach(key => {
                        tableHtml += `<th>${key}</th>`;
                    });
                    tableHtml += '</tr></thead><tbody>';
                    
                    data.forEach(row => {
                        tableHtml += '<tr>';
                        Object.values(row).forEach(value => {
                            tableHtml += `<td>${value}</td>`;
                        });
                        tableHtml += '</tr>';
                    });
                    
                    tableHtml += '</tbody></table>';
                    contentDiv.innerHTML = tableHtml;
                }
                
                previewDiv.style.display = 'block';
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.post("/upload", response_model=UploadResponse)
async def upload_excel_file(file: UploadFile = File(...)):
    """Upload and process Excel file."""
    try:
        # Validate file type
        if not file.filename.lower().endswith(('.xlsx', '.xls')):
            raise HTTPException(status_code=400, detail="Only Excel files (.xlsx, .xls) are supported")
        
        # Read file content
        content = await file.read()
        
        # Save to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as temp_file:
            temp_file.write(content)
            temp_file_path = temp_file.name
        
        try:
            # Read Excel file
            df = pd.read_excel(temp_file_path)
            
            if df.empty:
                raise HTTPException(status_code=400, detail="Excel file is empty")
            
            # Generate table name
            table_name = generate_table_name(file.filename)
            
            # Get database engine
            engine = get_database_engine()
            if not engine:
                raise HTTPException(status_code=500, detail="Database connection failed")
            
            # Create table
            if not create_table_from_dataframe(df, table_name, engine):
                raise HTTPException(status_code=500, detail="Failed to create database table")
            
            # Insert data
            if not insert_data_to_table(df, table_name, engine):
                raise HTTPException(status_code=500, detail="Failed to insert data into table")
            
            # Prepare preview data (first 5 rows)
            preview_data = df.head().to_dict('records')
            
            return UploadResponse(
                filename=file.filename,
                table_name=table_name,
                rows_processed=len(df),
                columns_processed=len(df.columns),
                message=f"Successfully created table '{table_name}' with {len(df)} rows",
                preview_data=preview_data
            )
            
        finally:
            # Clean up temporary file
            os.unlink(temp_file_path)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/tables", response_model=List[TableInfo])
async def list_tables():
    """List all tables in the database."""
    try:
        engine = get_database_engine()
        if not engine:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        # Get table names
        inspector = sqlalchemy.inspect(engine)
        table_names = inspector.get_table_names()
        
        tables_info = []
        for table_name in table_names:
            try:
                # Get column info
                columns = inspector.get_columns(table_name)
                column_info = [{"name": col['name'], "type": str(col['type'])} for col in columns]
                
                # Get row count
                with engine.connect() as conn:
                    result = conn.execute(sqlalchemy.text(f"SELECT COUNT(*) FROM {table_name}"))
                    row_count = result.scalar()
                
                tables_info.append({
                    "table_name": table_name,
                    "columns": column_info,
                    "row_count": row_count,
                    "created_at": datetime.now().isoformat()
                })
            except Exception as e:
                logger.warning(f"Could not get info for table {table_name}: {e}")
                continue
        
        return tables_info
        
    except Exception as e:
        logger.error(f"Error listing tables: {e}")
        raise HTTPException(status_code=500, detail="Failed to list tables")

@app.get("/table/{table_name}")
async def get_table_data(table_name: str, limit: int = 100):
    """Get data from a specific table."""
    try:
        engine = get_database_engine()
        if not engine:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        # Check if table exists
        inspector = sqlalchemy.inspect(engine)
        if table_name not in inspector.get_table_names():
            raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")
        
        # Get data
        query = f"SELECT * FROM {table_name} LIMIT {limit}"
        df = pd.read_sql(query, engine)
        
        return {
            "table_name": table_name,
            "data": df.to_dict('records'),
            "total_rows": len(df),
            "columns": list(df.columns)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting table data: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve table data")

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting Dynamic Data Uploader...")
    print(f"📁 Database: {db_config.database}")
    print(f"🌐 Server: http://localhost:8000")
    print("💡 Upload Excel files to automatically create database tables!")
    uvicorn.run(app, host="0.0.0.0", port=8000)