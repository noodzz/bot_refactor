import datetime
from collections import deque
from typing import Dict, List, Tuple, Any, Optional
import logging

logger = logging.getLogger(__name__)


def check_employee_availability(employee_id: int, start_date: str, duration: int, employee_manager) -> bool:
    """
    Проверяет доступность сотрудника на указанный период с учетом выходных дней

    Args:
        employee_id (int): ID сотрудника
        start_date (str): Дата начала в формате 'YYYY-MM-DD'
        duration (int): Длительность задачи в днях
        employee_manager: Менеджер сотрудников

    Returns:
        bool: True, если сотрудник доступен на все дни периода, False в противном случае
    """
    try:
        # Получаем информацию о сотруднике
        employee = employee_manager.get_employee(employee_id)
        if not employee:
            logger.warning(f"Сотрудник с ID {employee_id} не найден")
            return False

        # Выводим дни недели, которые сотрудник указал как выходные
        logger.info(f"Сотрудник {employee.name} (ID: {employee_id}): выходные дни = {employee.days_off}")

        # Преобразуем дату начала в объект datetime
        current_date = datetime.datetime.strptime(start_date, '%Y-%m-%d')

        # Проверяем каждый день
        unavailable_days = []
        for day in range(duration):
            date_str = current_date.strftime('%Y-%m-%d')
            weekday = current_date.weekday() + 1  # +1 для формата 1-7 (пн-вс)

            # Проверяем доступность сотрудника на этот день
            if not employee_manager.is_available(employee_id, date_str):
                # День недоступен (выходной)
                logger.debug(f"Сотрудник {employee_id} недоступен на дату {date_str} (день недели: {weekday})")
                unavailable_days.append((date_str, weekday))

            # Переходим к следующему дню
            current_date += datetime.timedelta(days=1)

        if unavailable_days:
            logger.warning(
                f"Сотрудник {employee.name} (ID: {employee_id}) недоступен в следующие дни: {unavailable_days}")
            return False

        # Если все дни проверены и сотрудник доступен, возвращаем True
        return True

    except Exception as e:
        logger.error(f"Ошибка при проверке доступности сотрудника: {str(e)}")
        return False

def find_suitable_employee(position: str, start_date: str, duration: int,
                          employee_manager, employee_workload: Dict[int, int]) -> Optional[Tuple[int, str, str, int]]:
    """
    Находит подходящего сотрудника для выполнения задачи

    Args:
        position (str): Требуемая должность
        start_date (str): Дата начала задачи
        duration (int): Длительность задачи в днях
        employee_manager: Менеджер сотрудников
        employee_workload (dict): Текущая загрузка сотрудников

    Returns:
        Optional[Tuple[int, str, str, int]]: (employee_id, start_date, end_date, calendar_duration) или None, если не найден
    """
    try:
        # Получаем список сотрудников требуемой должности
        employees = employee_manager.get_employees_by_position(position)

        if not employees:
            logger.warning(f"Не найдены сотрудники с должностью '{position}'")
            return None

        best_employee = None
        best_start_date = None
        best_end_date = None
        best_duration = float('inf')
        best_workload = float('inf')

        for employee in employees:
            employee_id = employee.id

            # Рассчитываем даты с учетом выходных
            result = calculate_dates_with_days_off(
                {"duration": duration}, start_date, employee_id, employee_manager
            )

            if not result:
                # Если не удалось рассчитать даты, пропускаем сотрудника
                continue

            start_date_adj, end_date_adj, calendar_duration = result

            # Рассчитываем текущую загрузку сотрудника
            current_load = employee_workload.get(employee_id, 0)

            # Выбираем сотрудника с минимальной загрузкой или с минимальной длительностью выполнения
            if (best_employee is None or
                    current_load < best_workload or
                    (current_load == best_workload and calendar_duration < best_duration)):
                best_employee = employee
                best_start_date = start_date_adj
                best_end_date = end_date_adj
                best_duration = calendar_duration
                best_workload = current_load

        if best_employee:
            return best_employee.id, best_start_date, best_end_date, best_duration
        else:
            return None

    except Exception as e:
        logger.error(f"Ошибка при поиске подходящего сотрудника: {str(e)}")
        return None

