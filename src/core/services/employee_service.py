from typing import List, Dict, Any, Optional
import json
import logging
from datetime import datetime

from src.core.models.employee import Employee
from src.data.database.employee_repo import EmployeeRepository
from src.data.database.task_repo import TaskRepository

logger = logging.getLogger(__name__)


class EmployeeService:
    """Сервис для работы с сотрудниками"""

    def __init__(self, employee_repo: EmployeeRepository, task_repo: TaskRepository):
        """
        Инициализирует сервис сотрудников

        Args:
            employee_repo: Репозиторий сотрудников
            task_repo: Репозиторий задач
        """
        self.employee_repo = employee_repo
        self.task_repo = task_repo

    def get_all_employees(self) -> List[Employee]:
        """
        Возвращает список всех сотрудников

        Returns:
            List[Employee]: Список сотрудников
        """
        return self.employee_repo.get_employees()

    def get_employees_by_position(self, position: str) -> List[Employee]:
        """
        Возвращает список сотрудников определенной должности

        Args:
            position: Должность

        Returns:
            List[Employee]: Список сотрудников
        """
        return self.employee_repo.get_employees_by_position(position)

    def get_employee(self, employee_id: int) -> Employee:
        """
        Возвращает информацию о сотруднике

        Args:
            employee_id: ID сотрудника

        Returns:
            Employee: Объект сотрудника

        Raises:
            ValueError: Если сотрудник не найден
        """
        employee = self.employee_repo.get_employee(employee_id)
        if not employee:
            raise ValueError(f"Сотрудник с ID {employee_id} не найден")

        return employee

    def is_available(self, employee_id: int, date_str: str) -> bool:
        """
        Проверяет, доступен ли сотрудник в указанную дату

        Args:
            employee_id: ID сотрудника
            date_str: Дата в формате 'YYYY-MM-DD'

        Returns:
            bool: True, если сотрудник доступен, иначе False
        """
        try:
            employee = self.get_employee(employee_id)

            # Получаем день недели (0 - понедельник, 6 - воскресенье)
            # Преобразуем формат даты 'YYYY-MM-DD' в объект datetime
            dt = datetime.strptime(date_str, '%Y-%m-%d')
            weekday = dt.weekday() + 1  # +1 чтобы привести к формату 1=пн, 7=вс

            # Проверяем, не выходной ли это день
            is_day_off = weekday in employee.days_off

            # Отладочная информация
            logger.debug(f"Проверка доступности {employee.name} на {date_str}: "
                         f"день недели {weekday}, выходные дни {employee.days_off}, "
                         f"результат: {'недоступен' if is_day_off else 'доступен'}")

            return not is_day_off
        except Exception as e:
            logger.error(f"Ошибка при проверке доступности сотрудника: {str(e)}")
            return False

    def get_available_employees(self, position: str, date: str) -> List[Employee]:
        """
        Возвращает список доступных сотрудников определенной должности на указанную дату

        Args:
            position: Должность
            date: Дата в формате 'YYYY-MM-DD'

        Returns:
            List[Employee]: Список доступных сотрудников
        """
        try:
            employees = self.get_employees_by_position(position)
            available_employees = []

            for employee in employees:
                if self.is_available(employee.id, date):
                    available_employees.append(employee)

            return available_employees

        except Exception as e:
            logger.error(f"Ошибка при получении списка доступных сотрудников: {str(e)}")
            return []

    def get_employee_workload(self, project_id: int) -> Dict[int, Dict[str, Any]]:
        """
        Возвращает распределение задач по сотрудникам для проекта с учетом одноименных подзадач

        Args:
            project_id: ID проекта

        Returns:
            dict: Словарь, где ключ - сотрудник, значение - список задач
        """
        try:
            # Получаем всех сотрудников
            employees = self.get_all_employees()

            # Создаем словарь для хранения задач сотрудников
            employee_tasks = {}

            # Сначала загрузим все задачи проекта для получения информации о родительских задачах
            all_tasks = self.task_repo.get_tasks_by_project(project_id, include_subtasks=True)

            # Создаем словарь для получения имени родительской задачи
            parent_task_map = {}
            for task in all_tasks:
                if task.parent_id:
                    # Находим родительскую задачу
                    parent = next((t for t in all_tasks if t.id == task.parent_id), None)
                    if parent:
                        parent_task_map[task.id] = parent.name

            # Создаем словарь для отслеживания уже добавленных задач для каждого сотрудника
            processed_task_ids = {}  # employee_id -> set of task IDs

            # Группируем задачи по сотрудникам
            for task in all_tasks:
                employee_id = task.employee_id
                if not employee_id:
                    continue

                # Инициализируем структуры, если это первая задача для сотрудника
                if employee_id not in employee_tasks:
                    employee_tasks[employee_id] = {
                        'name': '',
                        'position': '',
                        'tasks': []
                    }
                    processed_task_ids[employee_id] = set()

                # Находим сотрудника
                employee = next((e for e in employees if e.id == employee_id), None)
                if employee:
                    employee_tasks[employee_id]['name'] = employee.name
                    employee_tasks[employee_id]['position'] = employee.position

                    # Используем ID задачи для уникальной идентификации
                    task_id = task.id

                    # Проверяем, не добавляли ли мы уже эту задачу для этого сотрудника
                    if task_id not in processed_task_ids[employee_id]:
                        processed_task_ids[employee_id].add(task_id)

                        # Получаем название задачи с учетом родительской задачи
                        task_name = task.name
                        if task.parent_id and task.id in parent_task_map:
                            # Для подзадач формируем название "Родительская задача - Подзадача"
                            display_name = f"{parent_task_map[task.id]} - {task_name}"
                        else:
                            display_name = task_name

                        employee_tasks[employee_id]['tasks'].append({
                            'id': task_id,
                            'name': display_name,  # Используем расширенное имя для отображения
                            'start_date': task.start_date,
                            'end_date': task.end_date,
                            'duration': task.duration,
                            'parallel': task.parallel
                        })

            return employee_tasks

        except Exception as e:
            logger.error(f"Ошибка при получении распределения задач: {str(e)}")
            raise ValueError(f"Ошибка при получении распределения задач: {str(e)}")

    def generate_workload_report(self, project_id: int) -> str:
        """
        Генерирует отчет о распределении задач по сотрудникам с учетом параллельных задач

        Args:
            project_id: ID проекта

        Returns:
            str: Текстовый отчет
        """
        try:
            # Получаем данные о проекте
            project = self.task_repo.get_project(project_id)
            if not project:
                raise ValueError(f"Проект с ID {project_id} не найден")

            # Получаем распределение задач
            workload = self.get_employee_workload(project_id)

            # Создаем отчет
            report = f"Отчет о распределении задач для проекта '{project.name}'\n\n"

            if not workload:
                report += "Ни одной задачи не назначено на сотрудников.\n"
                return report

            # Подсчитываем загрузку каждого сотрудника с учетом параллельных задач
            employee_load = {}
            for employee_id, data in workload.items():
                # Группируем задачи по дате начала
                tasks_by_date = {}
                non_dated_tasks = []

                for task in data['tasks']:
                    start_date = task.get('start_date')
                    if start_date:
                        if start_date not in tasks_by_date:
                            tasks_by_date[start_date] = []
                        tasks_by_date[start_date].append(task)
                    else:
                        # Задачи без даты обрабатываем отдельно
                        non_dated_tasks.append(task)

                # Расчет загрузки для задач с датами
                total_duration = 0
                for date, tasks in tasks_by_date.items():
                    # Группируем по признаку параллельности
                    parallel_tasks = [t for t in tasks if t.get('parallel')]
                    sequential_tasks = [t for t in tasks if not t.get('parallel')]

                    # Для параллельных задач берем максимальную длительность
                    parallel_duration = max(
                        [t.get('working_duration', t['duration']) for t in parallel_tasks]) if parallel_tasks else 0

                    # Для последовательных задач суммируем
                    sequential_duration = sum(t.get('working_duration', t['duration']) for t in sequential_tasks)

                    # Добавляем к общей длительности
                    total_duration += (parallel_duration + sequential_duration)

                # Добавляем длительность задач без дат
                for task in non_dated_tasks:
                    # Используем working_duration если доступно, иначе duration
                    working_duration = task.get('working_duration', task['duration'])
                    total_duration += working_duration

                employee_load[employee_id] = total_duration

            # Группируем сотрудников по должностям
            positions = {}
            for employee_id, data in workload.items():
                position = data['position']
                if position not in positions:
                    positions[position] = []

                positions[position].append(employee_id)

            # Формируем отчет по должностям
            for position, employee_ids in positions.items():
                report += f"\n== {position} ==\n"

                for employee_id in employee_ids:
                    data = workload[employee_id]
                    report += f"\n{data['name']} - {employee_load[employee_id]} дней загрузки\n"

                    # Задачи сотрудника
                    for task in data['tasks']:
                        date_range = ""
                        if task.get('start_date') and task.get('end_date'):
                            date_range = f" ({task['start_date']} - {task['end_date']})"

                        report += f"• {task['name']} - {task['duration']} дн.{date_range}\n"

            return report

        except Exception as e:
            logger.error(f"Ошибка при создании отчета: {str(e)}")
            raise ValueError(f"Ошибка при создании отчета: {str(e)}")

    def check_employee_workload(self, employee_id: int, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """
        Проверяет загрузку сотрудника в указанном диапазоне дат

        Args:
            employee_id: ID сотрудника
            start_date: Дата начала в формате 'YYYY-MM-DD'
            end_date: Дата окончания в формате 'YYYY-MM-DD'

        Returns:
            list: Список задач, назначенных на сотрудника в указанном диапазоне
        """
        try:
            # Получаем все задачи, назначенные на сотрудника
            tasks = self.task_repo.get_tasks_by_employee(employee_id)

            # Фильтруем задачи по диапазону дат
            filtered_tasks = []
            for task in tasks:
                # Если у задачи есть даты начала и окончания, проверяем пересечение с указанным диапазоном
                if task.start_date and task.end_date:
                    # Проверяем, пересекаются ли диапазоны дат
                    if not (task.end_date < start_date or task.start_date > end_date):
                        filtered_tasks.append(task)

            return filtered_tasks

        except Exception as e:
            logger.error(f"Ошибка при проверке загрузки сотрудника: {str(e)}")
            raise ValueError(f"Ошибка при проверке загрузки сотрудника: {str(e)}")

    def get_category_by_position(self, position: str) -> Optional[str]:
        """
        Определяет категорию сотрудника по его должности

        Args:
            position: Должность сотрудника

        Returns:
            Optional[str]: Название категории ("ПМы", "Настройка", "Контент") или None
        """
        if not position:
            return None

        position = position.lower()

        # ПМы
        if "проектный менеджер" in position or "пм" in position or "менеджер" in position:
            return "ПМы"

        # Настройка (проверяем первым, так как имеет приоритет над "специалист")
        if "настройка" in position or "технический" in position or "руководитель настройки" in position:
            return "Настройка"

        # Контент
        if "контент" in position or "специалист" in position:
            return "Контент"

        return None