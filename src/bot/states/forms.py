from aiogram.fsm.state import State, StatesGroup


class ProjectState(StatesGroup):
    """Состояния для создания и редактирования проекта"""

    # Создание нового проекта
    waiting_for_name = State()
    waiting_for_start_date = State()
    waiting_for_choice = State()
    waiting_for_csv = State()
    waiting_for_template = State()


class TaskState(StatesGroup):
    """Состояния для создания и редактирования задачи"""

    # Добавление задачи
    waiting_for_name = State()
    waiting_for_duration = State()
    waiting_for_predecessors = State()
    waiting_for_employee_type = State()
    waiting_for_employee = State()


class AdminState(StatesGroup):
    """Состояния для административных команд"""

    # Управление пользователями
    waiting_for_user_id = State()
    waiting_for_admin_status = State()

    # Управление настройками
    waiting_for_setting_value = State()