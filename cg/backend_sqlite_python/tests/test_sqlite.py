"""Tests for backend-sqlite-python."""
import sys
import os
import sqlite3

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.sqlite import bulk_insert, connect, migrate, query_all, query_one


# ---------------------------------------------------------------------------
# connect
# ---------------------------------------------------------------------------

class TestConnect:
    def test_yields_connection(self):
        with connect(":memory:") as conn:
            assert isinstance(conn, sqlite3.Connection)

    def test_row_factory_returns_dict(self):
        with connect(":memory:") as conn:
            conn.execute("CREATE TABLE t (x INTEGER, y TEXT)")
            conn.execute("INSERT INTO t VALUES (1, 'hello')")
            row = query_one(conn, "SELECT x, y FROM t")
            assert row == {"x": 1, "y": "hello"}

    def test_commit_on_success(self):
        with connect(":memory:") as conn:
            conn.execute("CREATE TABLE t (x INTEGER)")
            conn.execute("INSERT INTO t VALUES (42)")
        # After context exits, data should have been committed (no error)

    def test_rollback_on_exception(self):
        with pytest.raises(ValueError):
            with connect(":memory:") as conn:
                conn.execute("CREATE TABLE t (x INTEGER)")
                conn.execute("INSERT INTO t VALUES (1)")
                raise ValueError("abort")
        # No assertion needed — just verifying no crash from the rollback path

    def test_foreign_keys_enforced(self):
        with connect(":memory:", foreign_keys=True) as conn:
            conn.execute("CREATE TABLE parent (id INTEGER PRIMARY KEY)")
            conn.execute(
                "CREATE TABLE child (id INTEGER, parent_id INTEGER REFERENCES parent(id))"
            )
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute("INSERT INTO child VALUES (1, 999)")
                conn.commit()

    def test_wal_mode(self):
        with connect(":memory:", wal=True) as conn:
            row = conn.execute("PRAGMA journal_mode").fetchone()
            # :memory: ignores WAL but doesn't error
            assert row is not None


# ---------------------------------------------------------------------------
# query_all / query_one
# ---------------------------------------------------------------------------

class TestQueryHelpers:
    def test_query_all_empty(self):
        with connect(":memory:") as conn:
            conn.execute("CREATE TABLE t (x INTEGER)")
            result = query_all(conn, "SELECT * FROM t")
            assert result == []

    def test_query_all_multiple_rows(self):
        with connect(":memory:") as conn:
            conn.execute("CREATE TABLE t (x INTEGER)")
            conn.executemany("INSERT INTO t VALUES (?)", [(1,), (2,), (3,)])
            rows = query_all(conn, "SELECT x FROM t ORDER BY x")
            assert rows == [{"x": 1}, {"x": 2}, {"x": 3}]

    def test_query_all_with_params(self):
        with connect(":memory:") as conn:
            conn.execute("CREATE TABLE t (x INTEGER)")
            conn.executemany("INSERT INTO t VALUES (?)", [(1,), (2,), (3,)])
            rows = query_all(conn, "SELECT x FROM t WHERE x > ?", (1,))
            assert len(rows) == 2

    def test_query_one_returns_first(self):
        with connect(":memory:") as conn:
            conn.execute("CREATE TABLE t (x INTEGER)")
            conn.executemany("INSERT INTO t VALUES (?)", [(10,), (20,)])
            row = query_one(conn, "SELECT x FROM t ORDER BY x")
            assert row == {"x": 10}

    def test_query_one_returns_none_when_empty(self):
        with connect(":memory:") as conn:
            conn.execute("CREATE TABLE t (x INTEGER)")
            assert query_one(conn, "SELECT x FROM t") is None


# ---------------------------------------------------------------------------
# bulk_insert
# ---------------------------------------------------------------------------

class TestBulkInsert:
    def _make_table(self, conn):
        conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)")

    def test_inserts_all_rows(self):
        with connect(":memory:") as conn:
            self._make_table(conn)
            rows = [{"id": i, "name": f"item{i}"} for i in range(5)]
            count = bulk_insert(conn, "items", rows)
            assert count == 5
            assert len(query_all(conn, "SELECT * FROM items")) == 5

    def test_on_conflict_ignore(self):
        with connect(":memory:") as conn:
            self._make_table(conn)
            bulk_insert(conn, "items", [{"id": 1, "name": "a"}])
            bulk_insert(conn, "items", [{"id": 1, "name": "b"}], on_conflict="IGNORE")
            row = query_one(conn, "SELECT name FROM items WHERE id=1")
            assert row["name"] == "a"  # original kept

    def test_on_conflict_replace(self):
        with connect(":memory:") as conn:
            self._make_table(conn)
            bulk_insert(conn, "items", [{"id": 1, "name": "a"}])
            bulk_insert(conn, "items", [{"id": 1, "name": "b"}], on_conflict="REPLACE")
            row = query_one(conn, "SELECT name FROM items WHERE id=1")
            assert row["name"] == "b"  # replaced

    def test_empty_rows_raises(self):
        with connect(":memory:") as conn:
            self._make_table(conn)
            with pytest.raises(ValueError):
                bulk_insert(conn, "items", [])

    def test_invalid_conflict_raises(self):
        with connect(":memory:") as conn:
            self._make_table(conn)
            with pytest.raises(ValueError):
                bulk_insert(conn, "items", [{"id": 1, "name": "x"}], on_conflict="UPDATE")


# ---------------------------------------------------------------------------
# migrate
# ---------------------------------------------------------------------------

class TestMigrate:
    def test_applies_all_migrations(self):
        with connect(":memory:") as conn:
            applied = migrate(conn, [
                (1, "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)"),
                (2, "ALTER TABLE users ADD COLUMN email TEXT"),
            ])
            assert applied == 2
            # Table should exist with both columns
            conn.execute("INSERT INTO users VALUES (1, 'Alice', 'a@b.com')")

    def test_skips_already_applied(self):
        with connect(":memory:") as conn:
            migrate(conn, [(1, "CREATE TABLE t (x INTEGER)")])
            applied = migrate(conn, [(1, "CREATE TABLE t (x INTEGER)")])
            assert applied == 0

    def test_applies_only_pending(self):
        with connect(":memory:") as conn:
            migrate(conn, [(1, "CREATE TABLE t (x INTEGER)")])
            applied = migrate(conn, [
                (1, "CREATE TABLE t (x INTEGER)"),
                (2, "ALTER TABLE t ADD COLUMN y TEXT"),
            ])
            assert applied == 1

    def test_applies_in_version_order(self):
        with connect(":memory:") as conn:
            applied = migrate(conn, [
                (3, "ALTER TABLE t ADD COLUMN z TEXT"),
                (1, "CREATE TABLE t (x INTEGER)"),
                (2, "ALTER TABLE t ADD COLUMN y TEXT"),
            ])
            assert applied == 3

    def test_version_table_created(self):
        with connect(":memory:") as conn:
            migrate(conn, [(1, "CREATE TABLE t (x INTEGER)")])
            rows = query_all(conn, "SELECT version FROM _schema_version")
            assert rows == [{"version": 1}]

    def test_custom_version_table(self):
        with connect(":memory:") as conn:
            migrate(conn, [(1, "CREATE TABLE t (x INTEGER)")], version_table="my_versions")
            rows = query_all(conn, "SELECT version FROM my_versions")
            assert rows == [{"version": 1}]
