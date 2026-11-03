# ==============================================================================
# Medium Database Service Sample (~250 LOC)
# Simulates enterprise repository layer with connection pooling, multi-query methods,
# transaction management, and inline business comments.
# ==============================================================================

import sqlite3
import logging
from typing import List, Dict, Optional, Tuple, Any

logger = logging.getLogger("db_service")

class DatabaseConnectionPool:
    """Manages thread-local or pooled connections to the local store."""
    def __init__(self, db_path: str = ":memory:", pool_size: int = 5):
        self.db_path = db_path
        self.pool_size = pool_size
        self._connections: List[sqlite3.Connection] = []
        self._initialize_pool()

    def _initialize_pool(self) -> None:
        # Pre-allocate pooled connections
        for _ in range(self.pool_size):
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            self._connections.append(conn)

    def acquire(self) -> sqlite3.Connection:
        """Acquires a free connection from the pool."""
        if not self._connections:
            # Fallback to dynamic connection
            return sqlite3.connect(self.db_path)
        return self._connections.pop()

    def release(self, conn: sqlite3.Connection) -> None:
        """Returns connection to the active pool."""
        if len(self._connections) < self.pool_size:
            self._connections.append(conn)
        else:
            conn.close()

class SecurityAuditRepository:
    """Handles persistent audit logging and vulnerability records."""

    def __init__(self, pool: DatabaseConnectionPool):
        self.pool = pool
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        conn = self.pool.acquire()
        try:
            cursor = conn.cursor()
            # DDL initialization for audit records
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    target_entity TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    payload_summary TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
        finally:
            self.pool.release(conn)

    def record_finding(self, event_type: str, entity: str, severity: str, details: str) -> int:
        """Inserts a single security finding with parameterized binding."""
        conn = self.pool.acquire()
        try:
            cursor = conn.cursor()
            # Defensive parameterized query to prevent SQLi
            cursor.execute(
                "INSERT INTO audit_events (event_type, target_entity, severity, payload_summary) VALUES (?, ?, ?, ?)",
                (event_type, entity, severity, details)
            )
            conn.commit()
            return cursor.lastrowid or -1
        except sqlite3.Error as e:
            logger.error(f"Database insertion failed: {e}")
            conn.rollback()
            return -1
        finally:
            self.pool.release(conn)

    def fetch_critical_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Queries high and critical severity events for dashboard display."""
        conn = self.pool.acquire()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, event_type, target_entity, severity, created_at FROM audit_events WHERE severity IN ('CRITICAL', 'HIGH') ORDER BY id DESC LIMIT ?",
                (limit,)
            )
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
        finally:
            self.pool.release(conn)

    def batch_update_status(self, updates: List[Tuple[str, int]]) -> int:
        """Executes transactional batch update across findings."""
        conn = self.pool.acquire()
        modified_count = 0
        try:
            cursor = conn.cursor()
            # Begin explicit transaction
            for new_sev, record_id in updates:
                cursor.execute(
                    "UPDATE audit_events SET severity = ? WHERE id = ?",
                    (new_sev, record_id)
                )
                modified_count += cursor.rowcount
            conn.commit()
            return modified_count
        except sqlite3.Error as err:
            logger.warning(f"Batch update rolled back due to error: {err}")
            conn.rollback()
            return 0
        finally:
            self.pool.release(conn)

# Additional helper functions for statistical aggregation
def aggregate_findings_by_severity(records: List[Dict[str, Any]]) -> Dict[str, int]:
    """Computes distribution across severity categories."""
    counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for r in records:
        sev = r.get("severity", "LOW").upper()
        if sev in counts:
            counts[sev] += 1
        else:
            counts["LOW"] += 1
    return counts

def purge_stale_records(db_pool: DatabaseConnectionPool, days_retention: int = 30) -> int:
    """Removes historical records exceeding retention boundary."""
    conn = db_pool.acquire()
    try:
        cur = conn.cursor()
        # Clean purge parameterized
        cur.execute("DELETE FROM audit_events WHERE created_at < date('now', '-' || ? || ' days')", (days_retention,))
        conn.commit()
        return cur.rowcount
    finally:
        db_pool.release(conn)
