#!/usr/bin/env python3
"""
Enhanced Startup Script for Enhanced Dynamic Data Uploader

This script helps you start the enhanced dynamic data uploader with proper configuration.
Features automatic database creation and smart schema generation.
"""

import os
import sys
import subprocess
from pathlib import Path

def check_dependencies():
    """Check if all required dependencies are installed."""
    required_packages = [
        'fastapi', 'uvicorn', 'pandas', 'openpyxl', 'sqlalchemy', 'psycopg2', 'python-multipart'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print("❌ Missing required packages:")
        for package in missing_packages:
            print(f"   - {package}")
        print("\n💡 Install them with:")
        print(f"   pip install {' '.join(missing_packages)}")
        return False
    
    print("✅ All required packages are installed")
    return True

def check_database_config():
    """Check if database configuration is available."""
    db_vars = {
        'DB_USERNAME': os.getenv('DB_USERNAME'),
        'DB_PASSWORD': os.getenv('DB_PASSWORD'),
        'DB_HOST': os.getenv('DB_HOST', 'localhost'),
        'DB_PORT': os.getenv('DB_PORT', '5432'),
        'DB_NAME': os.getenv('DB_NAME', 'insurance')
    }
    
    print("🗄️  Database Configuration:")
    for key, value in db_vars.items():
        if key in ['DB_USERNAME', 'DB_PASSWORD'] and value:
            print(f"   {key}: {'*' * len(value)}")
        else:
            print(f"   {key}: {value}")
    
    if not db_vars['DB_USERNAME'] or not db_vars['DB_PASSWORD']:
        print("\n⚠️  Warning: Database credentials not configured")
        print("💡 Set DB_USERNAME and DB_PASSWORD in your .env file or environment variables")
        print("💡 Using default credentials: postgres / Cognet@2026")
        return False
    
    return True

def create_sample_env():
    """Create a sample .env file if one doesn't exist."""
    env_content = """# Database Configuration for Enhanced Dynamic Data Uploader
# Copy these lines to your .env file to enable database functionality

# PostgreSQL Database Configuration
DB_USERNAME=postgres
DB_PASSWORD=Cognet@2026
DB_HOST=localhost
DB_PORT=5432
DB_NAME=insurance

# Instructions:
# 1. Replace credentials if needed
# 2. The enhanced uploader will automatically create the database if it doesn't exist
# 3. Tables will be created automatically based on Excel file structure
"""
    
    env_file = Path('.env')
    if not env_file.exists():
        print("📝 Creating sample .env file...")
        with open(env_file, 'w') as f:
            f.write(env_content)
        print("✅ Created .env file with sample configuration")
        return True
    else:
        print("✅ .env file already exists")
        return False

def main():
    """Main startup function."""
    print("🚀 Enhanced Dynamic Data Uploader Startup")
    print("=" * 60)
    print("✨ Features: Auto Database Creation, Smart Schema, Real-time Progress")
    print("=" * 60)
    
    # Check dependencies
    if not check_dependencies():
        print("\n❌ Cannot start: Missing dependencies")
        sys.exit(1)
    
    # Create sample .env if needed
    create_sample_env()
    
    # Check database configuration
    db_configured = check_database_config()
    
    print("\n" + "=" * 60)
    print("🎯 Starting Enhanced Dynamic Data Uploader...")
    
    if not db_configured:
        print("\n⚠️  Using default database configuration")
        print("💡 The system will automatically create the database if needed")
    
    print("\n🌐 Starting web server...")
    print("📁 Upload Excel files to automatically:")
    print("   ✅ Create database (if needed)")
    print("   ✅ Create tables with smart schema")
    print("   ✅ Store data with real-time progress")
    print("   ✅ Provide data preview and statistics")
    print("\n🌐 Access the uploader at: http://localhost:8000")
    print("💡 Press Ctrl+C to stop the server")
    print("=" * 60)
    
    try:
        # Start the enhanced uploader
        subprocess.run([sys.executable, 'upload_data/enhanced_data_uploader.py'])
    except KeyboardInterrupt:
        print("\n🛑 Stopping server...")
        print("✅ Enhanced Dynamic Data Uploader stopped")
    except Exception as e:
        print(f"\n❌ Error starting server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()