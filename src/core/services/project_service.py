from typing import List, Dict, Any, Optional
import datetime
import json
import logging

from src.core.models.project import Project
from src.core.models.task import Task
from src.data.database.project_repo import ProjectRepository
from src.data.database.task_repo import TaskRepository
from src.utils.date_utils import validate_date_format

logger = logging.getLogger(__name__)


class ProjectService:
    """Сервис для работы с проектами"""

    def __init__(self, project_repo: ProjectRepository, task_repo: TaskRepository,
                 templates: Dict[int, Dict[str, Any]]):
        """
        Инициализирует сервис проектов

        Args:
            project_repo: Репозиторий проектов
            task_repo: Репозиторий задач
            templates: Словарь шаблонов проектов
        """
        self.project_repo = project_repo
        self.task_repo = task_repo
        self.templates = templates

    def create_from_template(self, name: str, start_date: str, template_id: int, user_id: Optional[int] = None) -> int:
        """
        Создает проект из шаблона

        Args:
            name: Название проекта
            start_date: Дата начала в формате YYYY-MM-DD
            template_id: ID шаблона
            user_id: ID пользователя-создателя

        Returns:
            int: ID созданного проекта

        Raises:
            ValueError: Если неверный формат даты или не найден шаблон
        """
        # Валидация даты
        if not validate_date_format(start_date):
            raise ValueError(f"Неверный формат даты: {start_date}")

        # Проверяем существование шаблона
        if template_id not in self.templates:
            raise ValueError(f"Шаблон с ID {template_id} не найден")

        template = self.templates[template_id]

        # Создаем проект
        project = Project(name=name, start_date=start_date, user_id=user_id)
        project_id = self.project_repo.create_project(name, start_date, user_id)

        # Создаем задачи из шаблона
        task_mapping = {}  # Для сопоставления имен задач с их ID

        # Сначала создаем все задачи без зависимостей
        for task_data in template["tasks"]:
            is_group = task_data.get("is_group", False)

            task = Task(
                project_id=project_id,
                name=task_data["name"],
                duration=task_data["duration"],
                working_duration=task_data.get("working_duration", task_data["duration"]),
                is_group=is_group,
                position=task_data.get("position")
            )

            task_id = self.task_repo.create_task(task)
            task_mapping[task_data["name"]] = task_id
            logger.info(f"Создана задача '{task_data['name']}' с ID {task_id}")

            # Если это групповая задача, создаем подзадачи
            if is_group and "subtasks" in task_data:
                for subtask_data in task_data["subtasks"]:
                    subtask = Task(
                        project_id=project_id,
                        parent_id=task_id,
                        name=subtask_data["name"],
                        duration=subtask_data["duration"],
                        working_duration=task_data.get("working_duration", subtask_data["duration"]),
                        position=subtask_data.get("position"),
                        parallel=subtask_data.get("parallel", False)
                    )

                    subtask_id = self.task_repo.create_task(subtask)
                    logger.debug(
                        f"Создана подзадача '{subtask_data['name']}' (ID: {subtask_id}) "
                        f"для задачи '{task_data['name']}' (ID: {task_id})"
                    )

            # Затем устанавливаем зависимости
            for task_data in template["tasks"]:
                if "predecessors" in task_data and task_data["predecessors"]:
                    task_name = task_data["name"].strip()  # Удаляем лишние пробелы

                    # Если точное имя не найдено, попробуем найти без учета регистра и пробелов
                    if task_name not in task_mapping:
                        normalized_name = task_name.lower().replace(" ", "")
                        for k, v in task_mapping.items():
                            if k.lower().replace(" ", "") == normalized_name:
                                task_name = k
                                logger.info(f"Найдено соответствие для '{task_data['name']}' -> '{task_name}'")
                                break

                    if task_name not in task_mapping:
                        logger.warning(f"Задача '{task_data['name']}' не найдена в маппинге, пропускаем зависимости")
                        continue

                    task_id = task_mapping[task_name]

                    # Логируем для отладки
                    logger.info(f"Обрабатываем зависимости для задачи '{task_name}' (ID: {task_id})")

                    # Получаем текущую задачу
                    task = self.task_repo.get_task(task_id)
                    if task:
                        # Создаем список ID предшественников
                        predecessors = []
                        for predecessor_name in task_data["predecessors"]:
                            predecessor_name = predecessor_name.strip()  # Удаляем лишние пробелы

                            # Если точное имя не найдено, попробуем найти без учета регистра и пробелов
                            if predecessor_name not in task_mapping:
                                normalized_name = predecessor_name.lower().replace(" ", "")
                                for k, v in task_mapping.items():
                                    if k.lower().replace(" ", "") == normalized_name:
                                        predecessor_name = k
                                        logger.info(
                                            f"Найдено соответствие для предшественника '{predecessor_name}' -> '{k}'")
                                        break

                            if predecessor_name in task_mapping:
                                predecessor_id = task_mapping[predecessor_name]
                                predecessors.append(predecessor_id)
                                # Добавляем зависимость в базу данных
                                result = self.task_repo.add_dependency(task_id, predecessor_id)
                                logger.info(
                                    f"Добавлена зависимость: {task_id} ({task_name}) зависит от {predecessor_id} ({predecessor_name}), результат: {result}")
                            else:
                                logger.warning(f"Задача-предшественник '{predecessor_name}' не найдена")

                        # Обновляем задачу в базе с информацией о предшественниках
                        task.predecessors = predecessors
                        result = self.task_repo.update_task(task)
                        logger.info(
                            f"Обновлена задача {task_id} с предшественниками {predecessors}, результат: {result}")

        logger.info("Запускаем отладку зависимостей")
        self.task_repo.debug_dependencies(project_id)

        logger.info("===== Task Mapping =====")
        for task_name, task_id in task_mapping.items():
            logger.info(f"'{task_name}' -> {task_id}")
        logger.info("=======================")
        return project_id

    def create_from_csv(self, name: str, start_date: str, csv_data: List[Dict[str, Any]],
                        user_id: Optional[int] = None) -> int:
        """
        Создает проект из данных CSV

        Args:
            name: Название проекта
            start_date: Дата начала в формате YYYY-MM-DD
            csv_data: Данные из CSV-файла
            user_id: ID пользователя-создателя

        Returns:
            int: ID созданного проекта

        Raises:
            ValueError: Если неверный формат даты
        """
        # Валидация даты
        if not validate_date_format(start_date):
            raise ValueError(f"Неверный формат даты: {start_date}")

        # Создаем проект
        project = Project(name=name, start_date=start_date, user_id=user_id)
        project_id = self.project_repo.create_project(name, start_date, user_id)

        # Создаем задачи из CSV
        task_mapping = {}  # Для сопоставления имен задач с их ID

        # Сначала создаем все задачи без зависимостей
        for task_data in csv_data:
            is_group = task_data.get("is_group", False)

            task = Task(
                project_id=project_id,
                name=task_data["name"],
                duration=task_data["duration"],
                working_duration=task_data.get("working_duration", task_data["duration"]),
                is_group=is_group,
                position=task_data.get("position")
            )

            task_id = self.task_repo.create_task(task)
            task_mapping[task_data["name"]] = task_id

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

        # Затем устанавливаем зависимости
        for task_data in csv_data:
            if "predecessors" in task_data and task_data["predecessors"]:
                task_id = task_mapping[task_data["name"]]

                # Получаем текущую задачу
                task = self.task_repo.get_task(task_id)
                if task:
                    # Создаем список ID предшественников
                    predecessors = []
                    for predecessor_name in task_data["predecessors"]:
                        if predecessor_name in task_mapping:
                            predecessor_id = task_mapping[predecessor_name]
                            predecessors.append(predecessor_id)
                            # Добавляем зависимость в базу данных
                            self.task_repo.add_dependency(task_id, predecessor_id)

                    # Обновляем задачу в базе с информацией о предшественниках
                    task.predecessors = predecessors
                    self.task_repo.update_task(task)

        return project_id

    def get_all_projects(self, user_id: Optional[int] = None) -> List[Project]:
        """
        Возвращает список всех проектов

        Args:
            user_id: ID пользователя для фильтрации проектов

        Returns:
            List[Project]: Список проектов
        """
        try:
            projects = self.project_repo.get_projects(user_id)
            logger.info(f"Получено {len(projects)} проектов из БД для пользователя {user_id}")
            return projects
        except Exception as e:
            logger.error(f"Ошибка при получении списка проектов: {e}")
            return []

    def get_project_details(self, project_id: int) -> Project:
        """
        Возвращает детальную информацию о проекте

        Args:
            project_id: ID проекта

        Returns:
            Project: Проект

        Raises:
            ValueError: Если проект не найден
        """
        project = self.project_repo.get_project(project_id)
        if not project:
            raise ValueError(f"Проект с ID {project_id} не найден")

        return project

    def get_templates(self) -> List[Dict[str, Any]]:
        """
        Возвращает список доступных шаблонов

        Returns:
            List[Dict[str, Any]]: Список шаблонов
        """
        templates = []
        for template_id, template_data in self.templates.items():
            templates.append({
                "id": template_id,
                "name": template_data["name"]
            })
        return templates

    def add_task(self, project_id: int, task_data: Dict[str, Any]) -> int:
        """
        Добавляет задачу в проект

        Args:
            project_id: ID проекта
            task_data: Данные задачи

        Returns:
            int: ID созданной задачи

        Raises:
            ValueError: Если проект не найден
        """
        # Проверяем существование проекта
        project = self.project_repo.get_project(project_id)
        if not project:
            raise ValueError(f"Проект с ID {project_id} не найден")

        # Создаем задачу
        is_group = task_data.get("is_group", False)

        task = Task(
            project_id=project_id,
            name=task_data["name"],
            duration=task_data["duration"],
            working_duration=task_data.get("working_duration", task_data["duration"]),
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
            predecessors = []
            for predecessor_id in task_data["predecessors"]:
                # Проверяем существование предшественника
                predecessor = self.task_repo.get_task(predecessor_id)
                if predecessor:
                    self.task_repo.add_dependency(task_id, predecessor_id)
                    predecessors.append(predecessor_id)

            # Обновляем задачу с информацией о предшественниках
            if predecessors:
                task.predecessors = predecessors
                self.task_repo.update_task(task)

        return task_id

    def delete_project(self, project_id: int) -> bool:
        """
        Удаляет проект и все связанные с ним задачи

        Args:
            project_id: ID проекта

        Returns:
            bool: True, если удаление успешно, иначе False

        Raises:
            ValueError: Если проект не найден
        """
        # Проверяем существование проекта
        project = self.project_repo.get_project(project_id)
        if not project:
            raise ValueError(f"Проект с ID {project_id} не найден")

        # Получаем список задач проекта
        tasks = self.task_repo.get_tasks_by_project(project_id, include_subtasks=True)

        # Удаляем задачи
        for task in tasks:
            self.task_repo.delete_task(task.id)

        # Удаляем проект
        return self.project_repo.delete_project(project_id)