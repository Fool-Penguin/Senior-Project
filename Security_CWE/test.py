from flask import Flask, request
import sqlite3

app = Flask(__name__)

@app.route("/search")
def search():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    user_input = request.args.get("q")  # <--- TAINT SOURCE
    query = f"SELECT * FROM items WHERE name = '{user_input}'"  # <--- SQL INJECTION
    cursor.execute(query)  # <--- TAINT SINK
    return str(cursor.fetchall())

