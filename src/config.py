import os
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv


def load_config() -> Dict[str, Any]:
    """
    Загружает конфигурацию приложения из переменных окружения

    Returns:
        dict: Словарь с настройками
    """
    # Загружаем .env файл, если он существует
    load_dotenv()

    # Получаем абсолютный путь к папке проекта
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Путь к файлу базы данных (с абсолютным путем)
    db_name = os.getenv('DB_NAME', 'project_bot.db')
    # Полный путь к базе данных в корневой директории
    db_path = os.path.join(base_dir, db_name)

    print(f"База данных будет использоваться по пути: {db_path}")

    return {
        'BOT_TOKEN': os.getenv('BOT_TOKEN'),
        'DB_NAME': os.getenv('DB_NAME', 'project_bot.db'),
        'JIRA_URL': os.getenv('JIRA_URL', ''),
        'JIRA_USERNAME': os.getenv('JIRA_USERNAME', ''),
        'JIRA_API_TOKEN': os.getenv('JIRA_API_TOKEN', ''),
        'JIRA_PROJECT': os.getenv('JIRA_PROJECT', 'TEC'),
        'LOG_LEVEL': os.getenv('LOG_LEVEL', 'INFO'),
        'ALLOWED_USER_IDS': parse_user_ids(os.getenv('ALLOWED_USER_IDS', '')),
    }


def parse_user_ids(user_ids_str: str) -> List[int]:
    """
    Парсит список разрешенных ID пользователей из строки

    Args:
        user_ids_str: Строка с ID пользователей, разделенными запятыми

    Returns:
        List[int]: Список ID пользователей
    """
    if not user_ids_str:
        return []

    try:
        return [int(user_id.strip()) for user_id in user_ids_str.split(',') if user_id.strip()]
    except ValueError:
        # В случае ошибки возвращаем пустой список
        return []


# Пример резервных ID, если не удалось загрузить из конфигурации
DEFAULT_ALLOWED_USER_IDS = [6633100206]