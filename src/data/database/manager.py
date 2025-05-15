import sqlite3
import os
from typing import List, Dict, Any, Optional, Tuple, Union


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

    def init_db(self) -> None:
        """Инициализирует базу данных и создает таблицы, если их нет"""
        self.connect()

        # Создаем таблицы
        self.cursor.executescript('''
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

        self.connection.commit()
        self.close()

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

    def execute(self, query: str, params: Optional[Union[Tuple, Dict[str, Any]]] = None) -> List[sqlite3.Row]:
        """
        Выполняет SQL-запрос

        Args:
            query: SQL-запрос
            params: Параметры запроса

        Returns:
            List[sqlite3.Row]: Результат выполнения запроса
        """
        self.connect()
        try:
            if params:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)

            self.connection.commit()
            result = self.cursor.fetchall()
            return result
        finally:
            self.close()

    def execute_many(self, query: str, params_list: List[Tuple]) -> None:
        """
        Выполняет множество SQL-запросов

        Args:
            query: SQL-запрос
            params_list: Список параметров для выполнения запроса
        """
        self.connect()
        try:
            self.cursor.executemany(query, params_list)
            self.connection.commit()
        finally:
            self.close()

    def get_last_id(self) -> int:
        """
        Возвращает ID последней вставленной записи

        Returns:
            int: ID последней вставленной записи
        """
        if self.cursor:
            return self.cursor.lastrowid
        return 0