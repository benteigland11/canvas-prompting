"""
Example usage of backend-sqlite-python.

Runs and exits cleanly — no user input, no network calls, no external deps.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.sqlite import bulk_insert, connect, migrate, query_all, query_one

with connect(":memory:") as conn:
    # ── migrations ────────────────────────────────────────────────────────────
    applied = migrate(conn, [
        (1, "CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT, price REAL)"),
        (2, "CREATE TABLE orders (id INTEGER PRIMARY KEY, product_id INTEGER, qty INTEGER)"),
    ])
    assert applied == 2

    # re-running the same migrations is a no-op
    assert migrate(conn, [(1, "...")]) == 0

    # ── bulk insert ───────────────────────────────────────────────────────────
    products = [
        {"id": 1, "name": "Widget A", "price": 9.99},
        {"id": 2, "name": "Widget B", "price": 14.99},
        {"id": 3, "name": "Gadget X", "price": 49.99},
    ]
    bulk_insert(conn, "products", products)

    # inserting the same IDs is silently ignored
    bulk_insert(conn, "products", [{"id": 1, "name": "Duplicate", "price": 0.0}])

    # ── query helpers ─────────────────────────────────────────────────────────
    all_products = query_all(conn, "SELECT * FROM products ORDER BY price")
    assert len(all_products) == 3
    assert all_products[0]["name"] == "Widget A"

    cheap = query_all(conn, "SELECT * FROM products WHERE price < ?", (20.0,))
    assert len(cheap) == 2

    one = query_one(conn, "SELECT name FROM products WHERE id = ?", (3,))
    assert one == {"name": "Gadget X"}

    missing = query_one(conn, "SELECT * FROM products WHERE id = ?", (999,))
    assert missing is None
