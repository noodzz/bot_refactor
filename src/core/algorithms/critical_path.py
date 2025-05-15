import datetime
from typing import List, Dict, Any, Optional, Set, Tuple


def calculate_critical_path(task_dates: Dict[int, Dict[str, str]],
                            task_dependencies: Dict[int, List[int]]) -> List[int]:
    """
    Вычисляет критический путь проекта на основе дат задач и их зависимостей

    Args:
        task_dates (dict): Словарь с датами начала и окончания задач
        task_dependencies (dict): Словарь с зависимостями между задачами

    Returns:
        list: Список ID задач, образующих критический путь
    """
    # Если нет данных о датах, возвращаем пустой список
    if not task_dates:
        return []

    # Ищем самую позднюю дату окончания проекта
    latest_end_date = None
    latest_task_id = None

    for task_id, dates in task_dates.items():
        if 'end' in dates:
            try:
                end_date = datetime.datetime.strptime(dates['end'], '%Y-%m-%d')
                if latest_end_date is None or end_date > latest_end_date:
                    latest_end_date = end_date
                    latest_task_id = task_id
            except (ValueError, TypeError):
                continue

    # Если не нашли последнюю задачу, возвращаем пустой список
    if latest_task_id is None:
        return []

    # Находим путь от последней задачи к начальным задачам
    critical_path = []
    current_task_id = latest_task_id
    visited = set()  # Множество для отслеживания обработанных задач

    # Предотвращаем циклические зависимости
    while current_task_id is not None and current_task_id not in visited:
        critical_path.append(current_task_id)
        visited.add(current_task_id)

        # Находим предшественников текущей задачи
        predecessors = task_dependencies.get(current_task_id, [])

        if not predecessors:
            # Это начальная задача, путь построен
            break

        # Ищем предшественника с самой поздней датой окончания
        latest_predecessor_id = None
        latest_predecessor_end = None

        for predecessor_id in predecessors:
            if predecessor_id in task_dates and 'end' in task_dates[predecessor_id]:
                try:
                    end_date = datetime.datetime.strptime(task_dates[predecessor_id]['end'], '%Y-%m-%d')
                    if latest_predecessor_end is None or end_date > latest_predecessor_end:
                        latest_predecessor_end = end_date
                        latest_predecessor_id = predecessor_id
                except (ValueError, TypeError):
                    continue

        # Переходим к предшественнику или завершаем, если предшественников нет
        current_task_id = latest_predecessor_id

    # Возвращаем критический путь в обратном порядке (от начала к концу)
    return list(reversed(critical_path))


def identify_critical_tasks(early_times: List[float],
                            late_times: List[float],
                            task_mapping: Dict[int, int]) -> List[int]:
    """
    Определяет критические задачи на основе ранних и поздних времен событий

    Args:
        early_times: Список ранних времен наступления событий
        late_times: Список поздних времен наступления событий
        task_mapping: Сопоставление ID задач с вершинами в графе

    Returns:
        List[int]: Список ID критических задач
    """
    if not early_times or not late_times or len(early_times) != len(late_times):
        return []

    # Вычисляем резервы времени для каждой вершины
    reserves = []
    for i in range(len(early_times)):
        reserves.append(late_times[i] - early_times[i])

    # Определяем критические вершины (с нулевым резервом)
    critical_nodes = []
    for node, reserve in enumerate(reserves):
        if reserve == 0 and node > 0 and node < len(reserves) - 1:  # Исключаем источник и сток
            critical_nodes.append(node)

    # Преобразуем номера вершин в ID задач
    critical_tasks = []
    reverse_mapping = {v: k for k, v in task_mapping.items()}

    for node in critical_nodes:
        if node in reverse_mapping:
            critical_tasks.append(reverse_mapping[node])

    return critical_tasks


def calculate_project_duration(task_dates: Dict[int, Dict[str, str]],
                               start_date: str) -> int:
    """
    Рассчитывает длительность проекта в днях

    Args:
        task_dates: Словарь с датами задач
        start_date: Дата начала проекта

    Returns:
        int: Длительность проекта в днях
    """
    try:
        # Если нет задач с датами, возвращаем 0
        if not task_dates:
            return 0

        # Преобразуем дату начала проекта
        project_start = datetime.datetime.strptime(start_date, '%Y-%m-%d')

        # Находим самую позднюю дату окончания среди задач
        latest_end = None

        for task_id, dates in task_dates.items():
            if 'end' in dates:
                try:
                    end_date = datetime.datetime.strptime(dates['end'], '%Y-%m-%d')
                    if latest_end is None or end_date > latest_end:
                        latest_end = end_date
                except (ValueError, TypeError):
                    continue

        # Если не нашли даты окончания, возвращаем 0
        if latest_end is None:
            return 0

        # Вычисляем длительность проекта
        return (latest_end - project_start).days + 1  # +1 так как включаем день окончания

    except Exception:
        return 0