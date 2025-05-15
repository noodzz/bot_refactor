from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from typing import List, Dict, Any, Optional


def create_project_kb() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для выбора способа создания проекта

    Returns:
        InlineKeyboardMarkup: Клавиатура с кнопками выбора
    """
    buttons = [
        [InlineKeyboardButton(text="📋 Использовать шаблон", callback_data="use_template")],
        [InlineKeyboardButton(text="📎 Загрузить из CSV", callback_data="upload_csv")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def create_templates_kb(templates: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для выбора шаблона проекта

    Args:
        templates: Список доступных шаблонов

    Returns:
        InlineKeyboardMarkup: Клавиатура с кнопками шаблонов
    """
    buttons = []
    for template in templates:
        buttons.append([InlineKeyboardButton(text=template['name'], callback_data=f"template_{template['id']}")])

    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_project_creation")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def create_projects_list_kb(projects: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру со списком проектов

    Args:
        projects: Список проектов

    Returns:
        InlineKeyboardMarkup: Клавиатура с кнопками проектов
    """
    buttons = []
    for project in projects:
        start_date = project['start_date'][:10] if 'start_date' in project else "Нет даты"
        buttons.append([InlineKeyboardButton(
            text=f"{project['name']} (начало: {start_date})",
            callback_data=f"view_project_{project['id']}"
        )])

    # Добавляем кнопку для создания нового проекта
    buttons.append([InlineKeyboardButton(text="➕ Создать новый проект", callback_data="create_new_project")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def create_project_actions_kb(project_id: int) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру действий для проекта

    Args:
        project_id: ID проекта

    Returns:
        InlineKeyboardMarkup: Клавиатура с действиями
    """
    buttons = [
        [InlineKeyboardButton(text="📊 Рассчитать календарный план", callback_data=f"calculate_{project_id}")],
        [InlineKeyboardButton(text="👥 Распределение по сотрудникам", callback_data=f"workload_{project_id}")],
        [InlineKeyboardButton(text="🔄 Экспорт в Jira", callback_data=f"export_jira_{project_id}")],
        [InlineKeyboardButton(text="⬅️ Назад к списку проектов", callback_data="back_to_projects")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def create_employees_list_kb(employees: List[Dict[str, Any]], task_id: int) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру со списком сотрудников для назначения на задачу

    Args:
        employees: Список сотрудников
        task_id: ID задачи

    Returns:
        InlineKeyboardMarkup: Клавиатура с кнопками сотрудников
    """
    buttons = []
    for employee in employees:
        buttons.append([InlineKeyboardButton(
            text=f"{employee['name']} ({employee['position']})",
            callback_data=f"set_employee_{task_id}_{employee['id']}"
        )])

    # Добавляем кнопку отмены
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data=f"cancel_assign_{task_id}")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def create_admin_kb() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру административного меню

    Returns:
        InlineKeyboardMarkup: Клавиатура с админ-функциями
    """
    buttons = [
        [InlineKeyboardButton(text="👥 Управление пользователями", callback_data="admin_users")],
        [InlineKeyboardButton(text="📊 Статистика бота", callback_data="admin_stats")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def create_user_management_kb(users: List[Dict[str, Any]], current_admin_id: int) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для управления пользователями

    Args:
        users: Список пользователей
        current_admin_id: ID текущего администратора

    Returns:
        InlineKeyboardMarkup: Клавиатура с действиями над пользователями
    """
    buttons = []

    for user in users:
        # Не показываем кнопки управления для текущего админа
        if user['id'] != current_admin_id:
            action = "block" if user['is_active'] else "unblock"
            label = "🔒 Заблокировать" if user['is_active'] else "🔓 Разблокировать"
            buttons.append([InlineKeyboardButton(
                text=f"{label} {user['name']} (ID: {user['id']})",
                callback_data=f"user_{action}_{user['id']}"
            )])

    # Добавляем кнопки добавления и возврата
    buttons.append([InlineKeyboardButton(text="➕ Добавить пользователя", callback_data="add_user")])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def create_back_button(callback_data: str, text: str = "⬅️ Назад") -> InlineKeyboardMarkup:
    """
    Создает клавиатуру с кнопкой "Назад"

    Args:
        callback_data: callback_data для кнопки
        text: Текст кнопки

    Returns:
        InlineKeyboardMarkup: Клавиатура с кнопкой "Назад"
    """
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=text, callback_data=callback_data)]])


def create_yes_no_kb(yes_data: str, no_data: str) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру с кнопками "Да" и "Нет"

    Args:
        yes_data: callback_data для кнопки "Да"
        no_data: callback_data для кнопки "Нет"

    Returns:
        InlineKeyboardMarkup: Клавиатура с кнопками "Да" и "Нет"
    """
    buttons = [
        [
            InlineKeyboardButton(text="✅ Да", callback_data=yes_data),
            InlineKeyboardButton(text="❌ Нет", callback_data=no_data)
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)