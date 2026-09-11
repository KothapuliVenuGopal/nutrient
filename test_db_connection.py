"""
Database connection verification script for macOS MySQL.
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / '.env')

import pymysql
pymysql.install_as_MySQLdb()

import django
from django.db import connection

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'food_delivery.settings')
django.setup()

try:
    with connection.cursor() as cursor:
        cursor.execute("SELECT VERSION();")
        ver = cursor.fetchone()
        print(f"✅ Successfully connected to MySQL database! Server version: {ver[0]}")
        cursor.execute("SELECT DATABASE();")
        current_db = cursor.fetchone()
        print(f"✅ Active Database: {current_db[0]}")
except Exception as e:
    print(f"⚠️  Database connection check: {e}")
    print("\n👉 macOS MySQL Note:")
    print("If your MySQL root account requires a password, please set DB_PASSWORD in your .env file.")
    print("If your database 'nutrient_db' has not yet been created, you can run in terminal:")
    print("    mysql -u root -p -e 'CREATE DATABASE nutrient_db CHARACTER SET utf8mb4;'")
    print("Or to switch seamlessly to SQLite for local development, set USE_SQLITE=True in .env.")
