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

    # В файле src/core/services/task_service.py
    # Добавляем новый метод для исправления нарушений зависимостей непосредственно в БД

    def fix_dependency_violations(self, project_id: int) -> Dict[str, Any]:
        """
        Проверяет и исправляет нарушения зависимостей между задачами проекта

        Args:
            project_id: ID проекта

        Returns:
            Dict[str, Any]: Информация о выполненных исправлениях
        """
        logger.info(f"Исправление нарушений зависимостей для проекта {project_id}")

        # Получаем все задачи проекта
        tasks = self.get_all_tasks_by_project(project_id)

        # Создаем словарь задач для быстрого доступа
        task_by_id = {task.id: task for task in tasks}

        # Создаем словарь зависимостей
        dependencies = {}

        # Готовим список найденных нарушений и исправлений
        violations = []
        fixes = []

        # Получаем зависимости для каждой задачи
        for task in tasks:
            if not task.predecessors:
                continue

            # Преобразуем предшественников в список
            predecessors = []
            if isinstance(task.predecessors, list):
                predecessors = task.predecessors
            elif isinstance(task.predecessors, str) and task.predecessors.strip():
                try:
                    import json
                    predecessors = json.loads(task.predecessors)
                except Exception as e:
                    logger.warning(f"Не удалось разобрать предшественников для задачи {task.id}: {e}")
                    predecessors = []

            if predecessors:
                dependencies[task.id] = predecessors

        # Проверяем и исправляем нарушения зависимостей
        import datetime

        # Сначала находим все нарушения
        for task_id, predecessors in dependencies.items():
            task = task_by_id.get(task_id)
            if not task or not task.start_date:
                continue

            task_name = task.name
            task_start = datetime.datetime.strptime(task.start_date, '%Y-%m-%d')

            for pred_id in predecessors:
                pred = task_by_id.get(pred_id)
                if not pred or not pred.end_date:
                    continue

                pred_name = pred.name
                pred_end = datetime.datetime.strptime(pred.end_date, '%Y-%m-%d')

                # Проверяем нарушение: задача начинается раньше или в тот же день,
                # когда заканчивается предшественник
                if task_start <= pred_end:
                    violation = {
                        'task_id': task_id,
                        'task_name': task_name,
                        'task_start': task.start_date,
                        'task_end': task.end_date,
                        'pred_id': pred_id,
                        'pred_name': pred_name,
                        'pred_end': pred.end_date
                    }
                    violations.append(violation)

        # Если нарушений нет, возвращаем результат
        if not violations:
            return {
                'fixed': False,
                'message': 'Нарушений зависимостей не обнаружено',
                'violations': [],
                'fixes': []
            }

        # Исправляем нарушения
        for violation in violations:
            task_id = violation['task_id']
            task = task_by_id.get(task_id)
            pred_end = datetime.datetime.strptime(violation['pred_end'], '%Y-%m-%d')

            # Новая дата начала - день после окончания предшественника
            new_start_date = pred_end + datetime.timedelta(days=1)

            # Пересчитываем дату окончания с учетом длительности
            task_duration = task.duration - 1  # -1 т.к. считаем включительно
            new_end_date = new_start_date + datetime.timedelta(days=task_duration)

            # Сохраняем старые даты для логирования
            old_start = task.start_date
            old_end = task.end_date

            # Обновляем даты в базе данных
            self.update_task_dates({
                task_id: {
                    'start': new_start_date.strftime('%Y-%m-%d'),
                    'end': new_end_date.strftime('%Y-%m-%d')
                }
            })

            # Обновляем даты в нашем словаре задач для последующих проверок
            task.start_date = new_start_date.strftime('%Y-%m-%d')
            task.end_date = new_end_date.strftime('%Y-%m-%d')

            fix = {
                'task_id': task_id,
                'task_name': task.name,
                'old_start': old_start,
                'old_end': old_end,
                'new_start': task.start_date,
                'new_end': task.end_date,
                'pred_id': violation['pred_id'],
                'pred_name': violation['pred_name']
            }
            fixes.append(fix)

            logger.info(
                f"Исправлено нарушение: задача {task.name} (ID {task_id}) перенесена "
                f"с {old_start} - {old_end} на {task.start_date} - {task.end_date} "
                f"из-за зависимости от {violation['pred_name']} (ID {violation['pred_id']})"
            )

            # После изменения дат текущей задачи, нужно проверить задачи, зависящие от нее
            self._fix_dependent_tasks(task_id, task_by_id, dependencies, fixes)

        return {
            'fixed': True,
            'message': f'Исправлено {len(fixes)} нарушений зависимостей',
            'violations': violations,
            'fixes': fixes
        }

    def _fix_dependent_tasks(self, task_id: int, task_by_id: Dict[int, Any],
                             dependencies: Dict[int, List[int]], fixes: List[Dict[str, Any]]):
        """
        Рекурсивно исправляет даты задач, зависящих от указанной

        Args:
            task_id: ID задачи, даты которой были изменены
            task_by_id: Словарь задач по ID
            dependencies: Словарь зависимостей
            fixes: Список выполненных исправлений
        """
        import datetime

        # Находим все задачи, зависящие от данной
        dependent_tasks = []
        for dep_id, preds in dependencies.items():
            if task_id in preds:
                dependent_tasks.append(dep_id)

        # Текущая задача после обновления
        task = task_by_id.get(task_id)
        if not task or not task.end_date:
            return

        task_end = datetime.datetime.strptime(task.end_date, '%Y-%m-%d')

        # Исправляем даты зависимых задач
        for dep_id in dependent_tasks:
            dep_task = task_by_id.get(dep_id)
            if not dep_task or not dep_task.start_date:
                continue

            dep_start = datetime.datetime.strptime(dep_task.start_date, '%Y-%m-%d')

            # Если начало зависимой задачи раньше или равно окончанию текущей
            if dep_start <= task_end:
                # Новое начало - день после окончания текущей задачи
                new_start = task_end + datetime.timedelta(days=1)

                # Длительность зависимой задачи
                dep_duration = dep_task.duration - 1  # -1 т.к. считаем включительно

                # Новое окончание
                new_end = new_start + datetime.timedelta(days=dep_duration)

                # Сохраняем старые даты для логирования
                old_start = dep_task.start_date
                old_end = dep_task.end_date

                # Обновляем даты в базе данных
                self.update_task_dates({
                    dep_id: {
                        'start': new_start.strftime('%Y-%m-%d'),
                        'end': new_end.strftime('%Y-%m-%d')
                    }
                })

                # Обновляем даты в нашем словаре задач для последующих проверок
                dep_task.start_date = new_start.strftime('%Y-%m-%d')
                dep_task.end_date = new_end.strftime('%Y-%m-%d')

                fix = {
                    'task_id': dep_id,
                    'task_name': dep_task.name,
                    'old_start': old_start,
                    'old_end': old_end,
                    'new_start': dep_task.start_date,
                    'new_end': dep_task.end_date,
                    'pred_id': task_id,
                    'pred_name': task.name
                }
                fixes.append(fix)

                logger.info(
                    f"Каскадное исправление: задача {dep_task.name} (ID {dep_id}) перенесена "
                    f"с {old_start} - {old_end} на {dep_task.start_date} - {dep_task.end_date} "
                    f"из-за изменения дат задачи {task.name} (ID {task_id})"
                )

                # Рекурсивно проверяем задачи, зависящие от этой
                self._fix_dependent_tasks(dep_id, task_by_id, dependencies, fixes)