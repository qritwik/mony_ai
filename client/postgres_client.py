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
            print("✅ Connected to PostgreSQL successfully (Singleton)")

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

    def insert_or_update(self, table, data, update_column=None):
        """
        Insert or update a row in the table

        Args:
            table (str): Table name
            data (dict): Dictionary of column-value pairs
            update_column (str): Column name to check for conflicts (for updates)

        Returns:
            bool: True if successful
        """
        try:
            self._ensure_connection()

            if not data:
                raise ValueError("Data dictionary cannot be empty")

            columns = list(data.keys())
            values = [data[col] for col in columns]
            columns_sql = ", ".join(columns)
            placeholders = ", ".join(["%s"] * len(values))

            if not update_column or update_column not in data:
                # Simple INSERT
                sql = f"INSERT INTO {table} ({columns_sql}) VALUES ({placeholders})"
                self.cur.execute(sql, values)
                print(f"✅ Inserted row into {table}")
            else:
                # UPSERT using ON CONFLICT (PostgreSQL 9.5+)
                update_columns = [col for col in columns if col != update_column]
                set_clause = ", ".join(
                    [f"{col} = EXCLUDED.{col}" for col in update_columns]
                )

                sql = f"""
                INSERT INTO {table} ({columns_sql}) 
                VALUES ({placeholders})
                ON CONFLICT ({update_column}) 
                DO UPDATE SET {set_clause}
                """

                self.cur.execute(sql, values)
                print(
                    f"✅ Inserted/Updated row in {table} (conflict on {update_column})"
                )

            return True

        except Exception as e:
            print(f"❌ Error in insert_or_update: {e}")
            return False

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
            print("✅ Database connection closed")

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
