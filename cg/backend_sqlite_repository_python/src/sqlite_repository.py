"""Generic SQLite repository: get, save, delete, find_by over a typed table."""
import sqlite3
from typing import Any, Dict, List, Optional, Type, TypeVar

T = TypeVar("T")


class Repository:
    """CRUD operations for a single SQLite table backed by plain dicts or dataclasses.

    Rows are stored and returned as ``dict[str, Any]`` by default. If a
    *model* class is supplied, rows are constructed via ``model(**row_dict)``
    and returned as instances of that class.

    Parameters
    ----------
    conn:
        An open :class:`sqlite3.Connection` with ``row_factory`` set to
        :class:`sqlite3.Row`.
    table:
        Name of the target table.
    pk:
        Name of the primary key column. Default ``'id'``.
    model:
        Optional class to instantiate for each row. Must accept column names
        as keyword arguments (e.g. a ``dataclass``). Default ``None``
        (returns plain dicts).

    Examples
    --------
    >>> import sqlite3
    >>> conn = sqlite3.connect(':memory:')
    >>> conn.row_factory = sqlite3.Row
    >>> conn.execute('CREATE TABLE notes (id INTEGER PRIMARY KEY, body TEXT)')
    <...>
    >>> repo = Repository(conn, 'notes')
    >>> repo.save({'body': 'hello'})
    1
    >>> repo.get(1)
    {'id': 1, 'body': 'hello'}
    """

    def __init__(
        self,
        conn: sqlite3.Connection,
        table: str,
        pk: str = "id",
        model: Optional[Type] = None,
    ) -> None:
        self._conn = conn
        self._table = table
        self._pk = pk
        self._model = model

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, pk_value: Any) -> Optional[Any]:
        """Fetch a single row by primary key.

        Parameters
        ----------
        pk_value:
            Value of the primary key column.

        Returns
        -------
        dict or model instance, or ``None`` if not found.
        """
        sql = f"SELECT * FROM {self._table} WHERE {self._pk} = ?"
        row = self._conn.execute(sql, (pk_value,)).fetchone()
        return self._to_obj(row) if row is not None else None

    def all(self) -> List[Any]:
        """Return every row in the table.

        Returns
        -------
        List of dicts or model instances.
        """
        rows = self._conn.execute(f"SELECT * FROM {self._table}").fetchall()
        return [self._to_obj(r) for r in rows]

    def find_by(self, **kwargs: Any) -> List[Any]:
        """Return rows matching all supplied column=value filters (ANDed).

        Parameters
        ----------
        **kwargs:
            Column names and their required values.

        Returns
        -------
        List of dicts or model instances.

        Raises
        ------
        ValueError
            If no filter columns are supplied.
        """
        if not kwargs:
            raise ValueError("find_by requires at least one keyword argument")
        clauses = " AND ".join(f"{col} = ?" for col in kwargs)
        sql = f"SELECT * FROM {self._table} WHERE {clauses}"
        rows = self._conn.execute(sql, tuple(kwargs.values())).fetchall()
        return [self._to_obj(r) for r in rows]

    def save(self, obj: Any) -> Any:
        """Insert or update a row.

        If the object has no primary key value (or its PK is ``None``), an
        INSERT is performed and the new row ID is returned. Otherwise an
        ``INSERT OR REPLACE`` upserts the row.

        Parameters
        ----------
        obj:
            A dict or model instance. For a model, attributes matching column
            names are read via ``vars(obj)`` or the object's ``__dict__``.

        Returns
        -------
        Any
            The primary key value of the inserted/replaced row.
        """
        data = self._to_dict(obj)
        pk_val = data.get(self._pk)

        if pk_val is None:
            # INSERT — let the DB assign the PK
            data.pop(self._pk, None)
            columns = list(data.keys())
            placeholders = ", ".join("?" * len(columns))
            col_list = ", ".join(columns)
            sql = f"INSERT INTO {self._table} ({col_list}) VALUES ({placeholders})"
            cursor = self._conn.execute(sql, tuple(data.values()))
            return cursor.lastrowid
        else:
            columns = list(data.keys())
            placeholders = ", ".join("?" * len(columns))
            col_list = ", ".join(columns)
            sql = f"INSERT OR REPLACE INTO {self._table} ({col_list}) VALUES ({placeholders})"
            self._conn.execute(sql, tuple(data.values()))
            return pk_val

    def delete(self, pk_value: Any) -> bool:
        """Delete the row with the given primary key.

        Parameters
        ----------
        pk_value:
            Value of the primary key column.

        Returns
        -------
        bool
            ``True`` if a row was deleted, ``False`` if it did not exist.
        """
        sql = f"DELETE FROM {self._table} WHERE {self._pk} = ?"
        cursor = self._conn.execute(sql, (pk_value,))
        return cursor.rowcount > 0

    def count(self) -> int:
        """Return the total number of rows in the table.

        Returns
        -------
        int
        """
        row = self._conn.execute(f"SELECT COUNT(*) FROM {self._table}").fetchone()
        return row[0]

    def exists(self, pk_value: Any) -> bool:
        """Return ``True`` if a row with *pk_value* exists.

        Parameters
        ----------
        pk_value:
            Value of the primary key column.
        """
        sql = f"SELECT 1 FROM {self._table} WHERE {self._pk} = ? LIMIT 1"
        return self._conn.execute(sql, (pk_value,)).fetchone() is not None

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _to_dict(self, obj: Any) -> Dict[str, Any]:
        if isinstance(obj, dict):
            return dict(obj)
        if hasattr(obj, "__dict__"):
            return {k: v for k, v in vars(obj).items() if not k.startswith("_")}
        raise TypeError(f"Cannot convert {type(obj)} to dict")

    def _to_obj(self, row: sqlite3.Row) -> Any:
        d = dict(row)
        if self._model is not None:
            return self._model(**d)
        return d
