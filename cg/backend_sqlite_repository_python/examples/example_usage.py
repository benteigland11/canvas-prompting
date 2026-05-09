"""
Example usage of backend-sqlite-repository-python.

Runs and exits cleanly — no user input, no network calls, no external deps.
"""
import sys
import os
import sqlite3
from dataclasses import dataclass
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.sqlite_repository import Repository

conn = sqlite3.connect(":memory:")
conn.row_factory = sqlite3.Row
conn.execute("CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT, price REAL, category TEXT)")

repo = Repository(conn, "products")

# ── save (insert without pk) ─────────────────────────────────────────────────
pk1 = repo.save({"name": "Widget A", "price": 9.99,  "category": "widget"})
pk2 = repo.save({"name": "Widget B", "price": 14.99, "category": "widget"})
pk3 = repo.save({"name": "Gadget X", "price": 49.99, "category": "gadget"})
assert repo.count() == 3

# ── get ───────────────────────────────────────────────────────────────────────
row = repo.get(pk1)
assert row["name"] == "Widget A"
assert repo.get(9999) is None

# ── exists ────────────────────────────────────────────────────────────────────
assert repo.exists(pk1) is True
assert repo.exists(9999) is False

# ── find_by ───────────────────────────────────────────────────────────────────
widgets = repo.find_by(category="widget")
assert len(widgets) == 2

specific = repo.find_by(category="widget", name="Widget A")
assert len(specific) == 1

# ── upsert (save with pk) ─────────────────────────────────────────────────────
repo.save({"id": pk1, "name": "Widget A Pro", "price": 19.99, "category": "widget"})
assert repo.get(pk1)["name"] == "Widget A Pro"
assert repo.count() == 3  # no new row created

# ── delete ────────────────────────────────────────────────────────────────────
assert repo.delete(pk3) is True
assert repo.count() == 2
assert repo.delete(9999) is False

# ── all ───────────────────────────────────────────────────────────────────────
all_rows = repo.all()
assert len(all_rows) == 2

# ── dataclass model ───────────────────────────────────────────────────────────
@dataclass
class Product:
    id: Optional[int]
    name: str
    price: float
    category: str

typed_repo = Repository(conn, "products", model=Product)
products = typed_repo.all()
assert all(isinstance(p, Product) for p in products)
assert products[0].name == "Widget A Pro"
