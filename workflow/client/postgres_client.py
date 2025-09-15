import psycopg2
from psycopg2.extras import RealDictCursor
import os
import threading


class PostgresClient:
    _instance = None
    _lock = threading.Lock()
    _initialized = False

    def __new__(cls, dsn=None, **kwargs):
        """Ensure only one instance is created (thread-safe singleton)"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(PostgresClient, cls).__new__(cls)
        return cls._instance

    def __init__(self, dsn=None, **kwargs):
        """Initialize connection only once"""
        if not self._initialized:
            with self._lock:
                if not self._initialized:
                    self._initialize_connection(dsn, **kwargs)
                    self._initialized = True

    def _initialize_connection(self, dsn=None, **kwargs):
        """Initialize the database connection"""
        try:
            if dsn:
                self.dsn = dsn
            else:
                # Build DSN from individual parameters
                host = kwargs.get("host", "localhost")
                port = kwargs.get("port", 5432)
                database = kwargs.get("database")
                user = kwargs.get("user")
                password = kwargs.get("password")

                self.dsn = f"host={host} port={port} dbname={database} user={user} password={password}"

            self.conn = psycopg2.connect(self.dsn)
            self.conn.autocommit = True
            self.cur = self.conn.cursor(cursor_factory=RealDictCursor)

        except Exception as e:
            print(f"❌ Failed to connect to PostgreSQL: {e}")
            raise

    def _ensure_connection(self):
        """Ensure connection is alive, reconnect if needed"""
        try:
            # Test connection with a simple query
            self.cur.execute("SELECT 1")
        except (psycopg2.OperationalError, psycopg2.InterfaceError):
            print("🔄 Connection lost, reconnecting...")
            self.conn = psycopg2.connect(self.dsn)
            self.conn.autocommit = True
            self.cur = self.conn.cursor(cursor_factory=RealDictCursor)
            print("✅ Reconnected to PostgreSQL")

    def insert_or_update(self, table, data, conflict_columns=None, pk_column="id"):
        """
        Insert or upsert a row using PostgreSQL ON CONFLICT and return the primary key.

        Args:
            table (str): Table name
            data (dict): Column-value mapping
            conflict_columns (str/list/tuple, optional): Column(s) to handle conflict
            pk_column (str): Primary key column to return (default "id")

        Returns:
            int: The primary key of the inserted/updated row
        """
        try:
            self._ensure_connection()

            if not data:
                raise ValueError("Data dictionary cannot be empty")

            columns = list(data.keys())
            values = [data[col] for col in columns]
            columns_sql = ", ".join(columns)
            placeholders = ", ".join(["%s"] * len(values))

            if not conflict_columns:
                # Simple INSERT with RETURNING
                sql = f"""
                    INSERT INTO {table} ({columns_sql})
                    VALUES ({placeholders})
                    RETURNING {pk_column};
                """
                self.cur.execute(sql, values)
                pk = self.cur.fetchone()[pk_column]
                return pk
            else:
                # Normalize conflict columns
                if isinstance(conflict_columns, (list, tuple)):
                    conflict_cols = list(conflict_columns)
                else:
                    conflict_cols = [str(conflict_columns)]

                update_columns = [c for c in columns if c not in conflict_cols]
                set_clause = (
                    ", ".join([f"{c} = EXCLUDED.{c}" for c in update_columns]) or None
                )
                conflict_target = ", ".join(conflict_cols)

                if set_clause:
                    sql = f"""
                        INSERT INTO {table} ({columns_sql})
                        VALUES ({placeholders})
                        ON CONFLICT ({conflict_target})
                        DO UPDATE SET {set_clause}
                        RETURNING {pk_column};
                    """
                else:
                    # DO NOTHING, still return existing pk
                    # We need a separate query to fetch PK if conflict occurs
                    sql = f"""
                        INSERT INTO {table} ({columns_sql})
                        VALUES ({placeholders})
                        ON CONFLICT ({conflict_target})
                        DO NOTHING
                        RETURNING {pk_column};
                    """

                self.cur.execute(sql, values)
                result = self.cur.fetchone()
                if result:
                    return result[pk_column]
                else:
                    # Conflict happened, fetch existing row's PK
                    conflict_where = " AND ".join([f"{c} = %s" for c in conflict_cols])
                    select_sql = f"SELECT {pk_column} FROM {table} WHERE {conflict_where} LIMIT 1;"
                    self.cur.execute(select_sql, [data[c] for c in conflict_cols])
                    existing = self.cur.fetchone()
                    return existing[pk_column] if existing else None

        except Exception as e:
            print(f"❌ Error in insert_or_update: {e}")
            return None

    def execute_query(self, query, params=None):
        """
        Execute a SQL query and return results

        Args:
            query (str): SQL query string
            params (tuple): Optional parameters for parameterized queries

        Returns:
            list: List of dictionaries for SELECT queries, empty list for others
        """
        try:
            self._ensure_connection()

            if params:
                self.cur.execute(query, params)
            else:
                self.cur.execute(query)

            # Try to fetch results (for SELECT queries)
            try:
                result = self.cur.fetchall()
                # Convert RealDictRow to regular dict for JSON serialization
                return [dict(row) for row in result] if result else []
            except psycopg2.ProgrammingError:
                # No results to fetch (INSERT, UPDATE, DELETE, CREATE, etc.)
                return []

        except Exception as e:
            print(f"❌ Error executing query: {e}")
            print(f"Query: {query}")
            if params:
                print(f"Params: {params}")
            return []

    def close(self):
        """Close database connection"""
        try:
            if hasattr(self, "cur") and self.cur:
                self.cur.close()
            if hasattr(self, "conn") and self.conn:
                self.conn.close()

            # Reset singleton state
            PostgresClient._initialized = False
            PostgresClient._instance = None

        except Exception as e:
            print(f"❌ Error closing connection: {e}")

    @classmethod
    def get_instance(cls, dsn=None, **kwargs):
        """Get the singleton instance (alternative way to instantiate)"""
        return cls(dsn=dsn, **kwargs)

    @classmethod
    def reset_instance(cls):
        """Reset singleton instance (useful for testing)"""
        with cls._lock:
            if cls._instance:
                cls._instance.close()
            cls._instance = None
            cls._initialized = False