def find_suitable_employee_with_days_off(position: str, start_date: str, duration: int,
                                        employee_manager, employee_workload: Dict[int, int]) -> Optional[int]:
    """
    Находит подходящего сотрудника с учетом его выходных дней

    Args:
        position (str): Требуемая должность
        start_date (str): Дата начала задачи
        duration (int): Длительность задачи в днях
        employee_manager: Менеджер сотрудников
        employee_workload (dict): Словарь текущей загрузки сотрудников

    Returns:
        Optional[int]: ID подходящего сотрудника или None, если не найден
    """
    # Получаем список сотрудников требуемой должности
    suitable_employees = employee_manager.get_employees_by_position(position)

    if not suitable_employees:
        logger.warning(f"Не найдены сотрудники с должностью '{position}'")
        return None

    # Отфильтровываем сотрудников, у которых в этот период нет выходных
    available_employees = []

    for employee in suitable_employees:
        if check_employee_availability(employee.id, start_date, duration, employee_manager):
            available_employees.append(employee)

    if not available_employees:
        logger.warning(f"Не найдены доступные сотрудники с должностью '{position}' на период с {start_date} на {duration} дней")
        return None

    # Выбираем наименее загруженного сотрудника из доступных
    best_employee = min(available_employees, key=lambda e: employee_workload.get(e.id, 0))
    employee_workload[best_employee.id] = employee_workload.get(best_employee.id, 0) + duration

    logger.info(f"Выбран сотрудник {best_employee.name} (ID: {best_employee.id}) с загрузкой {employee_workload[best_employee.id]} дней")
    return best_employee.id

def calculate_dates_with_days_off(task: Dict[str, Any], start_date_str: str,
                                 employee_id: int, employee_manager) -> Optional[Tuple[str, str, int]]:
    """
    Вычисляет реальные даты начала и окончания задачи с учетом выходных дней сотрудника

    Args:
        task (dict): Задача
        start_date_str (str): Дата начала
        employee_id (int): ID сотрудника
        employee_manager: Менеджер сотрудников

    Returns:
        Optional[Tuple[str, str, int]]: (start_date, end_date, calendar_duration) - дата начала, дата окончания и
               календарная длительность в днях, или None, если не удалось рассчитать
    """
    try:
        # Конвертируем дату в объект datetime
        start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d')

        # Определяем длительность задачи в рабочих днях
        duration = task.get('duration', 1)

        # Учитываем выходные дни
        current_date = start_date
        working_days = 0
        calendar_days = 0

        # Максимальное количество итераций для защиты от бесконечного цикла
        max_iterations = duration * 3  # Берем с запасом

        # Ищем первый рабочий день, начиная с даты начала
        first_day_found = False

        while not first_day_found and calendar_days < max_iterations:
            date_str = current_date.strftime('%Y-%m-%d')
            if employee_manager.is_available(employee_id, date_str):
                first_day_found = True
                start_date = current_date  # Обновляем дату начала
            else:
                current_date += datetime.timedelta(days=1)
                calendar_days += 1

        if not first_day_found:
            logger.warning(f"Не удалось найти рабочий день для сотрудника {employee_id} в ближайшие {max_iterations} дней!")
            return None

        # Сбрасываем счетчик и перезапускаем с новой даты начала
        calendar_days = 0
        current_date = start_date

        # Считаем все дни до набора нужного количества рабочих дней
        while working_days < duration and calendar_days < max_iterations:
            date_str = current_date.strftime('%Y-%m-%d')

            if employee_manager.is_available(employee_id, date_str):
                working_days += 1

            if working_days < duration:  # Не увеличиваем для последнего дня
                current_date += datetime.timedelta(days=1)
                calendar_days += 1

        if working_days < duration:
            logger.warning(f"Не удалось набрать {duration} рабочих дней для сотрудника {employee_id}!")
            return None

        # Дата окончания - текущая дата
        end_date = current_date

        # Календарная длительность - разница между датами + 1 (включаем последний день)
        actual_calendar_duration = (end_date - start_date).days + 1

        return (
            start_date.strftime('%Y-%m-%d'),
            end_date.strftime('%Y-%m-%d'),
            actual_calendar_duration
        )

    except Exception as e:
        logger.error(f"Ошибка при расчете дат с учетом выходных: {str(e)}")
        return None


