"""
Web API Controller (File 2)
===========================
This file handles HTTP web traffic from users.
Notice that inside this file:
- There is NO cursor.execute()
- There is NO raw SQL execution sink
- It merely calls the imported utility function `execute_filtered_query()` from storage_service.
"""

from flask import Flask, request, jsonify
import sqlite3
from storage_service import execute_filtered_query

app = Flask(__name__)


@app.route("/api/items", methods=["GET"])
def get_store_items():
    # Source: Untrusted HTTP query parameter
    search_term = request.args.get("category", "books")

    # Connect to database
    conn = sqlite3.connect("store.db")

    # DANGEROUS CALL ACROSS FILES:
    # Notice: In this file, there is no direct SQL sink!
    # It passes an interpolated string into an imported function in another file.
    results = execute_filtered_query(conn, "inventory", f"category = '{search_term}'")
    conn.close()

    return jsonify({"items": results})


if __name__ == "__main__":
    app.run(port=5000)
