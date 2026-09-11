"""
Nutrient - The Super Food
Core Package Initialization
Configures PyMySQL as the MySQL database driver for macOS/cross-platform compatibility.
"""
import pymysql

pymysql.install_as_MySQLdb()
