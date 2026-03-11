#!/usr/bin/env python3
"""
Enhanced Dynamic Data Uploader

A web-based system that allows you to upload Excel files and automatically:
1. Creates database if it doesn't exist
2. Creates tables based on Excel file schema
3. Stores data in the database
4. Provides real-time feedback and progress

Features:
- Automatic database creation
- Smart table schema generation
- Real-time upload progress
- Enhanced error handling
- Database status monitoring
"""

from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import pandas as pd
import sqlalchemy
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, Float, Date, Boolean, Text, text
from sqlalchemy.exc import SQLAlchemyError
import os
import tempfile
import logging
import asyncio
from datetime import datetime
import json
from dotenv import load_dotenv

# Load environment variables from .env in the project root
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app setup
app = FastAPI(
    title="Enhanced Dynamic Data Uploader",
    description="Upload Excel files and automatically create database tables with smart schema generation",
    version="2.0.0"
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
        import urllib.parse
        self.db_type = os.getenv('DB_TYPE', 'postgres')
        self.username = os.getenv('DB_USER', os.getenv('DB_USERNAME', 'sa'))
        self.password = os.getenv('DB_PASSWORD', 'C0gnet@1')
        self.host = os.getenv('DB_HOST', '10.10.10.49')
        self.port = os.getenv('DB_PORT', '1433')
        self.database = os.getenv('DB_NAME', 'WCNDev3')
        self.driver = os.getenv('DB_DRIVER', 'SQL Server')
        
        # URL encode password and driver
        self.encoded_pwd = urllib.parse.quote_plus(self.password)
        self.encoded_driver = urllib.parse.quote_plus(self.driver)
        
        self.connection_string = self._build_url(self.database)
        self.server_connection_string = self._build_url('postgres' if self.db_type == 'postgres' else 'master')

    def _build_url(self, db_name: str | None) -> str:
        if self.db_type == 'postgres':
            return f"postgresql://{self.username}:{self.encoded_pwd}@{self.host}:{self.port}/{db_name or 'postgres'}"
        elif self.db_type == 'mysql':
            return f"mysql+pymysql://{self.username}:{self.encoded_pwd}@{self.host}:{self.port}/{db_name or ''}"
        elif self.db_type == 'mssql':
            # Use pyodbc (sync) for the uploader as it often uses direct engine calls
            # Standard URL format with quoted driver and TrustServerCertificate
            return f"mssql+pyodbc://{self.username}:{self.encoded_pwd}@{self.host}:{self.port}/{db_name or 'master'}?driver={self.encoded_driver}&TrustServerCertificate=yes"
        return f"postgresql://{self.username}:{self.encoded_pwd}@{self.host}:{self.port}/{db_name or 'postgres'}"

# Global database config
db_config = DatabaseConfig()

class UploadResponse(BaseModel):
    filename: str
    table_name: str
    rows_processed: int
    columns_processed: int
    message: str
    preview_data: List[Dict[str, Any]]
    database_created: bool
    table_created: bool

class TableInfo(BaseModel):
    table_name: str
    columns: List[Dict[str, str]]
    row_count: int
    created_at: str
    database_name: str

def get_server_engine():
    """Create and return server-level database engine (for database creation)."""
    try:
        engine = create_engine(db_config.server_connection_string)
        # Test connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return engine
    except Exception as e:
        logger.error(f"Server database connection failed: {e}")
        return None

def get_database_engine():
    """Create and return database engine."""
    try:
        engine = create_engine(db_config.connection_string)
        # Test connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return engine
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return None

def ensure_database_exists():
    """Check if database exists, create it if it doesn't."""
    try:
        server_engine = get_server_engine()
        if not server_engine:
            return False, "Server connection failed"

        # Define dialect-specific check and create logic
        db_name = db_config.database
        exists_sql = ""
        create_sql = f"CREATE DATABASE {db_name}"

        if db_config.db_type == 'postgres':
            exists_sql = "SELECT 1 FROM pg_database WHERE datname = :db_name"
        elif db_config.db_type == 'mysql':
            exists_sql = "SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME = :db_name"
        elif db_config.db_type == 'mssql':
            exists_sql = "SELECT 1 FROM sys.databases WHERE name = :db_name"
        
        # Check if database exists
        with server_engine.connect() as conn:
            result = conn.execute(text(exists_sql), {"db_name": db_name})
            database_exists = result.scalar() is not None

        if not database_exists:
            logger.info(f"Database '{db_name}' does not exist, creating...")
            # Use a fresh connection in AUTOCOMMIT mode for CREATE DATABASE
            with server_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
                conn.execute(text(create_sql))
            logger.info(f"Database '{db_name}' created successfully")
            return True, "Database created successfully"
        else:
            logger.info(f"Database '{db_name}' already exists")
            return True, "Database already exists"
            
    except Exception as e:
        logger.error(f"Error ensuring database exists: {e}")
        return False, str(e)
            
    except Exception as e:
        logger.error(f"Error ensuring database exists: {e}")
        return False, str(e)

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
    """Intelligently infer SQL type from pandas series."""
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
                numeric_series = pd.to_numeric(series.dropna())
                # Check if it's actually integer
                if (numeric_series == numeric_series.astype(int)).all():
                    return sqlalchemy.Integer
                else:
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
    """Create database table from DataFrame structure with smart schema."""
    try:
        metadata = MetaData()
        
        # Create columns based on DataFrame with smart naming
        columns = []
        for col_name, series in df.items():
            # Clean column name for SQL
            clean_name = ''.join(c for c in col_name if c.isalnum() or c in ['_', '-'])
            clean_name = clean_name.lower().replace(' ', '_')
            
            # Handle empty column names
            if not clean_name:
                clean_name = f"column_{len(columns) + 1}"
            
            # Handle duplicate column names
            original_name = clean_name
            counter = 1
            while any(col.name == clean_name for col in columns):
                clean_name = f"{original_name}_{counter}"
                counter += 1
            
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
            
            # Handle empty column names
            if not clean_name:
                clean_name = f"column_{len(clean_columns) + 1}"
            
            # Handle duplicate column names
            original_name = clean_name
            counter = 1
            while clean_name in clean_columns.values():
                clean_name = f"{original_name}_{counter}"
                counter += 1
            
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
    """Serve the enhanced upload interface."""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Enhanced Dynamic Data Uploader</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { font-family: Arial, sans-serif; max-width: 1000px; margin: 0 auto; padding: 20px; background-color: #f5f5f5; }
            .container { background: white; padding: 30px; border-radius: 12px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); margin-bottom: 20px; }
            .header { text-align: center; margin-bottom: 30px; }
            .header h1 { color: #2c3e50; margin: 0; font-size: 2.5em; }
            .header p { color: #7f8c8d; font-size: 1.1em; }
            .form-group { margin-bottom: 25px; }
            label { display: block; margin-bottom: 10px; font-weight: bold; color: #34495e; }
            input[type="file"] { width: 100%; padding: 12px; border: 2px dashed #3498db; border-radius: 8px; background-color: #ecf0f1; cursor: pointer; transition: all 0.3s; }
            input[type="file"]:hover { border-color: #2980b9; background-color: #d6eaf8; }
            button { background: #3498db; color: white; padding: 15px 30px; border: none; border-radius: 8px; cursor: pointer; font-size: 1.1em; transition: all 0.3s; width: 100%; }
            button:hover { background: #2980b9; transform: translateY(-2px); box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
            button:disabled { background: #95a5a6; cursor: not-allowed; transform: none; box-shadow: none; }
            .status { margin-top: 20px; padding: 20px; border-radius: 8px; font-weight: bold; }
            .success { background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
            .error { background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
            .info { background-color: #d1ecf1; color: #0c5460; border: 1px solid #bee5eb; }
            .warning { background-color: #fff3cd; color: #856404; border: 1px solid #ffeaa7; }
            .preview { margin-top: 20px; }
            .table-container { overflow-x: auto; border-radius: 8px; border: 1px solid #dee2e6; }
            table { width: 100%; border-collapse: collapse; margin-top: 10px; }
            th, td { border: 1px solid #dee2e6; padding: 12px; text-align: left; font-size: 0.9em; }
            th { background-color: #f8f9fa; font-weight: bold; color: #495057; }
            .progress-bar { width: 100%; height: 20px; background-color: #ecf0f1; border-radius: 10px; overflow: hidden; margin: 10px 0; }
            .progress-fill { height: 100%; background-color: #3498db; width: 0%; transition: width 0.3s; }
            .progress-text { text-align: center; color: #7f8c8d; font-size: 0.9em; }
            .features { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 15px; margin-top: 20px; }
            .feature-card { background: #f8f9fa; padding: 15px; border-radius: 8px; border-left: 4px solid #3498db; }
            .feature-card h4 { margin: 0 0 5px 0; color: #2c3e50; }
            .feature-card p { margin: 0; color: #7f8c8d; font-size: 0.9em; }
            .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-top: 20px; }
            .stat-card { background: white; padding: 20px; border-radius: 8px; text-align: center; border: 1px solid #dee2e6; }
            .stat-number { font-size: 2em; font-weight: bold; color: #3498db; }
            .stat-label { color: #7f8c8d; font-size: 0.9em; margin-top: 5px; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🚀 Enhanced Data Uploader</h1>
                <p>Upload Excel files and automatically create database tables with smart schema generation</p>
            </div>

            <div class="features">
                <div class="feature-card">
                    <h4>🗄️ Auto Database Creation</h4>
                    <p>Creates database if it doesn't exist - zero setup required</p>
                </div>
                <div class="feature-card">
                    <h4>📊 Smart Schema Generation</h4>
                    <p>Intelligently maps Excel data types to optimal database types</p>
                </div>
                <div class="feature-card">
                    <h4>⚡ Real-time Progress</h4>
                    <p>See upload progress and processing status in real-time</p>
                </div>
                <div class="feature-card">
                    <h4>🛡️ Enhanced Error Handling</h4>
                    <p>Graceful handling of all errors with clear feedback</p>
                </div>
            </div>

            <form id="uploadForm" enctype="multipart/form-data">
                <div class="form-group">
                    <label for="file">📁 Select Excel File (.xlsx, .xls):</label>
                    <input type="file" id="file" name="file" accept=".xlsx,.xls" required>
                </div>
                <button type="submit" id="uploadBtn">📤 Upload & Process</button>
            </form>

            <div id="progressSection" style="display: none; margin-top: 20px;">
                <div class="progress-bar">
                    <div class="progress-fill" id="progressFill"></div>
                </div>
                <div class="progress-text" id="progressText">Preparing upload...</div>
            </div>

            <div id="status" class="status" style="display: none;"></div>
        </div>

        <div id="preview" class="container" style="display: none;">
            <h3>📊 Data Preview</h3>
            <div class="stats">
                <div class="stat-card">
                    <div class="stat-number" id="rowsCount">0</div>
                    <div class="stat-label">Rows Processed</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" id="colsCount">0</div>
                    <div class="stat-label">Columns Processed</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" id="tableName">-</div>
                    <div class="stat-label">Table Created</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" id="dbName">-</div>
                    <div class="stat-label">Database</div>
                </div>
            </div>
            <div class="table-container" id="previewContent" style="margin-top: 20px;"></div>
        </div>

        <script>
            document.getElementById('uploadForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                
                const fileInput = document.getElementById('file');
                const file = fileInput.files[0];
                const uploadBtn = document.getElementById('uploadBtn');
                const progressSection = document.getElementById('progressSection');
                const progressFill = document.getElementById('progressFill');
                const progressText = document.getElementById('progressText');
                
                if (!file) {
                    showStatus('Please select a file', 'error');
                    return;
                }

                // Reset UI
                uploadBtn.disabled = true;
                uploadBtn.textContent = 'Processing...';
                progressSection.style.display = 'block';
                progressFill.style.width = '0%';
                progressText.textContent = 'Starting upload...';

                const formData = new FormData();
                formData.append('file', file);

                try {
                    // Step 1: Upload and process
                    progressFill.style.width = '20%';
                    progressText.textContent = 'Uploading file...';
                    
                    const response = await fetch('/upload', {
                        method: 'POST',
                        body: formData
                    });

                    progressFill.style.width = '60%';
                    progressText.textContent = 'Processing data...';

                    const result = await response.json();

                    progressFill.style.width = '100%';
                    progressText.textContent = 'Complete!';

                    if (response.ok) {
                        showStatus(`✅ Success! Table created: ${result.table_name}<br>Rows: ${result.rows_processed}, Columns: ${result.columns_processed}<br>Database: ${result.database_created ? 'Created' : 'Existing'}<br>Message: ${result.message}`, 'success');
                        showPreview(result.preview_data, result.rows_processed, result.columns_processed, result.table_name, result.database_created);
                    } else {
                        showStatus(`❌ Error: ${result.detail}`, 'error');
                    }
                } catch (error) {
                    showStatus(`❌ Network error: ${error}`, 'error');
                } finally {
                    uploadBtn.disabled = false;
                    uploadBtn.textContent = 'Upload & Process';
                }
            });

            function showStatus(message, type) {
                const statusDiv = document.getElementById('status');
                statusDiv.innerHTML = message;
                statusDiv.className = `status ${type}`;
                statusDiv.style.display = 'block';
            }

            function showPreview(data, rows, cols, tableName, dbCreated) {
                const previewDiv = document.getElementById('preview');
                const contentDiv = document.getElementById('previewContent');
                const rowsCount = document.getElementById('rowsCount');
                const colsCount = document.getElementById('colsCount');
                const tableCreated = document.getElementById('tableName');
                const dbName = document.getElementById('dbName');
                
                // Update stats
                rowsCount.textContent = rows;
                colsCount.textContent = cols;
                tableCreated.textContent = tableName;
                dbName.textContent = db_config.database || 'insurance';

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
    """Upload and process Excel file with automatic database and table creation."""
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
            
            # Step 1: Ensure database exists
            db_created, db_message = ensure_database_exists()
            if not db_created:
                raise HTTPException(status_code=500, detail=f"Database creation failed: {db_message}")
            
            # Step 2: Get database engine
            engine = get_database_engine()
            if not engine:
                raise HTTPException(status_code=500, detail="Database connection failed after creation")
            
            # Step 3: Create table
            table_created = create_table_from_dataframe(df, table_name, engine)
            if not table_created:
                raise HTTPException(status_code=500, detail="Failed to create database table")
            
            # Step 4: Insert data
            data_inserted = insert_data_to_table(df, table_name, engine)
            if not data_inserted:
                raise HTTPException(status_code=500, detail="Failed to insert data into table")
            
            # Prepare preview data (first 5 rows)
            preview_data = df.head().to_dict('records')
            
            return UploadResponse(
                filename=file.filename,
                table_name=table_name,
                rows_processed=len(df),
                columns_processed=len(df.columns),
                message=f"Successfully created table '{table_name}' with {len(df)} rows in database '{db_config.database}'",
                preview_data=preview_data,
                database_created=db_created,
                table_created=True
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
                    result = conn.execute(text(f'SELECT COUNT(*) FROM "{table_name}"'))
                    row_count = result.scalar()
                
                tables_info.append({
                    "table_name": table_name,
                    "columns": column_info,
                    "row_count": row_count,
                    "created_at": datetime.now().isoformat(),
                    "database_name": db_config.database
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
        query = f'SELECT * FROM "{table_name}" LIMIT {limit}'
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
    print("🚀 Starting Enhanced Dynamic Data Uploader...")
    print(f"📁 Database: {db_config.database}")
    print(f"🌐 Server: http://localhost:8000")
    print("💡 Upload Excel files to automatically create database tables!")
    print("✨ Features: Auto DB creation, Smart schema, Real-time progress")
    uvicorn.run(app, host="0.0.0.0", port=8000)