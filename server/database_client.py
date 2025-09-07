import os
import psycopg2
from dotenv import load_dotenv
import psycopg2.extras
from typing import Optional, Dict, List


class UserDB:
    def __init__(self):
        self.DB_HOST = os.getenv("DB_HOST")
        self.DB_PORT = os.getenv("DB_PORT")
        self.DB_NAME = os.getenv("DB_NAME")
        self.DB_USER = os.getenv("DB_USER")
        self.DB_PASSWORD = os.getenv("DB_PASSWORD")
        self.conn_string = f"host={self.DB_HOST} port={self.DB_PORT} dbname={self.DB_NAME} user={self.DB_USER} password={self.DB_PASSWORD}"

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
                    WHERE username = %s AND password = %s
                """,
                    (username, password),
                )
                row = cursor.fetchone()
                return dict(row) if row else None
