# 🚀 Dynamic Data Uploader

Welcome to your **Dynamic Data Uploader** system! This folder contains everything you need to upload Excel files and automatically create database tables.

## 📁 Contents

- **`dynamic_data_uploader.py`** - Main web application (FastAPI)
- **`start_uploader.py`** - Easy startup script with dependency checking
- **`DYNAMIC_UPLOADER_GUIDE.md`** - Complete user guide and documentation

## 🚀 Quick Start

### Option 1: Easy Startup (Recommended)
```bash
cd upload_data
python start_uploader.py
```

### Option 2: Direct Startup
```bash
cd upload_data
python dynamic_data_uploader.py
```

## 🌐 Web Interface

Once started, open your browser and navigate to:
**http://localhost:8000**

You'll see a clean, user-friendly interface where you can:
1. **Upload Excel files** (.xlsx, .xls)
2. **Preview data** before saving
3. **View upload results** with table details

## 🔧 Features

### ✨ Automatic Processing
- **Smart data type detection** - Automatically maps Excel data to database types
- **Dynamic table creation** - Creates tables with proper column names and types
- **Timestamp-based naming** - Ensures unique table names for each upload
- **Data validation** - Checks file format and content

### 🌐 Web Interface
- **Drag-and-drop upload** support
- **Real-time data preview**
- **Upload status and results**
- **Responsive design** - works on desktop and mobile

### 🔌 API Access
- `GET /` - Web upload interface
- `POST /upload` - Upload and process Excel files
- `GET /tables` - List all database tables
- `GET /table/{table_name}` - Get data from specific table

## 🗄️ Database Integration

### Configuration
Set up your database credentials in `.env` file:
```env
DB_USERNAME=your_username
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432
DB_NAME=your_database
```

### Database Features
- **Automatic table creation** based on Excel structure
- **Data type inference** for optimal storage
- **Row counting** and metadata tracking
- **Table listing** and management

## 📊 Data Processing

### Automatic Data Type Mapping
| Excel Data Type | Database Type | Description |
|----------------|---------------|-------------|
| Text | VARCHAR/TEXT | String data |
| Numbers | INTEGER/FLOAT | Numeric data |
| Dates | DATE | Date values |
| Booleans | BOOLEAN | True/False values |
| Mixed/Long Text | TEXT | Large text fields |

### Table Naming Convention
Tables are named using: `{filename}_{timestamp}`
Example: `payroll_data_20260304_151430`

## 💡 Use Cases

### Payroll Processing
- Upload payroll Excel files
- Automatically create payroll tables
- Process and analyze compensation data

### Inventory Management
- Upload inventory spreadsheets
- Create inventory tracking tables
- Monitor stock levels and movements

### Sales Data Analysis
- Upload sales reports
- Create sales analytics tables
- Track performance metrics

### HR Data Management
- Upload employee records
- Create HR database tables
- Manage personnel information

## 🔧 Troubleshooting

### Common Issues

**1. Database Connection Failed**
- Check PostgreSQL is running
- Verify database credentials in `.env`
- Ensure database exists

**2. File Upload Failed**
- Check file is Excel format (.xlsx, .xls)
- Verify file is not empty
- Check file size limits

**3. Dependencies Missing**
```bash
pip install fastapi uvicorn pandas openpyxl sqlalchemy psycopg2-binary
```

### Error Messages
- **"Database connection failed"**: Check PostgreSQL setup
- **"Only Excel files supported"**: Upload .xlsx or .xls files
- **"Excel file is empty"**: File has no data
- **"Internal server error"**: Check logs for details

## 📖 Documentation

For detailed information, see:
- **`DYNAMIC_UPLOADER_GUIDE.md`** - Complete user guide
- **`PAYROLL_SOLUTION_SUMMARY.md`** - Full solution overview (in parent directory)

## 🎯 Next Steps

1. **Test with your data** - Upload your payroll Excel file!
2. **Explore the API** - Use endpoints for programmatic access
3. **Customize the interface** - Modify HTML/CSS for your branding
4. **Add features** - Extend with authentication, validation, etc.

## 🎉 Success!

You now have a complete **Dynamic Data Uploader** system that:
- ✅ **Uploads Excel files through a web interface**
- ✅ **Automatically creates database tables**
- ✅ **Provides data preview and validation**
- ✅ **Offers API access for integration**
- ✅ **Scales with your data needs**

Start uploading your Excel files and watch them automatically become database tables!

---

**💡 Pro Tip**: Try uploading your `payroll_monthly_sample.xlsx` file to see the system in action!