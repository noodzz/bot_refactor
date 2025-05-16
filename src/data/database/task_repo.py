import logging
from typing import List, Dict, Any, Optional, Union
import json
from src.core.models.task import Task


class TaskRepository:
    """Репозиторий для работы с задачами в базе данных"""

    def __init__(self, db_manager):
        """
        Инициализирует репозиторий задач

        Args:
            db_manager: Менеджер базы данных
        """
        self.db = db_manager

    def create_task(self, task: Task) -> int:
        """
        Создает новую задачу в базе данных

        Args:
            task: Объект задачи

        Returns:
            int: ID созданной задачи
        """
        try:
            # Сериализуем предшественников в строку JSON
            predecessors = task.predecessors
            if predecessors is not None:
                if isinstance(predecessors, list):
                    import json
                    predecessors = json.dumps(predecessors)
                elif not isinstance(predecessors, str):
                    predecessors = str(predecessors)
            else:
                predecessors = "[]"  # Пустой список в формате JSON
            logger = logging.getLogger(__name__)
            logger.debug(f"Предшественники после обработки: {predecessors}, тип: {type(predecessors)}")

            # Если working_duration не указано, используем duration
            working_duration = task.working_duration or task.duration

            query = """INSERT INTO tasks 
                       (project_id, parent_id, name, duration, working_duration, 
                       is_group, parallel, position, predecessors) 
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"""

            params = (
                task.project_id, task.parent_id, task.name, task.duration,
                working_duration, task.is_group, task.parallel, task.position,
                predecessors
            )

            logger.debug(f"Создание задачи: {task.name}, параметры: {params}")

            self.db.execute(query, params)
            # Получаем ID созданной задачи
            result = self.db.execute("SELECT last_insert_rowid()")
            task_id = result[0][0] if result else 0
            logger.debug(f"Создана задача с ID: {task_id}")
            return task_id
        except Exception as e:
            logger.error(f"Ошибка при создании задачи: {str(e)}")
            raise ValueError(f"Не удалось создать задачу: {str(e)}")

    def get_task(self, task_id: int) -> Optional[Task]:
        """
        Возвращает информацию о задаче

        Args:
            task_id: ID задачи

        Returns:
            Optional[Task]: Объект задачи или None, если задача не найдена
        """
        result = self.db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        if result:
            return Task.from_dict(dict(result[0]))
        return None

    def get_tasks_by_project(self, project_id: int, include_subtasks: bool = False) -> List[Task]:
        """
        Возвращает список задач проекта

        Args:
            project_id: ID проекта
            include_subtasks: Включать ли подзадачи в результат

        Returns:
            List[Task]: Список задач
        """
        if include_subtasks:
            result = self.db.execute(
                "SELECT * FROM tasks WHERE project_id = ? ORDER BY id",
                (project_id,)
            )
        else:
            result = self.db.execute(
                "SELECT * FROM tasks WHERE project_id = ? AND parent_id IS NULL ORDER BY id",
                (project_id,)
            )

        return [Task.from_dict(dict(row)) for row in result]

    def get_subtasks(self, parent_id: int) -> List[Task]:
        """
        Возвращает список подзадач для групповой задачи

        Args:
            parent_id: ID родительской задачи

        Returns:
            List[Task]: Список подзадач
        """
        result = self.db.execute(
            "SELECT * FROM tasks WHERE parent_id = ? ORDER BY id",
            (parent_id,)
        )

        return [Task.from_dict(dict(row)) for row in result]

    def update_task(self, task: Task) -> bool:
        """
        Обновляет информацию о задаче

        Args:
            task: Объект задачи с обновленными данными

        Returns:
            bool: True, если обновление успешно, иначе False
        """
        if not task.id:
            return False

        # Сериализуем предшественников, если это список
        predecessors = task.predecessors
        if not isinstance(predecessors, str) and predecessors:
            predecessors = json.dumps(predecessors)

        try:
            self.db.execute(
                """UPDATE tasks SET 
                   name = ?, duration = ?, working_duration = ?, is_group = ?, 
                   parallel = ?, start_date = ?, end_date = ?, employee_id = ?, 
                   position = ?, predecessors = ? 
                   WHERE id = ?""",
                (
                    task.name, task.duration, task.working_duration, task.is_group,
                    task.parallel, task.start_date, task.end_date, task.employee_id,
                    task.position, predecessors, task.id
                )
            )
            return True
        except Exception:
            return False

    def update_task_dates(self, task_id: int, start_date: str, end_date: str) -> bool:
        """
        Обновляет даты начала и окончания задачи

        Args:
            task_id: ID задачи
            start_date: Дата начала в формате YYYY-MM-DD
            end_date: Дата окончания в формате YYYY-MM-DD

        Returns:
            bool: True, если обновление успешно, иначе False
        """
        try:
            self.db.execute(
                "UPDATE tasks SET start_date = ?, end_date = ? WHERE id = ?",
                (start_date, end_date, task_id)
            )
            return True
        except Exception:
            return False

    def assign_employee(self, task_id: int, employee_id: int) -> bool:
        """
        Назначает сотрудника на задачу

        Args:
            task_id: ID задачи
            employee_id: ID сотрудника

        Returns:
            bool: True, если назначение успешно, иначе False
        """
        try:
            self.db.execute(
                "UPDATE tasks SET employee_id = ? WHERE id = ?",
                (employee_id, task_id)
            )
            return True
        except Exception:
            return False

    def add_dependency(self, task_id: int, predecessor_id: int) -> bool:
        """
        Добавляет зависимость между задачами

        Args:
            task_id: ID зависимой задачи
            predecessor_id: ID задачи-предшественника

        Returns:
            bool: True, если добавление успешно, иначе False
        """
        try:
            self.db.execute(
                "INSERT INTO dependencies (task_id, predecessor_id) VALUES (?, ?)",
                (task_id, predecessor_id)
            )
            return True
        except Exception:
            return False

    def get_task_dependencies(self, task_id: int) -> List[int]:
        """
        Возвращает список ID задач-предшественников

        Args:
            task_id: ID задачи

        Returns:
            List[int]: Список ID задач-предшественников
        """
        result = self.db.execute(
            "SELECT predecessor_id FROM dependencies WHERE task_id = ?",
            (task_id,)
        )

        return [row['predecessor_id'] for row in result]

    def get_dependents(self, task_id: int) -> List[int]:
        """
        Возвращает список ID зависимых задач

        Args:
            task_id: ID задачи

        Returns:
            List[int]: Список ID зависимых задач
        """
        result = self.db.execute(
            "SELECT task_id FROM dependencies WHERE predecessor_id = ?",
            (task_id,)
        )

        return [row['task_id'] for row in result]

    def delete_task(self, task_id: int) -> bool:
        """
        Удаляет задачу из базы данных

        Args:
            task_id: ID задачи

        Returns:
            bool: True, если удаление успешно, иначе False
        """
        try:
            # Удаляем зависимости
            self.db.execute("DELETE FROM dependencies WHERE task_id = ? OR predecessor_id = ?",
                            (task_id, task_id))

            # Удаляем подзадачи
            subtasks = self.get_subtasks(task_id)
            for subtask in subtasks:
                self.delete_task(subtask.id)

            # Удаляем задачу
            self.db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            return True
        except Exception:
            return False