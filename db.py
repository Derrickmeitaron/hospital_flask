import mysql.connector

def get_db_connection():
    return mysql.connector.connect(
    host="mysql-derrick.alwaysdata.net",
    user="derrick",
    password="modcom2026",
    database="derrick_hospital"
)
