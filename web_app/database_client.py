import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from typing import Optional, Dict
from threading import Lock

load_dotenv()


class UserDB:
    _instance = None
    _lock: Lock = Lock()  # class-level lock for thread safety

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:  # ensure only one thread initializes
                if not cls._instance:  # double-checked locking
                    cls._instance = super(UserDB, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        # Prevent reinitialization on subsequent calls
        if not hasattr(self, "_initialized"):
            self.DB_HOST = os.getenv("DB_HOST")
            self.DB_PORT = os.getenv("DB_PORT")
            self.DB_NAME = os.getenv("DB_NAME")
            self.DB_USER = os.getenv("DB_USER")
            self.DB_PASSWORD = os.getenv("DB_PASSWORD")
            self.conn_string = (
                f"host={self.DB_HOST} port={self.DB_PORT} dbname={self.DB_NAME} "
                f"user={self.DB_USER} password={self.DB_PASSWORD}"
            )
            self._initialized = True  # mark as initialized

    def _get_connection(self):
        return psycopg2.connect(self.conn_string)

    def create_user(
        self, name: str, username: str, password: str, phone: int = None
    ) -> bool:
        """Create a new user account"""
        try:
            # Convert empty phone string to None
            phone = None if not phone else int(phone)

            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO users (name, username, password, phone)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (name, username, password, phone),
                    )
                conn.commit()
                return True
        except psycopg2.IntegrityError:
            conn.rollback()
            return False  # Username already exists

    def authenticate_user(self, username: str, password: str) -> Optional[Dict]:
        """Authenticate user and return user data"""
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(
                    """
                    SELECT * FROM users 
                    WHERE username = %s AND password = %s AND is_active = %s
                """,
                    (username, password, True),
                )
                row = cursor.fetchone()
                return dict(row) if row else None

    def get_user_gmail(self, user_id: int) -> Optional[Dict]:
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(
                    """
                    SELECT gmail_email FROM gmail_credentials 
                    WHERE user_id = %s and is_active = %s
                """,
                    (
                        user_id,
                        True,
                    ),
                )
                row = cursor.fetchone()
                return dict(row) if row else None

    def get_gmail_credential_by_email(self, email) -> Optional[Dict]:
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(
                    """
                    SELECT * FROM gmail_credentials 
                    WHERE gmail_email = %s and is_active = %s
                """,
                    (email, True),
                )
                row = cursor.fetchone()
                return dict(row) if row else None

    def create_gmail_credential(self, user_id, email, access_token, refresh_token):
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO gmail_credentials (user_id, gmail_email, access_token, refresh_token)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (
                            user_id,
                            email,
                            access_token,
                            refresh_token,
                        ),
                    )
                conn.commit()
                return True
        except psycopg2.IntegrityError:
            conn.rollback()
            raise

    def create_workflow(self, user_id):
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO workflow (user_id, is_active)
                        VALUES (%s, %s)
                        """,
                        (
                            user_id,
                            True,
                        ),
                    )
                conn.commit()
                return True
        except psycopg2.IntegrityError:
            conn.rollback()
            raise

    def get_user_workflow(self, user_id) -> Optional[Dict]:
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(
                    """
                    SELECT created_at FROM workflow 
                    WHERE user_id = %s and is_active = %s
                """,
                    (
                        user_id,
                        True,
                    ),
                )
                row = cursor.fetchone()
                return dict(row) if row else None

    def get_user_id(self, username: str) -> Optional[Dict]:
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(
                    """
                    SELECT id FROM users 
                    WHERE username = %s AND is_active = %s
                """,
                    (
                        username,
                        True,
                    ),
                )
                row = cursor.fetchone()
                return dict(row).get("id") if row else None

    def add_default_transaction_categories(self, user_id):
        transaction_categories = [
            "Food & Dining",
            "Transportation",
            "Shopping & Lifestyle",
            "Bills & Utilities",
            "Healthcare & Wellness",
            "Others",
        ]
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    for category in transaction_categories:
                        cursor.execute(
                            """
                            INSERT INTO transaction_category (user_id, category)
                            VALUES (%s, %s)
                            ON CONFLICT (user_id, category) DO NOTHING
                            """,
                            (user_id, category),
                        )
                conn.commit()
                return True
        except Exception as e:
            print(f"❌ Error inserting default categories: {e}")
            raise

    def get_transaction_categories(self, user_id) -> list[str]:
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(
                    """
                    SELECT id, category 
                    FROM transaction_category 
                    WHERE user_id = %s AND is_active = %s
                    """,
                    (user_id, True),
                )
                rows = cursor.fetchall()
                return [dict(row).get("category") for row in rows] if rows else []

    def create_transaction_category(self, user_id, category):
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO transaction_category (user_id, category)
                        VALUES (%s, %s)
                        ON CONFLICT (user_id, category) DO NOTHING
                        """,
                        (user_id, category),
                    )
                conn.commit()
                return True
        except psycopg2.IntegrityError:
            conn.rollback()
            raise

    def delete_transaction_category(self, user_id, category):
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        DELETE FROM transaction_category
                        WHERE user_id = %s AND category = %s
                        """,
                        (user_id, category),
                    )
                conn.commit()
                return (
                    cursor.rowcount > 0
                )  # ✅ True if a row was deleted, False otherwise
        except Exception as e:
            conn.rollback()
            print(f"❌ Error deleting transaction category: {e}")
            raise

    def delete_gmail_credential(self, user_id):
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        DELETE FROM gmail_credentials
                        WHERE user_id = %s
                        """,
                        (user_id,),
                    )
                conn.commit()
                return (
                    cursor.rowcount > 0
                )  # ✅ True if a row was deleted, False otherwise
        except Exception as e:
            conn.rollback()
            print(f"❌ Error deleting user gmail credentials: {e}")
            raise

    def delete_workflow(self, user_id):
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        DELETE FROM workflow
                        WHERE user_id = %s
                        """,
                        (user_id,),
                    )
                conn.commit()
                return (
                    cursor.rowcount > 0
                )  # ✅ True if a row was deleted, False otherwise
        except Exception as e:
            conn.rollback()
            print(f"❌ Error deleting user workflow: {e}")
            raise

    def get_telegram_info(self, user_id: int) -> Optional[Dict]:
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(
                    """
                    SELECT * FROM user_telegram
                    WHERE user_id = %s
                """,
                    (user_id,),
                )
                row = cursor.fetchone()
                return dict(row) if row else None

    def get_user_transactions(self, user_id: int):
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(
                    """
                    SELECT * FROM user_transactions
                    WHERE user_id = %s
                """,
                    (user_id,),
                )
                rows = cursor.fetchall()
                return [dict(row) for row in rows] if rows else []


if __name__ == "__main__":
    db = UserDB()
    t = db.get_user_transactions(11)
    print(t)
    # user_gmail = db.get_user_gmail(user_id=user_id)
    # user_workflow = db.get_user_workflow(user_id=user_id)
    # # data = db.get_transaction_categories(user_id=3)
    # print(user_gmail)
    # print(user_workflow)

    # user = db.authenticate_user("qritwik", "123456")
    # print(user)
