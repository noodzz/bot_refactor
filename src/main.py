import asyncio
import logging
import os
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from src.config import load_config
from src.utils.logging import setup_logging
from src.data.database.manager import DatabaseManager
from src.data.templates.default_templates import DEFAULT_TEMPLATES
from src.core.services.project_service import ProjectService
from src.core.services.task_service import TaskService
from src.core.services.employee_service import EmployeeService
from src.core.services.schedule_service import ScheduleService
from src.core.services.export_service import ExportService
from src.data.database.project_repo import ProjectRepository
from src.data.database.task_repo import TaskRepository
from src.data.database.employee_repo import EmployeeRepository
from src.bot.handlers import register_all_handlers

# Настройка логирования
logger = logging.getLogger(__name__)


async def main():
    # Загружаем переменные окружения
    load_dotenv()

    # Загружаем конфигурацию
    config = load_config()

    # Настраиваем логирование
    setup_logging(level=getattr(logging, config.get('LOG_LEVEL', 'INFO')))

    # Выводим базовую информацию
    logger.info("Запуск системы календарного планирования для онлайн-школ")
    logger.info(f"База данных: {config['DB_NAME']}")

    # Инициализируем менеджер базы данных
    db_manager = DatabaseManager(config['DB_NAME'])
    db_manager.init_db()

    # Инициализируем репозитории
    project_repo = ProjectRepository(db_manager)
    task_repo = TaskRepository(db_manager)
    employee_repo = EmployeeRepository(db_manager)

    # Инициализируем сервисы
    project_service = ProjectService(project_repo, task_repo, DEFAULT_TEMPLATES)
    task_service = TaskService(task_repo)
    employee_service = EmployeeService(employee_repo, task_repo)
    schedule_service = ScheduleService(task_service, employee_service)
    export_service = ExportService(
        config['JIRA_URL'],
        config['JIRA_USERNAME'],
        config['JIRA_API_TOKEN'],
        config['JIRA_PROJECT']
    )

    # Инициализируем бота
    bot = Bot(token=config['BOT_TOKEN'])
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Регистрируем обработчики
    register_all_handlers(
        dp,
        bot,
        project_service,
        task_service,
        employee_service,
        schedule_service,
        export_service,
        config
    )

    # Запускаем бота
    logger.info("Бот запущен")

    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
    finally:
        logger.info("Бот остановлен")
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())