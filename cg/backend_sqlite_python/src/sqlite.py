"""SQLite utilities: connection management, bulk insert, migration, and query helpers."""
import sqlite3
from contextlib import contextmanager
from typing import Any, Dict, Generator, List, Optional, Sequence, Tuple


@contextmanager
def connect(
    path: str,
    wal: bool = True,
    foreign_keys: bool = True,
    timeout: float = 5.0,
) -> Generator[sqlite3.Connection, None, None]:
    """Open a SQLite connection with sensible defaults and auto commit/rollback.

    Parameters
    ----------
    path:
        Path to the SQLite database file, or ``':memory:'``.
    wal:
        Enable WAL journal mode for better concurrent read performance.
        Default ``True``.
    foreign_keys:
        Enforce foreign key constraints. Default ``True``.
    timeout:
        Seconds to wait for a locked database before raising. Default 5.0.

    Yields
    ------
    sqlite3.Connection
        Connection with ``row_factory`` set to :class:`sqlite3.Row` so rows
        behave like dicts.

    Examples
    --------
    >>> with connect(':memory:') as conn:
    ...     conn.execute('CREATE TABLE t (x INTEGER)')
    ...     conn.execute('INSERT INTO t VALUES (1)')
    ...     row = conn.execute('SELECT x FROM t').fetchone()
    ...     assert row['x'] == 1
    """
    conn = sqlite3.connect(path, timeout=timeout)
    conn.row_factory = sqlite3.Row
    try:
        if wal:
            conn.execute("PRAGMA journal_mode=WAL")
        if foreign_keys:
            conn.execute("PRAGMA foreign_keys=ON")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def query_all(
    conn: sqlite3.Connection,
    sql: str,
    params: Sequence = (),
) -> List[Dict[str, Any]]:
    """Execute *sql* and return all rows as a list of plain dicts.

    Parameters
    ----------
    conn:
        An open :class:`sqlite3.Connection`.
    sql:
        SQL query string. Use ``?`` placeholders for parameters.
    params:
        Sequence of values bound to the query placeholders. Default ``()``.

    Returns
    -------
    List[Dict[str, Any]]
        Each row as a ``{column: value}`` dict. Empty list if no rows.
    """
    cursor = conn.execute(sql, params)
    rows = cursor.fetchall()
    return [dict(row) for row in rows]


def query_one(
    conn: sqlite3.Connection,
    sql: str,
    params: Sequence = (),
) -> Optional[Dict[str, Any]]:
    """Execute *sql* and return the first row as a dict, or ``None``.

    Parameters
    ----------
    conn:
        An open :class:`sqlite3.Connection`.
    sql:
        SQL query string. Use ``?`` placeholders for parameters.
    params:
        Sequence of values bound to the query placeholders.

    Returns
    -------
    Optional[Dict[str, Any]]
        First row as a ``{column: value}`` dict, or ``None`` if no rows.
    """
    cursor = conn.execute(sql, params)
    row = cursor.fetchone()
    return dict(row) if row is not None else None


def bulk_insert(
    conn: sqlite3.Connection,
    table: str,
    rows: List[Dict[str, Any]],
    on_conflict: str = "IGNORE",
) -> int:
    """Insert multiple rows into *table* in a single transaction.

    Parameters
    ----------
    conn:
        An open :class:`sqlite3.Connection`.
    table:
        Target table name.
    rows:
        List of ``{column: value}`` dicts. All dicts must have the same keys.
    on_conflict:
        SQLite conflict resolution: ``'IGNORE'``, ``'REPLACE'``, or
        ``'ABORT'``. Default ``'IGNORE'``.

    Returns
    -------
    int
        Number of rows actually inserted (``cursor.rowcount`` total).

    Raises
    ------
    ValueError
        If *rows* is empty or *on_conflict* is not a recognised keyword.
    """
    if not rows:
        raise ValueError("rows must not be empty")
    valid_conflicts = {"IGNORE", "REPLACE", "ABORT"}
    if on_conflict.upper() not in valid_conflicts:
        raise ValueError(f"on_conflict must be one of {valid_conflicts}")

    columns = list(rows[0].keys())
    placeholders = ", ".join("?" * len(columns))
    col_list = ", ".join(columns)
    sql = f"INSERT OR {on_conflict.upper()} INTO {table} ({col_list}) VALUES ({placeholders})"
    values = [tuple(row[c] for c in columns) for row in rows]
    cursor = conn.executemany(sql, values)
    return cursor.rowcount


def migrate(
    conn: sqlite3.Connection,
    migrations: List[Tuple[int, str]],
    version_table: str = "_schema_version",
) -> int:
    """Apply pending SQL migrations tracked by a version table.

    Each migration is a ``(version, sql)`` tuple. Migrations whose version
    number is already recorded in *version_table* are skipped. Applied in
    ascending version order regardless of list order.

    Parameters
    ----------
    conn:
        An open :class:`sqlite3.Connection`.
    migrations:
        List of ``(version, sql)`` tuples. *version* must be a positive int.
        *sql* may contain multiple statements separated by ``;``.
    version_table:
        Name of the table used to track applied versions. Created
        automatically on first use. Default ``'_schema_version'``.

    Returns
    -------
    int
        Number of migrations applied in this call.

    Examples
    --------
    >>> with connect(':memory:') as conn:
    ...     applied = migrate(conn, [
    ...         (1, 'CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)'),
    ...         (2, 'ALTER TABLE users ADD COLUMN email TEXT'),
    ...     ])
    ...     assert applied == 2
    """
    conn.execute(
        f"CREATE TABLE IF NOT EXISTS {version_table} "
        f"(version INTEGER PRIMARY KEY)"
    )
    applied_rows = conn.execute(f"SELECT version FROM {version_table}").fetchall()
    applied = {row[0] for row in applied_rows}

    pending = sorted(
        [(v, sql) for v, sql in migrations if v not in applied],
        key=lambda x: x[0],
    )

    for version, sql in pending:
        conn.executescript(sql)
        conn.execute(f"INSERT INTO {version_table} (version) VALUES (?)", (version,))

    return len(pending)
