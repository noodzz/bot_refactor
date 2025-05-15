from typing import List, Dict, Any, Optional
import sqlite3
from src.core.models.project import Project


class ProjectRepository:
    """Репозиторий для работы с проектами в базе данных"""

    def __init__(self, db_manager):
        """
        Инициализирует репозиторий проектов

        Args:
            db_manager: Менеджер базы данных
        """
        self.db = db_manager

    def create_project(self, name: str, start_date: str, user_id: Optional[int] = None) -> int:
        """
        Создает новый проект в базе данных

        Args:
            name: Название проекта
            start_date: Дата начала в формате YYYY-MM-DD
            user_id: ID пользователя-создателя

        Returns:
            int: ID созданного проекта
        """
        self.db.connect()

        query = "INSERT INTO projects (name, start_date, user_id) VALUES (?, ?, ?)"
        params = (name, start_date, user_id)

        try:
            self.db.cursor.execute(query, params)
            self.db.connection.commit()
            return self.db.cursor.lastrowid
        finally:
            self.db.close()

    def get_project(self, project_id: int) -> Optional[Project]:
        """
        Возвращает информацию о проекте

        Args:
            project_id: ID проекта

        Returns:
            Optional[Project]: Объект проекта или None, если проект не найден
        """
        result = self.db.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
        if result:
            return Project.from_dict(dict(result[0]))
        return None

    def get_projects(self, user_id: Optional[int] = None) -> List[Project]:
        """
        Возвращает список проектов

        Args:
            user_id: ID пользователя для фильтрации (опционально)

        Returns:
            List[Project]: Список проектов
        """
        if user_id is not None:
            result = self.db.execute(
                "SELECT * FROM projects WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,)
            )
        else:
            result = self.db.execute("SELECT * FROM projects ORDER BY created_at DESC")

        return [Project.from_dict(dict(row)) for row in result]

    def update_project(self, project: Project) -> bool:
        """
        Обновляет информацию о проекте

        Args:
            project: Объект проекта с обновленными данными

        Returns:
            bool: True, если обновление успешно, иначе False
        """
        if not project.id:
            return False

        try:
            self.db.execute(
                """UPDATE projects SET 
                   name = ?, start_date = ?, status = ? 
                   WHERE id = ?""",
                (project.name, project.start_date, project.status, project.id)
            )
            return True
        except Exception:
            return False

    def delete_project(self, project_id: int) -> bool:
        """
        Удаляет проект из базы данных

        Args:
            project_id: ID проекта

        Returns:
            bool: True, если удаление успешно, иначе False
        """
        try:
            self.db.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            return True
        except Exception:
            return False