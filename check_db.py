#check_db.py
import sqlite3

conn = sqlite3.connect("wheat.db")
c = conn.cursor()

print("Runs:")
c.execute("SELECT * FROM runs")
for row in c.fetchall():
    print(row)

print("\nStrains:")
c.execute("SELECT * FROM strains")
for row in c.fetchall():
    print(row)

print("\nAPI Logs:")
c.execute("SELECT * FROM api_logs")
for row in c.fetchall():
    print(row)

conn.close()