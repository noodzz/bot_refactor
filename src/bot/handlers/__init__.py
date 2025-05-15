from aiogram import Router, Dispatcher, Bot
from typing import Dict, Any


def register_all_handlers(
        dp: Dispatcher,
        bot: Bot,
        project_service,
        task_service,
        employee_service,
        schedule_service,
        export_service,
        config: Dict[str, Any]
):
    """Регистрирует все обработчики сообщений и запросов"""
    # Импорт всех обработчиков
    from .admin import register_admin_handlers
    from .project import register_project_handlers
    from .schedule import register_schedule_handlers
    from .employee import register_employee_handlers
    from .export import register_export_handlers

    # Регистрация обработчиков
    register_admin_handlers(dp, bot, config)
    register_project_handlers(dp, bot, project_service, task_service)
    register_schedule_handlers(dp, bot, schedule_service, project_service, task_service)
    register_employee_handlers(dp, bot, employee_service, project_service, task_service)
    register_export_handlers(dp, bot, export_service, project_service, task_service, employee_service)