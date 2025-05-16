from typing import List, Dict, Any, Optional, Set
from collections import deque
import datetime
import logging

logger = logging.getLogger(__name__)


class NetworkModel:
    """
    Класс для работы с сетевой моделью проекта по методу критического пути (CPM)
    с использованием алгоритма Форда и строгим соблюдением зависимостей
    """

    def __init__(self):
        """Инициализирует объект сетевой модели"""
        self.graph = None
        self.tasks = None
        self.task_mapping = None
        self.reverse_mapping = None

    def calculate(self, project, tasks, employee_service=None):
        """
        Рассчитывает календарный план проекта, используя алгоритм Форда
        с учетом выходных дней и строгим соблюдением зависимостей

        Args:
            project (dict): Информация о проекте
            tasks (list): Список задач проекта
            employee_service: Сервис для работы с сотрудниками (для учета выходных)

        Returns:
            dict: Результаты расчета (длительность проекта, критический путь, даты задач)
        """
        # Проверяем, что список задач не пуст
        if not tasks:
            return {
                'duration': 0,
                'critical_path': [],
                'task_dates': {},
                'early_times': [],
                'late_times': [],
                'reserves': []
            }

        # Инициализируем переменные
        self.tasks = list(tasks)  # Создаем копию списка задач
        self.graph = self._build_graph(self.tasks)

        # Проверяем, что граф не пуст
        if not self.graph:
            return {
                'duration': 0,
                'critical_path': [],
                'task_dates': {},
                'early_times': [],
                'late_times': [],
                'reserves': []
            }

        # Проверяем граф на цикличность
        if self._has_cycle():
            logger.warning("Обнаружен цикл в графе зависимостей! Результаты расчета могут быть некорректными.")
            return {
                'duration': 0,
                'critical_path': [],
                'task_dates': {},
                'early_times': [],
                'late_times': [],
                'reserves': [],
                'error': 'Обнаружен цикл в графе зависимостей'
            }

        # Применяем алгоритм Форда для вычисления ранних времен наступления событий
        early_times = self._calculate_early_times()

        # Проверяем, что результат не пуст
        if not early_times:
            return {
                'duration': 0,
                'critical_path': [],
                'task_dates': {},
                'early_times': [],
                'late_times': [],
                'reserves': []
            }

        # Вычисляем поздние времена наступления событий
        late_times = self._calculate_late_times(early_times)

        # Проверяем, что результат не пуст
        if not late_times:
            return {
                'duration': 0,
                'critical_path': [],
                'task_dates': {},
                'early_times': early_times,
                'late_times': [],
                'reserves': []
            }

        # Определяем резервы времени
        reserves = self._calculate_reserves(early_times, late_times)

        # Находим критический путь на основе резервов времени
        critical_path = self._find_critical_path(reserves)

        # Получаем зависимости между задачами
        dependencies = self._get_all_dependencies()

        # Создаем словарь задач для быстрого доступа
        task_dict = {task.get('id'): task for task in tasks}

        # Вычисляем даты начала и окончания задач
        # В зависимости от наличия сервиса сотрудников используем разные методы
        if employee_service:
            # Используем улучшенный метод с учетом выходных дней
            task_dates = self._calculate_task_dates_with_days_off(project['start_date'], early_times, employee_service)
        else:
            # Используем простой метод без учета выходных
            task_dates = self._calculate_task_dates(project['start_date'], early_times)

        # КЛЮЧЕВОЕ УЛУЧШЕНИЕ: корректируем даты с учетом зависимостей
        task_dates = self._correct_dates_for_dependencies(task_dates, dependencies, task_dict)

        # Длительность проекта (в рабочих днях)
        workday_duration = early_times[-1] if early_times and len(early_times) > 0 else 0

        # Определяем календарную длительность проекта
        if task_dates:
            start_dates = [datetime.datetime.strptime(dates['start'], '%Y-%m-%d') for dates in task_dates.values()]
            end_dates = [datetime.datetime.strptime(dates['end'], '%Y-%m-%d') for dates in task_dates.values()]

            if start_dates and end_dates:
                project_start = min(start_dates)
                project_end = max(end_dates)
                calendar_duration = (project_end - project_start).days + 1  # +1 для включения дня окончания
            else:
                calendar_duration = workday_duration
        else:
            calendar_duration = workday_duration

        return {
            'duration': calendar_duration,
            'workday_duration': workday_duration,
            'critical_path': critical_path,
            'task_dates': task_dates,
            'early_times': early_times,
            'late_times': late_times,
            'reserves': reserves,
            'dependencies': dependencies  # Добавляем зависимости в результат
        }

    def _build_graph(self, tasks):
        """
        Строит сетевую модель (граф) на основе задач проекта

        Args:
            tasks (list): Список задач проекта

        Returns:
            dict: Граф зависимостей в формате {node: [(neighbor, weight)]}
        """
        # Проверяем, что список задач не пуст
        if not tasks:
            return {}

        # Создаем словарь для сопоставления идентификаторов задач с вершинами графа
        self.task_mapping = {}
        self.reverse_mapping = {}

        # Инициализируем граф
        graph = {}

        # Добавляем фиктивный источник (вершина 0)
        graph[0] = []

        # Добавляем задачи в граф
        node_id = 1
        for task in tasks:
            if 'id' in task:  # Проверяем, что задача имеет id
                self.task_mapping[task['id']] = node_id
                self.reverse_mapping[node_id] = task['id']
                node_id += 1

        # Проверяем, что у нас есть хотя бы одна задача
        if node_id == 1:
            return {}

        # Добавляем фиктивный сток (вершина node_id)
        self.reverse_mapping[node_id] = 'sink'
        sink_id = node_id

        # Сначала получаем все зависимости и зависимые задачи
        task_dependencies = {}
        task_has_dependents = set()

        for task in tasks:
            if 'id' not in task:  # Пропускаем задачи без id
                continue

            task_id = task['id']
            dependencies = self._get_task_dependencies(task_id)
            task_dependencies[task_id] = dependencies

            # Отмечаем все задачи, от которых зависит текущая
            for dep_id in dependencies:
                task_has_dependents.add(dep_id)

        # Инициализируем вершины графа
        for i in range(node_id + 1):
            if i not in graph:
                graph[i] = []

        # Добавляем дуги в граф
        for task in tasks:
            if 'id' not in task:  # Пропускаем задачи без id
                continue

            task_id = task['id']

            # Проверяем, есть ли у задачи поле duration
            if 'duration' not in task:
                continue

            dependencies = task_dependencies.get(task_id, [])

            if dependencies:
                # Если есть зависимости, добавляем дуги от них к текущей задаче
                for dep_id in dependencies:
                    if dep_id in self.task_mapping:
                        graph[self.task_mapping[dep_id]].append((self.task_mapping[task_id], task['duration']))
            else:
                # Если нет зависимостей, добавляем дугу от источника
                graph[0].append((self.task_mapping[task_id], 0))

            # Если нет зависящих задач, добавляем дугу к стоку
            if task_id not in task_has_dependents:
                graph[self.task_mapping[task_id]].append((sink_id, 0))

        return graph

    def _get_task_dependencies(self, task_id):
        """
        Возвращает список идентификаторов задач, от которых зависит указанная задача

        Args:
            task_id: ID задачи

        Returns:
            list: Список ID задач-предшественников
        """
        import json

        dependencies = []

        # Проверяем сначала в атрибуте predecessors
        for task in self.tasks:
            if task.get('id') == task_id and 'predecessors' in task:
                # Пытаемся получить предшественников
                task_predecessors = task.get('predecessors')

                # Преобразуем предшественников в список
                if isinstance(task_predecessors, list):
                    dependencies = task_predecessors
                elif isinstance(task_predecessors, str):
                    try:
                        # Пытаемся преобразовать JSON-строку в список
                        dependencies = json.loads(task_predecessors)
                    except json.JSONDecodeError:
                        dependencies = []

                # Если это не список, создаем пустой список
                if not isinstance(dependencies, list):
                    dependencies = []

                break

        return dependencies

    def _get_all_dependencies(self):
        """
        Возвращает все зависимости между задачами проекта

        Returns:
            dict: Словарь с зависимостями, где ключ - ID задачи, значение - список ID зависимостей
        """
        dependencies = {}

        for task in self.tasks:
            task_id = task.get('id')
            if task_id is None:
                continue

            dependencies[task_id] = self._get_task_dependencies(task_id)

        return dependencies

    def _has_cycle(self):
        """
        Проверяет граф на наличие циклов

        Returns:
            bool: True, если в графе есть цикл, иначе False
        """
        visited = set()
        rec_stack = set()

        # Создаем копию графа для безопасной итерации
        graph_copy = {k: list(v) for k, v in self.graph.items()}

        def dfs(node):
            visited.add(node)
            rec_stack.add(node)

            for neighbor, _ in graph_copy.get(node, []):
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True

            rec_stack.remove(node)
            return False

        # Создаем копию ключей для безопасной итерации
        graph_nodes = list(graph_copy.keys())

        for node in graph_nodes:
            if node not in visited:
                if dfs(node):
                    return True

        return False

    def _calculate_early_times(self):
        """
        Вычисляет ранние времена наступления событий, используя алгоритм Форда

        Returns:
            list: Список ранних времен наступления для каждой вершины
        """
        # Проверяем, что граф не пуст
        if not self.graph:
            return []

        # Определяем количество вершин в графе
        try:
            n = max(self.graph.keys()) + 1
        except ValueError:  # Если граф пуст
            return []

        # Инициализируем массив ранних времен
        early_times = [0] * n

        # Создаем копию графа для безопасной итерации
        graph_copy = {k: list(v) for k, v in self.graph.items()}

        # Флаг для отслеживания изменений
        changed = True
        iteration_count = 0
        max_iterations = n * 10  # Ограничение на количество итераций

        # Выполняем алгоритм Форда
        while changed and iteration_count < max_iterations:
            changed = False
            iteration_count += 1

            for node in range(n):
                for neighbor, weight in graph_copy.get(node, []):
                    # Проверяем, что neighbor не выходит за пределы списка
                    if 0 <= neighbor < n:
                        if early_times[neighbor] < early_times[node] + weight:
                            early_times[neighbor] = early_times[node] + weight
                            changed = True

        return early_times

    def _calculate_late_times(self, early_times):
        """
        Вычисляет поздние времена наступления событий

        Args:
            early_times (list): Список ранних времен наступления

        Returns:
            list: Список поздних времен наступления для каждой вершины
        """
        # Проверяем, что список ранних времен не пуст
        if not early_times:
            return []

        # Определяем количество вершин в графе
        n = len(early_times)

        # Проверяем, что у нас есть хотя бы один узел (источник)
        if n == 0:
            return []

        # Общая длительность проекта - это раннее время наступления последнего события
        project_duration = early_times[n - 1]

        # Инициализируем массив поздних времен максимальным значением (длительность проекта)
        late_times = [project_duration] * n

        # Создаем обратный граф
        reverse_graph = {}
        for i in range(n):
            reverse_graph[i] = []

        # Заполняем обратный граф
        for node, edges in self.graph.items():
            for neighbor, weight in edges:
                if 0 <= neighbor < n:
                    reverse_graph[neighbor].append((node, weight))

        # Выполняем алгоритм Форда для обратного графа (проход назад)
        changed = True
        iteration_count = 0
        max_iterations = n * 10  # Ограничение на количество итераций

        while changed and iteration_count < max_iterations:
            changed = False
            iteration_count += 1

            for node in range(n - 1, -1, -1):
                for predecessor, weight in reverse_graph.get(node, []):
                    # Проверяем, что predecessor не выходит за пределы списка
                    if 0 <= predecessor < n:
                        if late_times[predecessor] > late_times[node] - weight:
                            late_times[predecessor] = late_times[node] - weight
                            changed = True

        return late_times

    def _calculate_reserves(self, early_times, late_times):
        """
        Вычисляет резервы времени для каждой вершины

        Args:
            early_times (list): Список ранних времен наступления
            late_times (list): Список поздних времен наступления

        Returns:
            list: Список резервов времени для каждой вершины
        """
        reserves = []
        for i in range(len(early_times)):
            reserves.append(late_times[i] - early_times[i])

        return reserves

    def _find_critical_path(self, reserves):
        """
        Находит критический путь в графе (вершины с нулевым резервом)

        Args:
            reserves (list): Список резервов времени

        Returns:
            list: Список идентификаторов задач, образующих критический путь
        """
        critical_nodes = []

        # Находим вершины с нулевым резервом времени (исключая источник и сток)
        for node, reserve in enumerate(reserves):
            if reserve == 0 and node > 0 and node < len(reserves) - 1:
                critical_nodes.append(node)

        # Преобразуем номера вершин в идентификаторы задач
        critical_path = []
        for node in critical_nodes:
            if node in self.reverse_mapping and self.reverse_mapping[node] != 'sink':
                critical_path.append(self.reverse_mapping[node])

        return critical_path

    def _calculate_task_dates(self, project_start_date, early_times):
        """
        Вычисляет даты начала и окончания задач на основе ранних времен

        Args:
            project_start_date (str): Дата начала проекта (YYYY-MM-DD)
            early_times (list): Список ранних времен наступления

        Returns:
            dict: Словарь с датами начала и окончания для каждой задачи
        """
        import datetime

        # Преобразуем дату начала проекта
        start_date = datetime.datetime.strptime(project_start_date, '%Y-%m-%d')

        # Словарь с датами для задач
        task_dates = {}

        # Для каждой задачи вычисляем даты на основе ранних времен
        for task_id, node_id in self.task_mapping.items():
            # Находим соответствующую задачу
            task = next((t for t in self.tasks if t.get('id') == task_id), None)
            if not task:
                continue

            # Получаем раннее время начала задачи
            early_start = early_times[node_id - 1] if node_id > 0 else 0

            # Вычисляем дату начала
            task_start = start_date + datetime.timedelta(days=early_start)

            # Вычисляем дату окончания
            task_duration = task.get('duration', 1)
            task_end = task_start + datetime.timedelta(days=task_duration - 1)  # -1 т.к. включаем день начала

            # Сохраняем даты
            task_dates[task_id] = {
                'start': task_start.strftime('%Y-%m-%d'),
                'end': task_end.strftime('%Y-%m-%d')
            }

        return task_dates

    def _calculate_task_dates_with_days_off(self, project_start_date, early_times, employee_service):
        """
        Вычисляет даты начала и окончания задач с учетом выходных дней

        Args:
            project_start_date (str): Дата начала проекта (YYYY-MM-DD)
            early_times (list): Список ранних времен наступления
            employee_service: Сервис для работы с сотрудниками

        Returns:
            dict: Словарь с датами начала и окончания для каждой задачи
        """
        import datetime

        # Преобразуем дату начала проекта
        start_date = datetime.datetime.strptime(project_start_date, '%Y-%m-%d')

        # Получаем корпоративные выходные дни (по умолчанию суббота и воскресенье)
        corp_days_off = [6, 7]  # 6=суббота, 7=воскресенье

        # Словарь с датами для задач
        task_dates = {}

        # Для каждой задачи вычисляем даты на основе ранних времен
        for task_id, node_id in self.task_mapping.items():
            # Находим соответствующую задачу
            task = next((t for t in self.tasks if t.get('id') == task_id), None)
            if not task:
                continue

            # Получаем раннее время начала задачи в рабочих днях
            early_start_workdays = early_times[node_id - 1] if node_id > 0 else 0

            # Получаем дни, которые являются выходными для конкретной задачи
            days_off = corp_days_off.copy()

            # Если задаче назначен сотрудник с персональными выходными, учитываем их
            employee_id = task.get('employee_id')
            if employee_id and employee_service:
                try:
                    employee = employee_service.get_employee(employee_id)
                    if employee and hasattr(employee, 'days_off') and employee.days_off:
                        # Заменяем стандартные выходные на выходные сотрудника
                        days_off = employee.days_off
                except:
                    pass  # Используем корпоративные выходные, если не удалось получить выходные сотрудника

            # Вычисляем реальную дату начала с учетом выходных дней
            current_date = start_date
            workdays_count = 0

            # Пропускаем выходные дни до начала задачи
            while workdays_count < early_start_workdays:
                # Проверяем, не выходной ли это день
                weekday = current_date.weekday() + 1  # +1 чтобы привести к формату 1=пн, 7=вс
                if weekday not in days_off:
                    workdays_count += 1

                current_date += datetime.timedelta(days=1)

            # Отступаем на один день назад, так как последний день был уже учтен
            task_start = current_date - datetime.timedelta(days=1)

            # Пропускаем выходные в начале задачи, если задача начинается с выходного
            weekday = task_start.weekday() + 1
            while weekday in days_off:
                task_start += datetime.timedelta(days=1)
                weekday = task_start.weekday() + 1

            # Вычисляем дату окончания с учетом выходных
            task_duration = task.get('duration', 1)
            workdays_count = 1  # Начинаем с 1, так как первый рабочий день уже найден
            current_date = task_start + datetime.timedelta(days=1)

            # Считаем рабочие дни до окончания задачи
            while workdays_count < task_duration:
                # Проверяем, не выходной ли это день
                weekday = current_date.weekday() + 1
                if weekday not in days_off:
                    workdays_count += 1

                current_date += datetime.timedelta(days=1)

            # Отступаем на один день назад, так как последний день был уже учтен
            task_end = current_date - datetime.timedelta(days=1)

            # Сохраняем даты
            task_dates[task_id] = {
                'start': task_start.strftime('%Y-%m-%d'),
                'end': task_end.strftime('%Y-%m-%d')
            }

        return task_dates

    def _correct_dates_for_dependencies(self, task_dates, dependencies, task_dict):
        """
        Корректирует даты начала и окончания задач с учетом зависимостей

        Args:
            task_dates (dict): Исходные даты задач
            dependencies (dict): Зависимости между задачами
            task_dict (dict): Словарь задач для быстрого доступа

        Returns:
            dict: Скорректированные даты задач
        """
        import datetime
        logger.info("Начинаем корректировку дат с учетом зависимостей")

        # Создаем копию дат для изменения
        corrected_dates = {}
        for task_id, dates in task_dates.items():
            corrected_dates[task_id] = dates.copy()

        # Создаем список задач для топологической сортировки
        task_list = []
        for task_id in dependencies.keys():
            if task_id in task_dict:
                task_list.append(task_dict[task_id])

        # Топологическая сортировка задач
        sorted_tasks = self._topological_sort(task_list, dependencies)

        # Для каждой задачи проверяем, все ли предшественники завершены до её начала
        for task in sorted_tasks:
            task_id = task.get('id')
            if task_id not in corrected_dates:
                continue

            # Получаем текущую дату начала
            start_date = datetime.datetime.strptime(corrected_dates[task_id]['start'], '%Y-%m-%d')

            # Проверяем всех предшественников
            predecessors = dependencies.get(task_id, [])

            # Находим самую позднюю дату окончания предшественников
            latest_end = None
            for pred_id in predecessors:
                if pred_id not in corrected_dates:
                    continue

                # Дата окончания предшественника
                pred_end = datetime.datetime.strptime(corrected_dates[pred_id]['end'], '%Y-%m-%d')

                # Обновляем самую позднюю дату
                if latest_end is None or pred_end > latest_end:
                    latest_end = pred_end

            # Если нужно, смещаем задачу
            if latest_end and start_date <= latest_end:
                # Вычисляем новую дату начала (следующий день после окончания предшественника)
                new_start = latest_end + datetime.timedelta(days=1)

                # Получаем длительность задачи
                duration = task.get('duration', 1)

                # Вычисляем новую дату окончания
                new_end = new_start + datetime.timedelta(days=duration - 1)

                # Обновляем даты
                corrected_dates[task_id] = {
                    'start': new_start.strftime('%Y-%m-%d'),
                    'end': new_end.strftime('%Y-%m-%d')
                }

                logger.info(
                    f"Смещена задача {task_id} '{task.get('name')}' с {start_date.strftime('%Y-%m-%d')} на {new_start.strftime('%Y-%m-%d')} из-за зависимостей")

                # Каскадно обновляем все зависимые задачи
                self._update_dependent_tasks(task_id, dependencies, corrected_dates, task_dict)

        return corrected_dates

    def _update_dependent_tasks(self, task_id, dependencies, dates, task_dict):
        """
        Рекурсивно обновляет даты зависимых задач

        Args:
            task_id: ID задачи, даты которой изменились
            dependencies: Словарь зависимостей
            dates: Словарь с датами задач
            task_dict: Словарь задач для быстрого доступа
        """
        import datetime

        # Находим все задачи, которые зависят от текущей
        dependent_tasks = []
        for dep_id, preds in dependencies.items():
            if task_id in preds:
                dependent_tasks.append(dep_id)

        # Если зависимых задач нет, выходим
        if not dependent_tasks:
            return

        # Получаем дату окончания текущей задачи
        end_date = datetime.datetime.strptime(dates[task_id]['end'], '%Y-%m-%d')

        # Обрабатываем каждую зависимую задачу
        for dep_id in dependent_tasks:
            if dep_id not in dates or dep_id not in task_dict:
                continue

            # Получаем дату начала зависимой задачи
            start_date = datetime.datetime.strptime(dates[dep_id]['start'], '%Y-%m-%d')

            # Если начало зависимой задачи раньше или равно окончанию текущей,
            # нужно сместить зависимую задачу
            if start_date <= end_date:
                # Новая дата начала - следующий день после окончания текущей задачи
                new_start = end_date + datetime.timedelta(days=1)

                # Получаем длительность зависимой задачи
                task = task_dict[dep_id]
                duration = task.get('duration', 1)

                # Вычисляем новую дату окончания
                new_end = new_start + datetime.timedelta(days=duration - 1)

                # Обновляем даты
                dates[dep_id] = {
                    'start': new_start.strftime('%Y-%m-%d'),
                    'end': new_end.strftime('%Y-%m-%d')
                }

                logger.info(
                    f"Каскадное смещение: задача {dep_id} '{task.get('name')}' смещена на {new_start.strftime('%Y-%m-%d')} из-за изменения дат задачи {task_id}")

                # Рекурсивно обновляем все задачи, зависящие от этой
                self._update_dependent_tasks(dep_id, dependencies, dates, task_dict)

    def _topological_sort(self, tasks, dependencies):
        """
        Выполняет топологическую сортировку списка задач с учетом зависимостей

        Args:
            tasks: Список задач
            dependencies: Словарь зависимостей, где ключ - ID задачи, значение - список ID зависимостей

        Returns:
            list: Отсортированный список задач
        """
        # Создаем словарь для подсчета входящих ребер
        in_degree = {}
        for task in tasks:
            task_id = task.get('id')
            if task_id is not None:
                in_degree[task_id] = 0

        # Подсчитываем входящие ребра для каждой задачи
        for task_id, deps in dependencies.items():
            for dep_id in deps:
                if dep_id in in_degree:
                    in_degree[dep_id] += 1

        # Очередь для задач без входящих ребер
        queue = deque()
        for task in tasks:
            task_id = task.get('id')
            if task_id is not None and task_id in in_degree and in_degree[task_id] == 0:
                queue.append(task)

        # Результат топологической сортировки
        sorted_tasks = []

        # Обработка очереди
        while queue:
            task = queue.popleft()
            sorted_tasks.append(task)

            task_id = task.get('id')
            if task_id is None:
                continue

            # Находим все зависимые задачи
            for dep_id in [id for id, deps in dependencies.items() if task_id in deps]:
                if dep_id in in_degree:
                    in_degree[dep_id] -= 1
                    if in_degree[dep_id] == 0:
                        # Находим задачу по ID
                        for t in tasks:
                            if t.get('id') == dep_id:
                                queue.append(t)
                                break

        # Проверяем, все ли задачи обработаны (может быть цикл)
        if len(sorted_tasks) < len(tasks):
            # Добавляем оставшиеся задачи в конец
            for task in tasks:
                if task not in sorted_tasks:
                    sorted_tasks.append(task)

        return sorted_tasks