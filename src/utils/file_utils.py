import os
import tempfile
from typing import Optional, List


def create_safe_filename(filename: str, max_length: int = 100) -> str:
    """
    Создает безопасное имя файла, удаляя или заменяя недопустимые символы

    Args:
        filename (str): Исходное имя файла
        max_length (int): Максимальная длина имени файла

    Returns:
        str: Безопасное имя файла
    """
    # Список недопустимых символов в Windows
    invalid_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']

    # Заменяем недопустимые символы на безопасные
    safe_name = filename
    for char in invalid_chars:
        safe_name = safe_name.replace(char, '_')

    # Ограничиваем длину имени файла
    if len(safe_name) > max_length:
        safe_name = safe_name[:max_length]

    return safe_name


def create_temp_directory() -> str:
    """
    Создает временный каталог для файлов

    Returns:
        str: Путь к временному каталогу
    """
    return tempfile.mkdtemp()


def create_temp_file(directory: str, filename: str, content: str) -> str:
    """
    Создает временный файл с указанным содержимым

    Args:
        directory (str): Каталог для создания файла
        filename (str): Имя файла
        content (str): Содержимое файла

    Returns:
        str: Путь к созданному файлу
    """
    safe_filename = create_safe_filename(filename)
    file_path = os.path.join(directory, safe_filename)

    with open(file_path, 'w', encoding='utf-8') as file:
        file.write(content)

    return file_path


def cleanup_files(files: List[str]) -> None:
    """
    Удаляет временные файлы

    Args:
        files (List[str]): Список путей к файлам
    """
    for file_path in files:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            print(f"Ошибка при удалении файла {file_path}: {str(e)}")