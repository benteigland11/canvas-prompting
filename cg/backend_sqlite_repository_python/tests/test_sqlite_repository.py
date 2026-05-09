"""Tests for backend-sqlite-repository-python."""
import sys
import os
import sqlite3
from dataclasses import dataclass
from typing import Optional

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.sqlite_repository import Repository


def make_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, email TEXT)"
    )
    return conn


@dataclass
class User:
    id: Optional[int]
    name: str
    email: str


class TestGet:
    def test_returns_row_as_dict(self):
        conn = make_conn()
        conn.execute("INSERT INTO users VALUES (1, 'Alice', 'alice@example.com')")
        repo = Repository(conn, "users")
        row = repo.get(1)
        assert row == {"id": 1, "name": "Alice", "email": "alice@example.com"}

    def test_returns_none_for_missing(self):
        conn = make_conn()
        repo = Repository(conn, "users")
        assert repo.get(999) is None

    def test_returns_model_instance(self):
        conn = make_conn()
        conn.execute("INSERT INTO users VALUES (1, 'Bob', 'bob@example.com')")
        repo = Repository(conn, "users", model=User)
        user = repo.get(1)
        assert isinstance(user, User)
        assert user.name == "Bob"


class TestAll:
    def test_empty_table(self):
        conn = make_conn()
        assert Repository(conn, "users").all() == []

    def test_returns_all_rows(self):
        conn = make_conn()
        conn.executemany(
            "INSERT INTO users VALUES (?, ?, ?)",
            [(1, "Alice", "a@b.com"), (2, "Bob", "b@b.com")],
        )
        rows = Repository(conn, "users").all()
        assert len(rows) == 2


class TestFindBy:
    def test_single_filter(self):
        conn = make_conn()
        conn.executemany(
            "INSERT INTO users VALUES (?, ?, ?)",
            [(1, "Alice", "a@b.com"), (2, "Alice", "aa@b.com"), (3, "Bob", "b@b.com")],
        )
        rows = Repository(conn, "users").find_by(name="Alice")
        assert len(rows) == 2
        assert all(r["name"] == "Alice" for r in rows)

    def test_multiple_filters(self):
        conn = make_conn()
        conn.executemany(
            "INSERT INTO users VALUES (?, ?, ?)",
            [(1, "Alice", "a@b.com"), (2, "Alice", "other@b.com")],
        )
        rows = Repository(conn, "users").find_by(name="Alice", email="a@b.com")
        assert len(rows) == 1

    def test_no_kwargs_raises(self):
        conn = make_conn()
        with pytest.raises(ValueError):
            Repository(conn, "users").find_by()

    def test_no_matches_returns_empty(self):
        conn = make_conn()
        assert Repository(conn, "users").find_by(name="Nobody") == []


class TestSave:
    def test_insert_without_pk(self):
        conn = make_conn()
        repo = Repository(conn, "users")
        pk = repo.save({"name": "Alice", "email": "a@b.com"})
        assert pk == 1
        assert repo.get(1)["name"] == "Alice"

    def test_insert_assigns_incrementing_pks(self):
        conn = make_conn()
        repo = Repository(conn, "users")
        pk1 = repo.save({"name": "Alice", "email": "a@b.com"})
        pk2 = repo.save({"name": "Bob", "email": "b@b.com"})
        assert pk2 > pk1

    def test_upsert_with_pk(self):
        conn = make_conn()
        repo = Repository(conn, "users")
        repo.save({"id": 1, "name": "Alice", "email": "a@b.com"})
        repo.save({"id": 1, "name": "Alice Updated", "email": "a@b.com"})
        assert repo.get(1)["name"] == "Alice Updated"

    def test_save_dataclass(self):
        conn = make_conn()
        repo = Repository(conn, "users", model=User)
        user = User(id=None, name="Carol", email="c@b.com")
        pk = repo.save(user)
        assert pk is not None
        fetched = repo.get(pk)
        assert isinstance(fetched, User)
        assert fetched.name == "Carol"


class TestDelete:
    def test_delete_existing(self):
        conn = make_conn()
        conn.execute("INSERT INTO users VALUES (1, 'Alice', 'a@b.com')")
        repo = Repository(conn, "users")
        assert repo.delete(1) is True
        assert repo.get(1) is None

    def test_delete_nonexistent(self):
        conn = make_conn()
        assert Repository(conn, "users").delete(999) is False


class TestCountExists:
    def test_count_empty(self):
        conn = make_conn()
        assert Repository(conn, "users").count() == 0

    def test_count_after_inserts(self):
        conn = make_conn()
        conn.executemany(
            "INSERT INTO users VALUES (?, ?, ?)",
            [(1, "A", "a@b.com"), (2, "B", "b@b.com")],
        )
        assert Repository(conn, "users").count() == 2

    def test_exists_true(self):
        conn = make_conn()
        conn.execute("INSERT INTO users VALUES (1, 'Alice', 'a@b.com')")
        assert Repository(conn, "users").exists(1) is True

    def test_exists_false(self):
        conn = make_conn()
        assert Repository(conn, "users").exists(999) is False
