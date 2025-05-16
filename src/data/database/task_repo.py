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
        logger = logging.getLogger(__name__)
        try:
            # Сериализуем предшественников в строку JSON
            if isinstance(task.predecessors, list):
                predecessors = json.dumps(task.predecessors)
            elif isinstance(task.predecessors, str):
                predecessors = task.predecessors
            else:
                predecessors = "[]"  # Пустой список в формате JSON

            # Если working_duration не указано, используем duration
            working_duration = task.working_duration or task.duration

            # Подготавливаем запрос
            query = """INSERT INTO tasks 
                       (project_id, parent_id, name, duration, working_duration, 
                       is_group, parallel, position, predecessors) 
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"""

            params = (
                task.project_id, task.parent_id, task.name, task.duration,
                working_duration, 1 if task.is_group else 0, 1 if task.parallel else 0,
                task.position, predecessors
            )

            # Используем новый метод для вставки и получения ID
            task_id = self.db.insert_and_get_id(query, params)

            if task_id:
                logger.info(f"Создана задача '{task.name}' с ID {task_id}")
                return task_id

            logger.error(f"Не удалось получить ID созданной задачи '{task.name}'")
            return 0
        except Exception as e:
            logger.error(f"Ошибка при создании задачи '{task.name}': {str(e)}")
            return 0

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
        logger = logging.getLogger(__name__)
        try:
            # Проверка наличия зависимости
            existing = self.db.execute(
                "SELECT COUNT(*) FROM dependencies WHERE task_id = ? AND predecessor_id = ?",
                (task_id, predecessor_id)
            )

            if existing and existing[0][0] > 0:
                logger.debug(f"Зависимость {task_id} -> {predecessor_id} уже существует")
                return True

            # Добавляем зависимость в таблицу dependencies
            self.db.execute(
                "INSERT INTO dependencies (task_id, predecessor_id) VALUES (?, ?)",
                (task_id, predecessor_id)
            )
            logger.info(f"Добавлена зависимость в таблицу dependencies: {task_id} -> {predecessor_id}")

            # Получаем текущие предшественники
            current_pred_query = "SELECT predecessors FROM tasks WHERE id = ?"
            current_pred_result = self.db.execute(current_pred_query, (task_id,))

            pred_list = []
            if current_pred_result and current_pred_result[0][0]:
                try:
                    # Пытаемся распарсить JSON
                    pred_json = current_pred_result[0][0]
                    if isinstance(pred_json, str):
                        pred_list = json.loads(pred_json)
                        if not isinstance(pred_list, list):
                            pred_list = []
                except Exception as e:
                    logger.error(f"Ошибка при парсинге JSON предшественников: {e}")
                    pred_list = []

            # Добавляем нового предшественника, если его еще нет
            if predecessor_id not in pred_list:
                pred_list.append(predecessor_id)

            # Обновляем поле predecessors
            pred_json = json.dumps(pred_list)
            self.db.execute(
                "UPDATE tasks SET predecessors = ? WHERE id = ?",
                (pred_json, task_id)
            )

            logger.info(f"Обновлено поле predecessors для задачи {task_id}: {pred_json}")
            return True
        except Exception as e:
            logger.error(f"Ошибка при добавлении зависимости {task_id} -> {predecessor_id}: {e}")
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

    def get_project(self, project_id: int) -> Optional[Dict[str, Any]]:
        """
        Возвращает информацию о проекте

        Args:
            project_id: ID проекта

        Returns:
            Optional[Dict[str, Any]]: Данные проекта или None, если проект не найден
        """
        logger = logging.getLogger(__name__)
        try:
            result = self.db.execute(
                "SELECT * FROM projects WHERE id = ?",
                (project_id,)
            )
            if result and len(result) > 0:
                # Возвращаем словарь с данными проекта
                return dict(result[0])
            return None
        except Exception as e:
            logger.error(f"Ошибка при получении проекта {project_id}: {e}")
            return None

    def debug_dependencies(self, project_id: int):
        """
        Отладочный метод для проверки и исправления зависимостей

        Args:
            project_id: ID проекта
        """
        logger = logging.getLogger(__name__)
        # Получаем все задачи проекта
        tasks = self.get_tasks_by_project(project_id, include_subtasks=True)

        # Выводим список задач
        logger.info(f"Проект {project_id}: найдено {len(tasks)} задач")

        # Проверяем таблицу dependencies
        deps = self.db.execute("SELECT * FROM dependencies")
        logger.info(f"В таблице dependencies {len(deps)} записей")

        # Проверяем каждую задачу
        for task in tasks:
            # Получаем предшественников из таблицы dependencies
            query = "SELECT predecessor_id FROM dependencies WHERE task_id = ?"
            predecessors = self.db.execute(query, (task.id,))

            # Преобразуем в список ID
            pred_ids = [row[0] for row in predecessors]

            logger.info(
                f"Задача {task.id} ({task.name}): найдено {len(pred_ids)} предшественников в таблице dependencies")

            # Проверяем, что поле predecessors заполнено правильно
            if task.predecessors:
                logger.info(
                    f"Задача {task.id}: поле predecessors = {task.predecessors}, тип: {type(task.predecessors)}")
            else:
                logger.info(f"Задача {task.id}: поле predecessors пусто")

            # Если предшественники есть, но поле пусто, обновляем
            if pred_ids and (not task.predecessors or task.predecessors == "[]"):
                # Обновляем поле predecessors в базе данных
                try:
                    self.db.execute(
                        "UPDATE tasks SET predecessors = ? WHERE id = ?",
                        (json.dumps(pred_ids), task.id)
                    )
                    logger.info(f"Обновлено поле predecessors для задачи {task.id}: {pred_ids}")
                except Exception as e:
                    logger.error(f"Ошибка при обновлении предшественников для задачи {task.id}: {e}")