import logging
import datetime
import platform
import os
import psutil
from aiogram import Dispatcher, Bot, Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from src.bot.states.forms import AdminState
from src.utils.file_utils import create_safe_filename
from src.bot.keyboards import create_admin_kb, create_user_management_kb, create_back_button

logger = logging.getLogger(__name__)


def register_admin_handlers(dp: Dispatcher, bot: Bot, config):
    """Регистрирует обработчики для административных команд"""

    @dp.message(Command("admin"))
    async def cmd_admin(message: types.Message):
        """Показывает административное меню"""
        from src.utils.helpers import is_admin

        if not is_admin(message.from_user.id):
            await message.answer("У вас нет прав администратора.")
            return

        markup = create_admin_kb()
        await message.answer("Административное меню:", reply_markup=markup)

    @dp.callback_query(F.data == "admin_users")
    async def admin_users(callback: types.CallbackQuery):
        """Показывает список пользователей"""
        from src.utils.helpers import is_admin

        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав администратора.")
            return

        # Получаем данные из БД
        db_manager = callback.bot.get('db_manager')
        users = db_manager.get_all_users()

        text = "Список пользователей:\n\n"

        # Формируем текст
        for user in users:
            status = "✅ Активен" if user['is_active'] else "❌ Заблокирован"
            role = "🔑 Администратор" if user['is_admin'] else "👤 Пользователь"
            text += f"ID: {user['id']} - {status}, {role}\n"

        # Создаем клавиатуру управления пользователями
        markup = create_user_management_kb(users, callback.from_user.id)
        await callback.message.edit_text(text, reply_markup=markup)

    # Обработчик для блокировки/разблокировки пользователя
    @dp.callback_query(lambda c: c.data.startswith("user_block_") or c.data.startswith("user_unblock_"))
    async def toggle_user_status(callback: types.CallbackQuery):
        from src.utils.helpers import is_admin

        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав администратора.")
            return

        parts = callback.data.split("_")
        action = parts[1]  # "block" или "unblock"
        user_id = int(parts[2])

        # Получаем данные из БД
        db_manager = callback.bot.get('db_manager')

        # Меняем статус пользователя
        is_active = action == "unblock"  # True если разблокировка, False если блокировка
        db_manager.update_user(user_id, is_active=is_active)

        action_text = "разблокирован" if is_active else "заблокирован"
        await callback.answer(f"Пользователь {user_id} {action_text}!")

        # Обновляем список пользователей
        await admin_users(callback)

    @dp.callback_query(F.data == "add_user")
    async def add_user_start(callback: types.CallbackQuery, state: FSMContext):
        from src.utils.helpers import is_admin

        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав администратора.")
            return

        await callback.message.edit_text(
            "Введите Telegram ID пользователя, которого хотите добавить:"
        )
        await state.set_state(AdminState.waiting_for_user_id)

    @dp.message(AdminState.waiting_for_user_id)
    async def process_new_user_id(message: types.Message, state: FSMContext):
        from src.utils.helpers import is_admin

        if not is_admin(message.from_user.id):
            await message.answer("У вас нет прав администратора.")
            await state.clear()
            return

        try:
            user_id = int(message.text.strip())

            # Получаем данные из БД
            db_manager = message.bot.get('db_manager')

            # Проверяем, существует ли уже такой пользователь
            existing_user = db_manager.get_user(user_id)

            if existing_user:
                await message.answer(
                    f"Пользователь с ID {user_id} уже существует.\n\n"
                    f"Статус: {'Активен' if existing_user['is_active'] else 'Заблокирован'}\n"
                    f"Роль: {'Администратор' if existing_user['is_admin'] else 'Пользователь'}"
                )
            else:
                # Добавляем нового пользователя
                db_manager.add_user(user_id, name=f"User_{user_id}", is_admin=0)
                await message.answer(f"Пользователь с ID {user_id} успешно добавлен!")

            # Возвращаемся к списку пользователей
            markup = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Вернуться к списку пользователей", callback_data="admin_users")]
            ])
            await message.answer("Что дальше?", reply_markup=markup)

        except ValueError:
            await message.answer("Ошибка: ID пользователя должен быть числом. Попробуйте еще раз:")

        await state.clear()

    @dp.callback_query(F.data == "admin_stats")
    async def admin_stats(callback: types.CallbackQuery):
        """Показывает статистику использования бота"""
        from src.utils.helpers import is_admin

        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав администратора.")
            return

        try:
            # Получаем данные из БД
            db_manager = callback.bot.get('db_manager')

            # Получаем статистику по проектам
            total_projects = db_manager.execute("SELECT COUNT(*) FROM projects")[0][0]
            active_projects = db_manager.execute("SELECT COUNT(*) FROM projects WHERE status = 'active'")[0][0]

            # Статистика по задачам
            total_tasks = db_manager.execute("SELECT COUNT(*) FROM tasks")[0][0]
            group_tasks = db_manager.execute("SELECT COUNT(*) FROM tasks WHERE is_group = 1")[0][0]
            subtasks = db_manager.execute("SELECT COUNT(*) FROM tasks WHERE parent_id IS NOT NULL")[0][0]

            # Статистика по пользователям
            total_users = db_manager.execute("SELECT COUNT(*) FROM users")[0][0]
            active_users = db_manager.execute("SELECT COUNT(*) FROM users WHERE is_active = 1")[0][0]
            admin_users = db_manager.execute("SELECT COUNT(*) FROM users WHERE is_admin = 1")[0][0]

            # Распределение проектов по пользователям
            projects_by_user = db_manager.execute("""
                SELECT u.id, u.name, COUNT(p.id) as project_count 
                FROM users u 
                LEFT JOIN projects p ON u.id = p.user_id 
                GROUP BY u.id 
                ORDER BY project_count DESC
            """)

            # Последняя активность
            last_project = db_manager.execute(
                "SELECT name, created_at FROM projects ORDER BY created_at DESC LIMIT 1"
            )

            # Формируем отчёт
            stats_text = "📊 **СТАТИСТИКА БОТА**\n\n"

            stats_text += "**Проекты:**\n"
            stats_text += f"• Всего проектов: {total_projects}\n"
            stats_text += f"• Активных проектов: {active_projects}\n"

            stats_text += "\n**Задачи:**\n"
            stats_text += f"• Всего задач: {total_tasks}\n"
            stats_text += f"• Групповых задач: {group_tasks}\n"
            stats_text += f"• Подзадач: {subtasks}\n"

            stats_text += "\n**Пользователи:**\n"
            stats_text += f"• Всего пользователей: {total_users}\n"
            stats_text += f"• Активных пользователей: {active_users}\n"
            stats_text += f"• Администраторов: {admin_users}\n"

            stats_text += "\n**Распределение проектов по пользователям:**\n"
            for user_data in projects_by_user:
                user_id, user_name, count = user_data
                stats_text += f"• {user_name or f'User_{user_id}'}: {count} проект(ов)\n"

            if last_project:
                project_name, created_at = last_project[0]
                stats_text += f"\n**Последний созданный проект:**\n• {project_name} ({created_at})\n"

            # Добавляем техническую информацию
            stats_text += "\n**Системная информация:**\n"
            stats_text += f"• ОС: {platform.system()} {platform.release()}\n"
            stats_text += f"• Python: {platform.python_version()}\n"

            try:
                process = psutil.Process(os.getpid())
                memory_usage = process.memory_info().rss / 1024 / 1024  # в МБ
                stats_text += f"• Использование памяти: {memory_usage:.2f} МБ\n"
                stats_text += f"• Время работы бота: {(datetime.datetime.now() - datetime.datetime.fromtimestamp(process.create_time())).total_seconds() / 3600:.2f} ч\n"
            except:
                stats_text += "• Данные о системных ресурсах недоступны\n"

            # Кнопка для возврата
            markup = create_back_button("admin")

            await callback.message.edit_text(stats_text, reply_markup=markup)

        except Exception as e:
            markup = create_back_button("admin")
            await callback.message.edit_text(
                f"Ошибка при получении статистики: {str(e)}",
                reply_markup=markup
            )

    @dp.callback_query(F.data == "admin")
    async def back_to_admin(callback: types.CallbackQuery):
        """Возвращает к административному меню"""
        from src.utils.helpers import is_admin

        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав администратора.")
            return

        markup = create_admin_kb()
        await callback.message.edit_text("Административное меню:", reply_markup=markup)