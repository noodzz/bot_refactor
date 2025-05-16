import sqlite3
import os
from typing import List, Dict, Any, Optional, Tuple, Union
import logging

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Менеджер для работы с базой данных SQLite"""

    def __init__(self, db_path: str):
        """
        Инициализирует менеджер базы данных

        Args:
            db_path: Путь к файлу базы данных
        """
        self.db_path = db_path
        self.connection = None
        self.cursor = None
        # Проверяем существование директории
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)

    def connect(self) -> None:
        """Устанавливает соединение с базой данных"""
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
        self.cursor = self.connection.cursor()

    def close(self) -> None:
        """Закрывает соединение с базой данных"""
        if self.connection:
            self.connection.close()
            self.connection = None
            self.cursor = None

    def init_db(self) -> None:
        """Инициализирует базу данных и создает таблицы, если их нет"""
        connection = self._get_connection()
        cursor = connection.cursor()

        # Создаем таблицы
        cursor.executescript('''
         -- Таблица пользователей
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            name TEXT,
            is_admin BOOLEAN DEFAULT 0,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        -- Таблица сотрудников
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            position TEXT NOT NULL,
            days_off TEXT NOT NULL
        );

        -- Таблица проектов
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            start_date TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            user_id INTEGER,
            FOREIGN KEY (user_id) REFERENCES users (id)
        );

        -- Таблица задач
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            parent_id INTEGER DEFAULT NULL,
            name TEXT NOT NULL,
            duration INTEGER NOT NULL,
            is_group BOOLEAN DEFAULT 0,
            parallel BOOLEAN DEFAULT 0,
            start_date TEXT DEFAULT NULL,
            end_date TEXT DEFAULT NULL,
            employee_id INTEGER DEFAULT NULL,
            position TEXT DEFAULT NULL,
            predecessors TEXT DEFAULT NULL,
            working_duration INTEGER DEFAULT NULL,
            FOREIGN KEY (project_id) REFERENCES projects (id),
            FOREIGN KEY (parent_id) REFERENCES tasks (id),
            FOREIGN KEY (employee_id) REFERENCES employees (id)
        );

        -- Таблица зависимостей между задачами
        CREATE TABLE IF NOT EXISTS dependencies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            predecessor_id INTEGER NOT NULL,
            FOREIGN KEY (task_id) REFERENCES tasks (id),
            FOREIGN KEY (predecessor_id) REFERENCES tasks (id)
        );
        ''')

        connection.commit()
        connection.close()

    def _get_connection(self) -> sqlite3.Connection:
        """
        Создает новое соединение с базой данных

        Returns:
            sqlite3.Connection: Новое соединение
        """
        connection = sqlite3.connect(self.db_path, timeout=30.0)  # Увеличиваем timeout
        connection.row_factory = sqlite3.Row
        return connection

    def execute(self, query: str, params: Optional[Union[Tuple, Dict[str, Any]]] = None) -> List[sqlite3.Row]:
        """
        Выполняет SQL-запрос

        Args:
            query: SQL-запрос
            params: Параметры запроса

        Returns:
            List[sqlite3.Row]: Результат выполнения запроса
        """
        result = []
        self.connect()

        try:
            if params:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)

            self.connection.commit()

            try:
                result = self.cursor.fetchall()
            except sqlite3.Error:
                # Нет результатов
                pass

        except Exception as e:
            if self.connection:
                self.connection.rollback()
            logger.error(f"SQL Error: {e} in query: {query}")
            raise
        finally:
            self.close()

        return result

    def get_last_inserted_id(self) -> int:
        """
        Возвращает ID последней добавленной записи

        Returns:
            int: ID записи или 0, если произошла ошибка
        """
        self.connect()
        try:
            self.cursor.execute("SELECT last_insert_rowid()")
            result = self.cursor.fetchone()
            return result[0] if result else 0
        finally:
            self.close()

    def execute_transaction(self, queries_with_params: List[Tuple[str, Optional[Tuple]]]) -> List[List[sqlite3.Row]]:
        """
        Выполняет несколько запросов в рамках одной транзакции

        Args:
            queries_with_params: Список кортежей (запрос, параметры)

        Returns:
            List[List[sqlite3.Row]]: Список результатов для каждого запроса
        """
        connection = None
        cursor = None

        try:
            connection = self._get_connection()
            cursor = connection.cursor()

            results = []
            for query, params in queries_with_params:
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)

                try:
                    results.append(cursor.fetchall())
                except sqlite3.Error:
                    results.append([])

            connection.commit()
            return results
        except Exception as e:
            if connection:
                try:
                    connection.rollback()
                except Exception as rollback_error:
                    logger.error(f"Ошибка при откате транзакции: {rollback_error}")
            logger.error(f"Ошибка SQL при выполнении транзакции: {e}")
            raise
        finally:
            if connection:
                try:
                    connection.close()
                except Exception as close_error:
                    logger.error(f"Ошибка при закрытии соединения с БД: {close_error}")

    def execute_many(self, query: str, params_list: List[Tuple]) -> None:
        """
        Выполняет множество SQL-запросов

        Args:
            query: SQL-запрос
            params_list: Список параметров для выполнения запроса
        """
        connection = self._get_connection()
        cursor = connection.cursor()

        try:
            cursor.executemany(query, params_list)
            connection.commit()
        except Exception as e:
            connection.rollback()
            logger.error(f"Ошибка SQL: {e} в запросе: {query}")
            raise
        finally:
            connection.close()

    def get_last_id(self) -> int:
        """
        Возвращает ID последней вставленной записи

        Returns:
            int: ID последней вставленной записи
        """
        result = self.execute("SELECT last_insert_rowid()")
        if result:
            return result[0][0]
        return 0

    def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Gets a user by ID

        Args:
            user_id: User ID

        Returns:
            Optional[Dict[str, Any]]: User data or None if not found
        """
        result = self.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        if result:
            return dict(result[0])
        return None

    def get_all_users(self) -> List[Dict[str, Any]]:
        """
        Gets all users

        Returns:
            List[Dict[str, Any]]: List of users
        """
        result = self.execute("SELECT * FROM users ORDER BY id")
        return [dict(row) for row in result]

    def add_user(self, user_id: int, name: str = "", is_admin: int = 0, is_active: int = 1) -> bool:
        """
        Adds a new user

        Args:
            user_id: User ID
            name: User name
            is_admin: Is user an admin (0 or 1)
            is_active: Is user active (0 or 1)

        Returns:
            bool: True if user was added
        """
        try:
            self.execute(
                "INSERT OR IGNORE INTO users (id, name, is_admin, is_active) VALUES (?, ?, ?, ?)",
                (user_id, name, is_admin, is_active)
            )
            return True
        except Exception as e:
            logger.error(f"Ошибка при добавлении пользователя: {e}")
            return False

    def update_user(self, user_id: int, name: Optional[str] = None,
                    is_admin: Optional[int] = None, is_active: Optional[int] = None) -> bool:
        """
        Updates user data

        Args:
            user_id: User ID
            name: User name (optional)
            is_admin: Is user an admin (optional)
            is_active: Is user active (optional)

        Returns:
            bool: True if user was updated
        """
        # Build SET part of query based on provided parameters
        update_parts = []
        params = []

        if name is not None:
            update_parts.append("name = ?")
            params.append(name)

        if is_admin is not None:
            update_parts.append("is_admin = ?")
            params.append(is_admin)

        if is_active is not None:
            update_parts.append("is_active = ?")
            params.append(is_active)

        if not update_parts:
            return False  # Nothing to update

        # Add user_id to params
        params.append(user_id)

        # Execute query
        try:
            self.execute(
                f"UPDATE users SET {', '.join(update_parts)} WHERE id = ?",
                tuple(params)
            )
            return True
        except Exception as e:
            logger.error(f"Ошибка при обновлении пользователя: {e}")
            return False

    def insert_and_get_id(self, query: str, params: Optional[Tuple] = None) -> int:
        """
        Выполняет операцию вставки и возвращает ID вставленной записи

        Args:
            query: SQL-запрос INSERT
            params: Параметры запроса

        Returns:
            int: ID вставленной записи или 0, если произошла ошибка
        """
        self.connect()
        try:
            if params:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)

            # Получаем ID сразу после вставки, до коммита и закрытия соединения
            row_id = self.cursor.lastrowid

            # Только после получения ID выполняем коммит
            self.connection.commit()

            return row_id or 0
        except Exception as e:
            if self.connection:
                self.connection.rollback()
            logger.error(f"SQL Error in insert_and_get_id: {e} in query: {query}")
            return 0
        finally:
            self.close()