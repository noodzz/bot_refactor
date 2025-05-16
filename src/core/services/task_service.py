from typing import List, Dict, Any, Optional
import json
import logging

from src.core.models.task import Task
from src.data.database.task_repo import TaskRepository

logger = logging.getLogger(__name__)


class TaskService:
    """Сервис для работы с задачами"""

    def __init__(self, task_repo: TaskRepository):
        """
        Инициализирует сервис задач

        Args:
            task_repo: Репозиторий задач
        """
        self.task_repo = task_repo

    def get_tasks_by_project(self, project_id: int, include_subtasks: bool = False) -> List[Task]:
        """
        Возвращает список задач проекта

        Args:
            project_id: ID проекта
            include_subtasks: Включать ли подзадачи в результат

        Returns:
            List[Task]: Список задач
        """
        return self.task_repo.get_tasks_by_project(project_id, include_subtasks)

    def get_subtasks(self, parent_id: int) -> List[Task]:
        """
        Возвращает список подзадач для групповой задачи

        Args:
            parent_id: ID родительской задачи

        Returns:
            List[Task]: Список подзадач
        """
        return self.task_repo.get_subtasks(parent_id)

    def get_task(self, task_id: int) -> Optional[Task]:
        """
        Возвращает информацию о задаче

        Args:
            task_id: ID задачи

        Returns:
            Optional[Task]: Объект задачи или None, если задача не найдена

        Raises:
            ValueError: Если задача не найдена
        """
        task = self.task_repo.get_task(task_id)
        if not task:
            raise ValueError(f"Задача с ID {task_id} не найдена")

        return task

    def create_task(self, project_id: int, task_data: Dict[str, Any]) -> int:
        """
        Создает новую задачу в проекте

        Args:
            project_id: ID проекта
            task_data: Данные задачи

        Returns:
            int: ID созданной задачи

        Raises:
            ValueError: Если произошла ошибка при создании задачи
        """
        try:
            # Создаем задачу
            is_group = task_data.get("is_group", False)

            task = Task(
                project_id=project_id,
                name=task_data["name"],
                duration=task_data["duration"],
                is_group=is_group,
                position=task_data.get("position")
            )

            task_id = self.task_repo.create_task(task)

            # Если это групповая задача, создаем подзадачи
            if is_group and "subtasks" in task_data:
                for subtask_data in task_data["subtasks"]:
                    subtask = Task(
                        project_id=project_id,
                        parent_id=task_id,
                        name=subtask_data["name"],
                        duration=subtask_data["duration"],
                        position=subtask_data["position"],
                        parallel=subtask_data.get("parallel", False)
                    )

                    self.task_repo.create_task(subtask)

            # Устанавливаем зависимости
            if "predecessors" in task_data and task_data["predecessors"]:
                for predecessor_id in task_data["predecessors"]:
                    self.task_repo.add_dependency(task_id, predecessor_id)

            return task_id

        except Exception as e:
            logger.error(f"Ошибка при создании задачи: {str(e)}")
            raise ValueError(f"Ошибка при создании задачи: {str(e)}")

    def create_subtask(self, project_id: int, parent_id: int, subtask_data: Dict[str, Any]) -> int:
        """
        Создает подзадачу для групповой задачи

        Args:
            project_id: ID проекта
            parent_id: ID родительской задачи
            subtask_data: Данные подзадачи

        Returns:
            int: ID созданной подзадачи

        Raises:
            ValueError: Если произошла ошибка при создании подзадачи
        """
        try:
            # Проверяем существование родительской задачи
            parent_task = self.task_repo.get_task(parent_id)
            if not parent_task:
                raise ValueError(f"Родительская задача с ID {parent_id} не найдена")

            # Проверяем, что родительская задача является групповой
            if not parent_task.is_group:
                raise ValueError("Подзадачи можно создавать только для групповых задач")

            # Создаем подзадачу
            subtask = Task(
                project_id=project_id,
                parent_id=parent_id,
                name=subtask_data["name"],
                duration=subtask_data["duration"],
                position=subtask_data["position"],
                parallel=subtask_data.get("parallel", False)
            )

            subtask_id = self.task_repo.create_task(subtask)

            return subtask_id

        except Exception as e:
            logger.error(f"Ошибка при создании подзадачи: {str(e)}")
            raise ValueError(f"Ошибка при создании подзадачи: {str(e)}")

    def assign_employee(self, task_id: int, employee_id: int) -> bool:
        """
        Назначает сотрудника на задачу

        Args:
            task_id: ID задачи
            employee_id: ID сотрудника

        Returns:
            bool: True, если назначение успешно, иначе False

        Raises:
            ValueError: Если произошла ошибка при назначении сотрудника
        """
        try:
            # Проверяем существование задачи
            task = self.task_repo.get_task(task_id)
            if not task:
                raise ValueError(f"Задача с ID {task_id} не найдена")

            # Проверяем, что задача не является групповой
            if task.is_group:
                raise ValueError("Нельзя назначить сотрудника на групповую задачу. Назначьте сотрудников на подзадачи.")

            # Назначаем сотрудника на задачу
            return self.task_repo.assign_employee(task_id, employee_id)

        except Exception as e:
            logger.error(f"Ошибка при назначении сотрудника: {str(e)}")
            raise ValueError(f"Ошибка при назначении сотрудника: {str(e)}")

    def get_task_dependencies(self, task_id: int) -> List[int]:
        """
        Возвращает список предшественников задачи

        Args:
            task_id: ID задачи

        Returns:
            List[int]: Список ID задач-предшественников
        """
        return self.task_repo.get_task_dependencies(task_id)

    def get_task_dependents(self, task_id: int) -> List[int]:
        """
        Возвращает список задач, зависящих от указанной

        Args:
            task_id: ID задачи

        Returns:
            List[int]: Список ID зависимых задач
        """
        return self.task_repo.get_dependents(task_id)

    def add_dependency(self, task_id: int, predecessor_id: int) -> bool:
        """
        Добавляет зависимость между задачами

        Args:
            task_id: ID зависимой задачи
            predecessor_id: ID задачи-предшественника

        Returns:
            bool: True, если добавление успешно, иначе False

        Raises:
            ValueError: Если произошла ошибка при добавлении зависимости
        """
        try:
            # Проверяем существование задачи
            task = self.task_repo.get_task(task_id)
            if not task:
                raise ValueError(f"Задача с ID {task_id} не найдена")

            # Проверяем существование предшественника
            predecessor = self.task_repo.get_task(predecessor_id)
            if not predecessor:
                raise ValueError(f"Предшественник с ID {predecessor_id} не найден")

            # Проверяем, что не создается циклическая зависимость
            if self._is_cyclic_dependency(task_id, predecessor_id):
                raise ValueError("Нельзя создать циклическую зависимость между задачами")

            # Добавляем зависимость
            return self.task_repo.add_dependency(task_id, predecessor_id)

        except Exception as e:
            logger.error(f"Ошибка при добавлении зависимости: {str(e)}")
            raise ValueError(f"Ошибка при добавлении зависимости: {str(e)}")

    def _is_cyclic_dependency(self, task_id: int, predecessor_id: int) -> bool:
        """
        Проверяет, не создается ли циклическая зависимость

        Args:
            task_id: ID зависимой задачи
            predecessor_id: ID задачи-предшественника

        Returns:
            bool: True, если создается циклическая зависимость, иначе False
        """
        # Если задача и предшественник совпадают, это циклическая зависимость
        if task_id == predecessor_id:
            return True

        # Проверяем, не является ли задача уже предшественником для предшественника
        predecessors_of_predecessor = self.get_task_dependencies(predecessor_id)
        if task_id in predecessors_of_predecessor:
            return True

        # Рекурсивно проверяем предшественников предшественника
        for pred_id in predecessors_of_predecessor:
            if self._is_cyclic_dependency(task_id, pred_id):
                return True

        return False

    def update_task_dates(self, task_dates: Dict[int, Dict[str, str]]) -> None:
        """
        Обновляет даты начала и окончания задач

        Args:
            task_dates: Словарь с датами задач
        """
        for task_id, dates in task_dates.items():
            # Проверяем наличие необходимых данных
            if 'start' in dates and 'end' in dates:
                try:
                    # Проверяем, существует ли задача
                    task = self.task_repo.get_task(task_id)
                    if task:
                        # Логируем для отладки
                        logger.info(f"Обновляем даты для задачи {task_id}: {dates['start']} - {dates['end']}")
                        result = self.task_repo.update_task_dates(task_id, dates['start'], dates['end'])
                        if not result:
                            logger.error(f"Не удалось обновить даты для задачи {task_id}")
                except Exception as e:
                    logger.error(f"Ошибка при обновлении дат задачи {task_id}: {str(e)}")

    def get_all_tasks_by_project(self, project_id: int) -> List[Task]:
        """
        Возвращает список всех задач проекта, включая подзадачи

        Args:
            project_id: ID проекта

        Returns:
            List[Task]: Список задач
        """
        return self.task_repo.get_tasks_by_project(project_id, include_subtasks=True)