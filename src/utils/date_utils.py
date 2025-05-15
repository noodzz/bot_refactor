import datetime
from typing import List, Optional, Tuple


def validate_date_format(date_str: str) -> bool:
    """
    Проверяет, что строка соответствует формату YYYY-MM-DD

    Args:
        date_str: Строка с датой

    Returns:
        bool: True, если формат корректный, иначе False
    """
    try:
        datetime.datetime.strptime(date_str, '%Y-%m-%d')
        return True
    except ValueError:
        return False


def format_date(date_str: str) -> str:
    """
    Форматирует дату для отображения

    Args:
        date_str (str): Дата в формате YYYY-MM-DD

    Returns:
        str: Отформатированная дата (DD.MM.YYYY)
    """
    if not date_str:
        return "Не указана"

    try:
        date = datetime.datetime.strptime(date_str, '%Y-%m-%d')
        return date.strftime('%d.%m.%Y')
    except ValueError:
        return date_str


def add_days_to_date(date_str: str, days: int) -> str:
    """
    Добавляет указанное количество дней к дате

    Args:
        date_str (str): Дата в формате YYYY-MM-DD
        days (int): Количество дней для добавления

    Returns:
        str: Новая дата в формате YYYY-MM-DD
    """
    date = datetime.datetime.strptime(date_str, '%Y-%m-%d')
    new_date = date + datetime.timedelta(days=days)
    return new_date.strftime('%Y-%m-%d')


def calculate_end_date(start_date: str, duration: int) -> str:
    """
    Вычисляет дату окончания задачи

    Args:
        start_date (str): Дата начала в формате YYYY-MM-DD
        duration (int): Длительность в днях

    Returns:
        str: Дата окончания в формате YYYY-MM-DD
    """
    return add_days_to_date(start_date, duration)


def get_working_days(start_date: str, end_date: str, days_off: List[int]) -> int:
    """
    Вычисляет количество рабочих дней в указанном интервале, исключая выходные дни

    Args:
        start_date (str): Дата начала в формате YYYY-MM-DD
        end_date (str): Дата окончания в формате YYYY-MM-DD
        days_off (list): Список дней недели, которые являются выходными (1 - понедельник, 7 - воскресенье)

    Returns:
        int: Количество рабочих дней
    """
    start = datetime.datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.datetime.strptime(end_date, '%Y-%m-%d')

    # Преобразуем дни недели из 1-7 в 0-6 (формат Python)
    python_days_off = [(day - 1) % 7 for day in days_off]

    working_days = 0
    current = start

    while current <= end:
        if current.weekday() not in python_days_off:
            working_days += 1
        current += datetime.timedelta(days=1)

    return working_days


def adjust_date_for_days_off(date_str: str, duration: int, days_off: List[int]) -> str:
    """
    Корректирует дату окончания задачи с учетом выходных дней

    Args:
        date_str (str): Дата начала в формате YYYY-MM-DD
        duration (int): Длительность в рабочих днях
        days_off (list): Список дней недели, которые являются выходными (1 - понедельник, 7 - воскресенье)

    Returns:
        str: Скорректированная дата окончания в формате YYYY-MM-DD
    """
    start = datetime.datetime.strptime(date_str, '%Y-%m-%d')

    # Преобразуем дни недели из 1-7 в 0-6 (формат Python)
    python_days_off = [(day - 1) % 7 for day in days_off]

    working_days = 0
    current = start

    while working_days < duration:
        current += datetime.timedelta(days=1)
        if current.weekday() not in python_days_off:
            working_days += 1

    return current.strftime('%Y-%m-%d')


def find_available_date(days_off: List[int], start_date: str, duration: int) -> Tuple[str, str]:
    """
    Находит доступную дату с учетом выходных дней

    Args:
        days_off (List[int]): Список выходных дней недели (1-7)
        start_date (str): Предполагаемая дата начала в формате YYYY-MM-DD
        duration (int): Требуемая длительность в рабочих днях

    Returns:
        Tuple[str, str]: (start_date, end_date) - Найденные даты начала и окончания
    """
    current_date = datetime.datetime.strptime(start_date, '%Y-%m-%d')

    # Преобразуем дни недели из 1-7 в 0-6 (формат Python)
    python_days_off = [(day - 1) % 7 for day in days_off]

    # Проверяем, подходит ли начальная дата (не выходной)
    if current_date.weekday() in python_days_off:
        # Начальная дата - выходной, ищем следующий рабочий день
        while current_date.weekday() in python_days_off:
            current_date += datetime.timedelta(days=1)

    # Начинаем с найденной даты и считаем рабочие дни
    start_date = current_date
    working_days = 0

    while working_days < duration:
        if current_date.weekday() not in python_days_off:
            working_days += 1

        if working_days < duration:
            current_date += datetime.timedelta(days=1)

    return start_date.strftime('%Y-%m-%d'), current_date.strftime('%Y-%m-%d')