def find_available_date(employee_id: int, start_date: str, duration: int, employee_manager) -> Tuple[
    Optional[str], Optional[str]]:
    """
    Находит ближайшую доступную дату для сотрудника с учетом выходных

    Args:
        employee_id (int): ID сотрудника
        start_date (str): Предполагаемая дата начала
        duration (int): Длительность задачи в днях
        employee_manager: Менеджер сотрудников

    Returns:
        Tuple[Optional[str], Optional[str]]: (start_date, end_date) - новая дата начала и окончания или (None, None), если не найдена
    """
    # Максимальное количество дней для поиска
    max_days = 60  # Увеличиваем для большего диапазона поиска

    try:
        # Получаем информацию о сотруднике
        employee = employee_manager.get_employee(employee_id)
        if not employee:
            logger.warning(f"Сотрудник с ID {employee_id} не найден")
            return None, None

        logger.info(
            f"Поиск доступных дат для сотрудника {employee.name} (ID: {employee_id}): выходные дни = {employee.days_off}")

        current_date = datetime.datetime.strptime(start_date, '%Y-%m-%d')
        end_date = current_date

        # Пробуем каждую дату как потенциальное начало периода
        for attempt in range(max_days):
            # Проверяем, не выходной ли день
            if not employee_manager.is_available(employee_id, current_date.strftime('%Y-%m-%d')):
                # Если текущий день - выходной, переходим к следующему
                logger.debug(
                    f"День {current_date.strftime('%Y-%m-%d')} - выходной для сотрудника {employee_id}, пробуем следующий")
                current_date += datetime.timedelta(days=1)
                continue

            # Пробуем период с текущей даты
            test_date = current_date
            consecutive_working_days = 0
            available_period = True

            while consecutive_working_days < duration:
                if not employee_manager.is_available(employee_id, test_date.strftime('%Y-%m-%d')):
                    # Встретили выходной день внутри периода
                    available_period = False
                    logger.debug(
                        f"Внутри проверяемого периода с {current_date.strftime('%Y-%m-%d')} обнаружен выходной {test_date.strftime('%Y-%m-%d')}")
                    break

                consecutive_working_days += 1
                end_date = test_date
                test_date += datetime.timedelta(days=1)

            if available_period:
                logger.info(
                    f"Найден доступный период для сотрудника {employee_id}: {current_date.strftime('%Y-%m-%d')} - {end_date.strftime('%Y-%m-%d')}")
                return current_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')

            # Сдвигаемся на один день и пробуем снова
            current_date += datetime.timedelta(days=1)

        logger.warning(f"Не удалось найти доступный период для сотрудника {employee_id} в течение {max_days} дней")
        return None, None

    except Exception as e:
        logger.error(f"Ошибка при поиске доступной даты: {str(e)}")
        return None, None

def topological_sort(graph: Dict[int, List[int]]) -> List[int]:
    """
    Выполняет топологическую сортировку графа

    Args:
        graph (dict): Граф зависимостей, где ключ - ID задачи,
                      значение - список ID задач-предшественников

    Returns:
        List[int]: Отсортированный список ID задач
    """
    # Подсчитываем входящие связи для каждой вершины
    in_degree = {node: 0 for node in graph}
    for node in graph:
        for neighbor in graph[node]:
            in_degree[neighbor] = in_degree.get(neighbor, 0) + 1

    # Инициализируем очередь вершинами без входящих связей
    queue = deque([node for node in graph if in_degree[node] == 0])
    result = []

    # Обходим граф
    while queue:
        node = queue.popleft()
        result.append(node)

        # Удаляем текущую вершину из графа
        for neighbor in graph[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    # Проверяем на циклы
    if len(result) != len(graph):
        logger.warning("В графе обнаружены циклы! Некоторые зависимости могут быть нарушены.")

        # Добавляем оставшиеся вершины
        remaining = [node for node in graph if node not in result]
        for node in remaining:
            result.append(node)

    # Результат содержит задачи в порядке зависимостей от предшественников к последователям
    # Нам нужен обратный порядок - от источников к стокам
    return list(reversed(result))
