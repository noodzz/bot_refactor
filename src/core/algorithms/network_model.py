import datetime
import json
from collections import defaultdict, deque
from typing import Dict, List, Tuple, Any, Optional, Set
import logging

logger = logging.getLogger(__name__)


class NetworkModel:
    """
    Класс для работы с сетевой моделью проекта по методу критического пути (CPM)
    """

    def __init__(self):
        """Инициализирует объект сетевой модели"""
        self.graph = None
        self.tasks = None
        self.task_mapping = None
        self.reverse_mapping = None

    def calculate(self, project: Dict[str, Any], tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Рассчитывает календарный план проекта, используя алгоритм Форда

        Args:
            project (dict): Информация о проекте
            tasks (list): Список задач проекта

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
            logger.warning("Обнаружен цикл в графе зависимостей. "
                           "Невозможно рассчитать календарный план.")
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

        # Находим критический путь
        critical_path = self._find_critical_path(reserves)

        # Вычисляем даты начала и окончания задач
        task_dates = self._calculate_task_dates(project['start_date'], early_times)

        # Длительность проекта
        project_duration = early_times[-1] if early_times and len(early_times) > 0 else 0

        # Если длительность все еще 0, но есть даты задач, вычисляем по датам
        if project_duration == 0 and task_dates:
            end_dates = []
            for task_id, dates in task_dates.items():
                if 'end' in dates:
                    try:
                        end_date = datetime.datetime.strptime(dates['end'], '%Y-%m-%d')
                        start_date = datetime.datetime.strptime(project['start_date'], '%Y-%m-%d')
                        days_diff = (end_date - start_date).days + 1
                        end_dates.append(days_diff)
                    except (ValueError, TypeError):
                        pass

            if end_dates:
                project_duration = max(end_dates)

        return {
            'duration': project_duration,
            'critical_path': critical_path,
            'task_dates': task_dates,
            'early_times': early_times,
            'late_times': late_times,
            'reserves': reserves
        }

    def _build_graph(self, tasks: List[Dict[str, Any]]) -> Optional[Dict[int, List[Tuple[int, int]]]]:
        """
        Строит сетевую модель на основе задач проекта

        Args:
            tasks (list): Список задач проекта

        Returns:
            dict: Граф зависимостей
        """
        # Проверяем, что список задач не пуст
        if not tasks:
            return {}

        # Создаем словарь для сопоставления идентификаторов задач с вершинами графа
        self.task_mapping = {}
        self.reverse_mapping = {}

        # Инициализируем граф
        graph = defaultdict(list)

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

    def _get_task_dependencies(self, task_id: int) -> List[int]:
        """
        Возвращает список идентификаторов задач, от которых зависит указанная задача
        """
        dependencies = []

        # Проверяем сначала в таблице dependencies
        for task in self.tasks:
            if task.get('id') == task_id and 'predecessors' in task:
                # Пытаемся получить предшественников
                task_predecessors = task.get('predecessors')

                logger.info(
                    f"Задача {task_id}: предшественники из БД = {task_predecessors}, тип: {type(task_predecessors)}")

                # Преобразуем предшественников в список
                if isinstance(task_predecessors, list):
                    dependencies = task_predecessors
                elif isinstance(task_predecessors, str):
                    try:
                        # Пытаемся преобразовать JSON-строку в список
                        dependencies = json.loads(task_predecessors)
                    except json.JSONDecodeError:
                        logger.error(
                            f"Ошибка при разборе JSON предшественников для задачи {task_id}: {task_predecessors}")
                        dependencies = []

                # Если это не список, создаем пустой список
                if not isinstance(dependencies, list):
                    dependencies = []

                logger.info(f"Задача {task_id}: итоговые предшественники = {dependencies}")
                break

        return dependencies

    def _has_cycle(self) -> bool:
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

    def _calculate_early_times(self) -> List[int]:
        """
        Вычисляет наиболее ранние времена наступления событий, используя алгоритм Форда

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

            for node in graph_copy:
                for neighbor, weight in graph_copy[node]:
                    # Проверяем, что neighbor не выходит за пределы списка
                    if 0 <= neighbor < n:
                        if early_times[neighbor] < early_times[node] + weight:
                            early_times[neighbor] = early_times[node] + weight
                            changed = True

        return early_times

    def _calculate_late_times(self, early_times: List[int]) -> List[int]:
        """
        Вычисляет наиболее поздние времена наступления событий

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

        # Инициализируем массив поздних времен
        late_times = [project_duration] * n

        # Строим обратный граф
        reverse_graph = defaultdict(list)

        # Создаем копию графа для безопасной итерации
        graph_copy = {k: list(v) for k, v in self.graph.items()}

        for node in graph_copy:
            for neighbor, weight in graph_copy[node]:
                # Проверяем, что neighbor не выходит за пределы списка
                if 0 <= neighbor < n:
                    reverse_graph[neighbor].append((node, weight))

        # Выполняем алгоритм Форда для обратного графа
        changed = True
        iteration_count = 0
        max_iterations = n * 10  # Ограничение на количество итераций

        while changed and iteration_count < max_iterations:
            changed = False
            iteration_count += 1

            for node in range(n - 1, -1, -1):
                for neighbor, weight in reverse_graph.get(node, []):
                    # Проверяем, что neighbor не выходит за пределы списка
                    if 0 <= neighbor < n:
                        if late_times[neighbor] > late_times[node] - weight:
                            late_times[neighbor] = late_times[node] - weight
                            changed = True

        return late_times

    def _calculate_reserves(self, early_times: List[int], late_times: List[int]) -> List[int]:
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

    def _find_critical_path(self, reserves: List[int]) -> List[int]:
        """
        Находит критический путь в графе

        Args:
            reserves (list): Список резервов времени

        Returns:
            list: Список идентификаторов задач, образующих критический путь
        """
        critical_nodes = []

        if not reserves or len(reserves) <= 2:  # Проверяем, что у нас есть хотя бы один узел (кроме источника и стока)
            return critical_nodes

        for node, reserve in enumerate(reserves):
            if reserve == 0 and node > 0 and node < len(reserves) - 1:  # Исключаем источник и сток
                critical_nodes.append(node)

        # Преобразуем идентификаторы вершин в идентификаторы задач
        critical_path = []
        for node in critical_nodes:
            if node in self.reverse_mapping and self.reverse_mapping[node] != 'sink':
                critical_path.append(self.reverse_mapping[node])

        return critical_path

    def _calculate_task_dates(self, project_start_date: str, early_times: List[int]) -> Dict[int, Dict[str, str]]:
        """
        Вычисляет даты начала и окончания задач с учетом зависимостей

        Args:
            project_start_date (str): Дата начала проекта (YYYY-MM-DD)
            early_times (list): Список ранних времен наступления

        Returns:
            dict: Словарь с датами начала и окончания для каждой задачи
        """
        # Преобразуем дату начала проекта
        start_date = datetime.datetime.strptime(project_start_date, '%Y-%m-%d')
        logger.info(f"Дата начала проекта: {start_date.strftime('%Y-%m-%d')}")

        # Словарь с датами для задач
        task_dates = {}

        # Получаем все задачи
        tasks = {}
        for task in self.tasks:
            if 'id' in task:
                tasks[task['id']] = task

        logger.info(f"Найдено {len(tasks)} задач")

        # Построим граф зависимостей (предшественники)
        dependencies = {}
        for task_id, task in tasks.items():
            predecessors = self._get_task_dependencies(task_id)
            dependencies[task_id] = predecessors
            logger.info(f"Задача {task_id} ({task.get('name', '?')}): предшественники = {predecessors}")

        # Вычисляем даты начала и окончания для каждой задачи
        # Начнем с задач без предшественников
        processed = set()
        task_end_dates = {}  # ID задачи -> дата окончания

        # Повторяем, пока не обработаем все задачи
        remaining = set(tasks.keys())

        # Пока есть необработанные задачи
        while remaining:
            # Найдем задачи, все предшественники которых уже обработаны
            ready_tasks = []
            for task_id in remaining:
                # Проверяем, все ли предшественники обработаны
                all_predecessors_done = True
                for pred_id in dependencies.get(task_id, []):
                    if pred_id not in processed:
                        all_predecessors_done = False
                        break

                if all_predecessors_done:
                    ready_tasks.append(task_id)

            # Если нет готовых задач, но остались необработанные,
            # значит у нас есть циклическая зависимость
            if not ready_tasks and remaining:
                logger.warning("Обнаружена циклическая зависимость! Обрабатываем все оставшиеся задачи.")
                ready_tasks = list(remaining)

            # Обрабатываем готовые задачи
            for task_id in ready_tasks:
                task = tasks[task_id]

                # Определяем дату начала задачи
                task_start = start_date  # По умолчанию - дата начала проекта

                # Если есть предшественники, дата начала - день после окончания самого позднего предшественника
                for pred_id in dependencies.get(task_id, []):
                    if pred_id in task_end_dates:
                        pred_end = task_end_dates[pred_id]
                        next_day = pred_end + datetime.timedelta(days=1)
                        if next_day > task_start:
                            task_start = next_day

                # Определяем дату окончания задачи
                duration = task.get('duration', 1)
                task_end = task_start + datetime.timedelta(days=duration - 1)  # -1, так как включаем последний день

                # Сохраняем даты
                task_dates[task_id] = {
                    'start': task_start.strftime('%Y-%m-%d'),
                    'end': task_end.strftime('%Y-%m-%d')
                }

                # Сохраняем дату окончания для будущих зависимых задач
                task_end_dates[task_id] = task_end

                # Помечаем задачу как обработанную
                processed.add(task_id)
                remaining.remove(task_id)

                logger.info(
                    f"Задача {task_id} ({task.get('name', '?')}): {task_start.strftime('%Y-%m-%d')} - {task_end.strftime('%Y-%m-%d')}")

        return task_dates

    def _topological_sort(self, dependencies: Dict[int, List[int]]) -> List[int]:
        """
        Выполняет топологическую сортировку графа зависимостей

        Args:
            dependencies: Словарь зависимостей, где ключ - задача, значение - список предшественников

        Returns:
            List[int]: Отсортированный список задач
        """
        # Создаем обратный граф: для каждой задачи список задач, зависящих от неё
        reversed_deps = {}
        all_tasks = set()

        for task_id, predecessors in dependencies.items():
            all_tasks.add(task_id)
            for pred in predecessors:
                all_tasks.add(pred)
                if pred not in reversed_deps:
                    reversed_deps[pred] = []
                reversed_deps[pred].append(task_id)

        # Инициализация
        visited = set()
        sorted_tasks = []

        # Рекурсивная функция для DFS
        def dfs(task_id):
            if task_id in visited:
                return
            visited.add(task_id)

            # Посещаем все зависимые задачи
            for dependent in reversed_deps.get(task_id, []):
                dfs(dependent)

            # После посещения всех зависимых, добавляем текущую задачу
            sorted_tasks.append(task_id)

        # Запускаем DFS с каждой задачи, которая не имеет предшественников
        for task_id in all_tasks:
            if not dependencies.get(task_id, []):
                dfs(task_id)

        # Возвращаем задачи в порядке их выполнения
        return sorted_tasks