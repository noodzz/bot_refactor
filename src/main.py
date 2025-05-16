import asyncio
import logging
import os
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from src.config import load_config
from src.data.templates.default_employees import DEFAULT_EMPLOYEES
from src.utils.auth_utils import setup_auth_functions
from src.utils.context import init_services
from src.utils.logging import setup_logging
from src.data.database.manager import DatabaseManager
from src.core.services.project_service import ProjectService
from src.core.services.task_service import TaskService
from src.core.services.employee_service import EmployeeService
from src.core.services.schedule_service import ScheduleService
from src.core.services.export_service import ExportService
from src.data.database.project_repo import ProjectRepository
from src.data.database.task_repo import TaskRepository
from src.data.database.employee_repo import EmployeeRepository
from src.data.templates.default_templates import DEFAULT_TEMPLATES
from src.core.reports.gantt_chart import GanttChart
from src.core.reports.workload_chart import WorkloadChart
from src.bot.handlers import register_all_handlers
from src.bot.middlewares.auth import AuthMiddleware

# Настройка логирования
logger = logging.getLogger(__name__)


async def main():
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    print(f"Текущая директория установлена на: {os.getcwd()}")
    # Загружаем переменные окружения
    load_dotenv()

    # Загружаем конфигурацию
    config = load_config()

    # Настраиваем логирование
    setup_logging(level=getattr(logging, config.get('LOG_LEVEL', 'INFO')))

    # Выводим базовую информацию
    logger.info("Запуск системы календарного планирования для онлайн-школ")
    logger.info(f"База данных: {config['DB_NAME']}")
    # В начале функции main()
    logger.info(f"Текущая директория: {os.getcwd()}")
    logger.info(f"Полный путь к файлу БД: {config['DB_NAME']}")

    # Инициализируем менеджер базы данных
    db_manager = DatabaseManager(config['DB_NAME'])
    db_manager.init_db()

    # Проверяем пользователей в БД
    users = db_manager.execute("SELECT * FROM users")
    if not users:
        # Добавляем администратора по умолчанию
        default_admin_id = config.get('ALLOWED_USER_IDS', [None])[0]
        if default_admin_id:
            db_manager.execute(
                "INSERT INTO users (id, name, is_admin, is_active) VALUES (?, ?, ?, ?)",
                (default_admin_id, "Default Admin", 1, 1)
            )
            logger.info(f"Добавлен администратор по умолчанию с ID {default_admin_id}")
    else:
        logger.info(f"Пользователи в БД: {len(users)}")

    # Проверка базы данных
    def check_database():
        """Проверяет структуру и содержимое базы данных"""
        try:
            # Проверяем таблицы
            tables = db_manager.execute("SELECT name FROM sqlite_master WHERE type='table'")
            table_names = [table[0] for table in tables]
            logger.info(f"Таблицы в БД: {table_names}")

            # Проверяем пользователей
            users = db_manager.execute("SELECT id, name, is_admin FROM users")
            logger.info(f"Пользователи в БД: {[(user['id'], user['name'], user['is_admin']) for user in users]}")

            # Проверяем проекты (если есть)
            projects = db_manager.execute("SELECT id, name, start_date FROM projects")
            logger.info(
                f"Проекты в БД: {[(project['id'], project['name'], project['start_date']) for project in projects]}")
        except Exception as e:
            logger.error(f"Ошибка при проверке БД: {e}")

    # Вызов функции проверки
    check_database()

    # Функция для выгрузки содержимого БД в файл
    def dump_database():
        """Выгружает содержимое БД в текстовый файл для проверки"""
        try:
            dump_file = "db_dump.txt"
            with open(dump_file, "w", encoding="utf-8") as f:
                # Получаем список всех таблиц
                tables = db_manager.execute("SELECT name FROM sqlite_master WHERE type='table'")

                for table in tables:
                    table_name = table[0]
                    f.write(f"=== Таблица: {table_name} ===\n")

                    # Получаем структуру таблицы
                    structure = db_manager.execute(f"PRAGMA table_info({table_name})")
                    f.write("Структура:\n")
                    for col in structure:
                        f.write(f"  {col['name']} {col['type']}\n")

                    # Получаем данные таблицы
                    data = db_manager.execute(f"SELECT * FROM {table_name}")
                    f.write(f"Данные ({len(data)} строк):\n")
                    for row in data:
                        f.write(f"  {dict(row)}\n")

                    f.write("\n")

            logger.info(f"База данных выгружена в файл {dump_file}")
        except Exception as e:
            logger.error(f"Ошибка при выгрузке БД: {e}")

    # Вызываем функцию после инициализации БД
    dump_database()
    # Инициализируем репозитории
    project_repo = ProjectRepository(db_manager)
    task_repo = TaskRepository(db_manager)
    employee_repo = EmployeeRepository(db_manager)

    # Инициализируем сервисы
    project_service = ProjectService(project_repo, task_repo, DEFAULT_TEMPLATES)
    task_service = TaskService(task_repo)
    employee_service = EmployeeService(employee_repo, task_repo, DEFAULT_EMPLOYEES)
    schedule_service = ScheduleService(task_service, employee_service)
    export_service = ExportService(
        config.get('JIRA_URL', ''),
        config.get('JIRA_USERNAME', ''),
        config.get('JIRA_API_TOKEN', ''),
        config.get('JIRA_PROJECT', '')
    )

    # Инициализируем генераторы отчетов
    gantt_chart = GanttChart()
    workload_chart = WorkloadChart()

    # Инициализируем бота
    bot = Bot(token=config['BOT_TOKEN'])
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Инициализируем и добавляем мидлвар
    auth_middleware = AuthMiddleware(config)
    dp.update.outer_middleware(auth_middleware)
    setup_auth_functions(auth_middleware)

    # Добавляем зависимости в контекст бота
    dp["db_manager"] = db_manager
    dp["project_service"] = project_service
    dp["task_service"] = task_service
    dp["employee_service"] = employee_service
    dp["schedule_service"] = schedule_service
    dp["export_service"] = export_service
    dp["gantt_chart"] = gantt_chart
    dp["workload_chart"] = workload_chart
    dp["is_authorized"] = auth_middleware.is_authorized
    dp["is_admin"] = auth_middleware.is_admin

    # Инициализируем глобальные утилиты
    init_services(dp)

    # Регистрируем обработчики
    register_all_handlers(
        dp,
        bot,
        project_service,
        task_service,
        employee_service,
        schedule_service,
        export_service,
        gantt_chart,
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