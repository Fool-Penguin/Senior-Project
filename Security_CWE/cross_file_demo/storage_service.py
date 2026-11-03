"""
Storage Service Helper (File 1)
===============================
This file contains internal database utility functions.
By itself, this file contains NO HTTP requests, NO user inputs, and looks like
a standard dynamic query utility that expects trusted internal queries.
"""

import sqlite3
from typing import List, Tuple, Any


def execute_filtered_query(conn: sqlite3.Connection, table_name: str, filter_clause: str) -> List[Tuple[Any, ...]]:
    """
    Executes a query with a caller-supplied filter clause.
    - Inside this file: filter_clause is just an internal Python string parameter.
    - No request.args, no sys.argv, no external web inputs exist here.
    """
    cursor = conn.cursor()
    # Looks like an internal query builder
    sql_statement = f"SELECT id, name, category, price FROM {table_name} WHERE {filter_clause}"
    cursor.execute(sql_statement)
    return cursor.fetchall()
