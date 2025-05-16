import os
import tempfile
import logging
from aiogram import Dispatcher, Bot, Router, types, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile

from src.utils.auth_utils import is_authorized
from src.utils.context import get_service
from src.utils.date_utils import validate_date_format, format_date
from src.data.csv.parser import parse_csv
from src.bot.states.forms import ProjectState
from src.bot.keyboards import (
    create_project_kb, create_templates_kb, create_projects_list_kb,
    create_project_actions_kb, create_back_button
)

logger = logging.getLogger(__name__)


def register_project_handlers(dp: Dispatcher, bot: Bot, project_service, task_service):
    """Регистрирует обработчики команд для работы с проектами"""

    @dp.message(Command("ping"))
    async def cmd_ping(message: types.Message):
        """Simple ping command that bypasses auth"""
        print(f"PING received from {message.from_user.id}")
        await message.answer("PONG!")

    @dp.message(CommandStart())
    async def cmd_start(message: types.Message):
        # Direct logging regardless of authorization
        print(f"START COMMAND RECEIVED from user {message.from_user.id}")
        logger.info(f"START COMMAND RECEIVED from user {message.from_user.id}")

        try:
            if not is_authorized(message.from_user.id):
                user_id = message.from_user.id
                await message.answer(
                    f"Извините, у вас нет доступа к этому боту.\n"
                    f"Ваш ID: {user_id}\n"
                    f"Обратитесь к администратору для получения доступа."
                )
                return

            welcome_text = (
                "👋 Добро пожаловать в бот для управления проектами!\n\n"
                # Rest of welcome message...
            )
            await message.answer(welcome_text)
        except Exception as e:
            error_msg = f"Error in start handler: {str(e)}"
            print(error_msg)
            logger.error(error_msg)
            # Try to respond even if there's an error
            await message.answer(f"Error processing your command: {str(e)}")

    @dp.message(Command("help"))
    async def cmd_help(message: types.Message):
        help_text = (
            "Доступные команды:\n"
            "/create_project - Создать новый проект из шаблона или CSV\n"
            "/list_projects - Список всех проектов\n"
            "/help - Показать эту справку\n\n"
            "/cancel - Отменить текущую операцию\n\n"
            "Рабочий процесс:\n"
            "1. Создайте проект с помощью шаблона или CSV-файла\n"
            "2. Рассчитайте календарный план\n"
            "3. Просмотрите распределение задач по сотрудникам\n"
            "4. При необходимости экспортируйте проект в Jira"
        )
        await message.answer(help_text)

    @dp.message(Command("cancel"))
    async def cmd_cancel(message: types.Message, state: FSMContext):
        """Отменяет текущую операцию и очищает состояние"""
        # Проверяем, есть ли активное состояние
        current_state = await state.get_state()

        if current_state is None:
            # Если нет активного состояния
            await message.answer("Нет активной операции для отмены.")
            return

        # Если есть состояние, очищаем его и сообщаем пользователю
        await state.clear()

        # Выводим разное сообщение в зависимости от того, какое состояние было активно
        if current_state.startswith('ProjectState:'):
            await message.answer("✅ Создание проекта отменено. Что бы вы хотели сделать дальше?")
        elif current_state.startswith('TaskState:'):
            await message.answer("✅ Добавление задачи отменено.")
        elif current_state.startswith('AdminState:'):
            await message.answer("✅ Административная операция отменена.")
        else:
            await message.answer("✅ Операция отменена.")

        # Предлагаем основные команды
        help_text = (
            "Доступные команды:\n"
            "/create_project - Создать новый проект\n"
            "/list_projects - Список всех проектов\n"
            "/help - Показать справку"
        )
        await message.answer(help_text)

    @dp.message(Command("create_project"))
    async def cmd_create_project(message: types.Message, state: FSMContext):
        await message.answer("Введите название проекта:")
        await state.set_state(ProjectState.waiting_for_name)

    @dp.message(ProjectState.waiting_for_name)
    async def process_project_name(message: types.Message, state: FSMContext):
        await state.update_data(project_name=message.text)
        await message.answer("Введите дату начала проекта (формат YYYY-MM-DD):")
        await state.set_state(ProjectState.waiting_for_start_date)

    @dp.message(ProjectState.waiting_for_start_date)
    async def process_start_date(message: types.Message, state: FSMContext):
        start_date = message.text.strip()

        # Проверяем корректность формата даты
        if not validate_date_format(start_date):
            await message.answer(
                "❌ Некорректный формат даты. Пожалуйста, введите дату в формате YYYY-MM-DD (например, 2025-05-14)."
            )
            return

        # Если дата корректна, сохраняем её и предлагаем выбор типа проекта
        await state.update_data(start_date=start_date)

        markup = create_project_kb()
        await message.answer("Как вы хотите создать проект?", reply_markup=markup)
        await state.set_state(ProjectState.waiting_for_choice)

    @dp.callback_query(F.data == "use_template", ProjectState.waiting_for_choice)
    async def process_template_choice(callback: types.CallbackQuery, state: FSMContext):
        templates = project_service.get_templates()

        markup = create_templates_kb(templates)
        await callback.message.edit_text("Выберите шаблон:")
        await callback.message.answer("Доступные шаблоны:", reply_markup=markup)
        await state.set_state(ProjectState.waiting_for_template)

    @dp.callback_query(ProjectState.waiting_for_template)
    async def process_template_selection(callback: types.CallbackQuery, state: FSMContext):
        template_id = int(callback.data.split('_')[1])
        user_data = await state.get_data()

        try:
            user_id = callback.from_user.id
            logger.info(f"Создание проекта из шаблона. Пользователь ID: {user_id}")

            project_id = project_service.create_from_template(
                user_data['project_name'],
                user_data['start_date'],
                template_id,
                user_id=user_id
            )

            # Создаем кнопку для перехода к проекту
            buttons = [
                [InlineKeyboardButton(text="📂 Открыть проект", callback_data=f"view_project_{project_id}")],
                [InlineKeyboardButton(text="📋 Список всех проектов", callback_data="back_to_projects")]
            ]
            markup = InlineKeyboardMarkup(inline_keyboard=buttons)

            await callback.message.edit_text(
                f"✅ Проект '{user_data['project_name']}' успешно создан из шаблона!\n\n"
                f"ID проекта: {project_id}\n\n"
                f"Все задачи из шаблона добавлены в проект. Теперь вы можете просмотреть и отредактировать задачи, "
                f"или рассчитать календарный план.",
                reply_markup=markup
            )
        except Exception as e:
            await callback.message.edit_text(f"Ошибка при создании проекта: {str(e)}")

        await state.clear()

    @dp.callback_query(F.data == "upload_csv", ProjectState.waiting_for_choice)
    async def process_csv_choice(callback: types.CallbackQuery, state: FSMContext):
        await callback.message.edit_text(
            "Пожалуйста, загрузите CSV-файл с данными проекта.\n"
            "Файл должен содержать следующие столбцы:\n"
            "- Задача - Название задачи\n"
            "- Длительность - Длительность задачи в днях\n"
            "- Тип - Тип задачи (обычная или групповая)\n"
            "- Должность - Требуемая должность для выполнения задачи\n"
            "- Предшественники - Список предшествующих задач через запятую\n"
            "- Родительская задача - Для подзадач указывается название родительской задачи\n"
            "- Параллельная - Для подзадач указывается, могут ли они выполняться параллельно (да/нет)\n"
            "\n"
            "Шаблон для задачи можете найти по ссылке: https://docs.google.com/spreadsheets/d/1n-He466tyHoeZVLSUfI8A4YuXfCdf9W7yLyrT8v2ZI8/edit?gid=0#gid=0"
        )
        await state.set_state(ProjectState.waiting_for_csv)

    @dp.message(ProjectState.waiting_for_csv)
    async def process_csv_file(message: types.Message, state: FSMContext):
        if not message.document:
            await message.answer("Пожалуйста, отправьте CSV-файл.")
            return

        try:
            file = await bot.get_file(message.document.file_id)
            file_path = file.file_path
            downloaded_file = await bot.download_file(file_path)

            user_data = await state.get_data()
            csv_content = downloaded_file.read().decode('utf-8')
            project_data = parse_csv(csv_content)

            user_id = message.from_user.id
            logger.info(f"Создание проекта из CSV. Пользователь ID: {user_id}")

            project_id = project_service.create_from_csv(
                user_data['project_name'],
                user_data['start_date'],
                project_data,
                user_id=user_id
            )

            # Создаем кнопку для перехода к проекту
            buttons = [
                [InlineKeyboardButton(text="📂 Открыть проект", callback_data=f"view_project_{project_id}")],
                [InlineKeyboardButton(text="📋 Список всех проектов", callback_data="back_to_projects")]
            ]
            markup = InlineKeyboardMarkup(inline_keyboard=buttons)

            await message.answer(
                f"✅ Проект '{user_data['project_name']}' успешно создан из CSV!\n\n"
                f"ID проекта: {project_id}\n\n"
                f"Загружено {len(project_data)} задач. Теперь вы можете просмотреть проект и рассчитать календарный план.",
                reply_markup=markup
            )
        except Exception as e:
            await message.answer(f"Ошибка при обработке CSV: {str(e)}")

        await state.clear()

    @dp.message(Command("list_projects"))
    async def cmd_list_projects(message: types.Message):
        if not is_authorized(message.from_user.id):
            return

        projects = project_service.get_all_projects(user_id=message.from_user.id)

        if not projects:
            await message.answer("Проектов пока нет. Создайте новый с помощью команды /create_project")
            return

        markup = create_projects_list_kb(projects)
        await message.answer("Выберите проект для просмотра:", reply_markup=markup)

    @dp.callback_query(lambda c: c.data.startswith("view_project_"))
    async def view_project_callback(callback: types.CallbackQuery, project_service=None, task_service=None):
        try:
            project_id = int(callback.data.split("_")[2])
        except (ValueError, IndexError):
            await callback.message.edit_text("Ошибка: некорректный идентификатор проекта")
            return

        try:
            # Используем переданные сервисы через внедрение зависимостей
            # Если у вас недоступен какой-то сервис, используйте get_service
            _project_service = project_service or get_service("project_service")
            _task_service = task_service or get_service("task_service")
            # Получаем данные о проекте
            project = project_service.get_project_details(project_id)
            tasks = task_service.get_tasks_by_project(project_id)

            text = f"Проект: {project.name}\n"
            text += f"Дата начала: {format_date(project.start_date)}\n"
            text += f"Статус: {project.status}\n\n"

            if tasks:
                text += "Задачи:\n"
                for task in tasks:
                    text += f"• {task.name} "
                    text += f"({task.duration} дн.) "

                    if task.is_group:
                        text += "[Групповая задача]\n"
                        subtasks = task_service.get_subtasks(task.id)
                        for subtask in subtasks:
                            employee = None
                            if subtask.employee_id:
                                try:
                                    employee_service = callback.bot.dispatcher.get("employee_service")
                                    employee = employee_service.get_employee(subtask.employee_id)
                                except ValueError:
                                    pass

                            employee_name = f"{employee.name} ({employee.position})" if employee else "Не назначен"
                            text += f"  ↳ {subtask.name} - {employee_name}\n"
                    else:
                        employee = None
                        if task.employee_id:
                            try:
                                employee_service = callback.bot.dispatcher.get("employee_service")
                                employee = employee_service.get_employee(task.employee_id)
                            except ValueError:
                                pass

                        text += f"- {employee.name} ({employee.position})" if employee else "- Не назначен\n"
            else:
                text += "Задач в проекте нет"

            # Проверяем длину текста и отправляем соответствующим образом
            if len(text) > 3500:  # Лимит Telegram с запасом
                # Создаем временный файл
                temp_dir = tempfile.mkdtemp()
                safe_project_name = "".join(
                    c if c.isalnum() or c in [' ', '.', '_', '-'] else '_' for c in project.name
                )
                file_path = os.path.join(temp_dir, f"{safe_project_name}_details.txt")

                # Записываем текст в файл
                with open(file_path, 'w', encoding='utf-8') as file:
                    file.write(text)

                # Отправляем краткую информацию
                await callback.message.edit_text(
                    f"Проект: {project.name}\n"
                    f"Дата начала: {format_date(project.start_date)}\n"
                    f"Статус: {project.status}\n\n"
                    f"Проект содержит много задач, полные детали в файле:"
                )

                # Отправляем файл с отчетом
                file = FSInputFile(file_path)
                await bot.send_document(
                    callback.from_user.id,
                    file,
                    caption=f"Детали проекта '{project.name}'"
                )

                # Отправляем кнопки для дальнейших действий
                markup = create_project_actions_kb(project_id)
                await callback.message.answer("Выберите действие:", reply_markup=markup)

                # Очистка временных файлов
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    os.rmdir(temp_dir)
                except Exception as e:
                    logger.error(f"Ошибка при очистке временных файлов: {str(e)}")
            else:
                # Если текст не слишком длинный, отправляем обычным сообщением
                markup = create_project_actions_kb(project_id)
                await callback.message.edit_text(text, reply_markup=markup)

        except Exception as e:
            await callback.message.edit_text(f"Ошибка при получении данных проекта: {str(e)}")

    @dp.callback_query(F.data == "back_to_projects")
    async def back_to_projects(callback: types.CallbackQuery):
        projects = project_service.get_all_projects()
        markup = create_projects_list_kb(projects)
        await callback.message.edit_text("Выберите проект для просмотра:", reply_markup=markup)