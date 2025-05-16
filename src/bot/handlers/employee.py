import os
import tempfile
import logging
from aiogram import Dispatcher, Bot, Router, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile

from src.bot.keyboards import create_back_button
from src.utils.date_utils import format_date

logger = logging.getLogger(__name__)


def register_employee_handlers(dp: Dispatcher, bot: Bot, employee_service, project_service, task_service):
    """Регистрирует обработчики для работы с сотрудниками и распределения задач"""

    @dp.message(Command("employee_workload"))
    async def cmd_employee_workload(message: types.Message):
        """Показывает распределение задач по сотрудникам"""
        projects = project_service.get_all_projects()

        if not projects:
            await message.answer("Проектов пока нет. Создайте новый с помощью команды /create_project")
            return

        buttons = []
        for project in projects:
            buttons.append([InlineKeyboardButton(
                text=f"{project.name} (начало: {format_date(project.start_date)})",
                callback_data=f"workload_{project.id}"
            )])

        markup = InlineKeyboardMarkup(inline_keyboard=buttons)
        await message.answer("Выберите проект для просмотра распределения задач по сотрудникам:", reply_markup=markup)

    @dp.callback_query(lambda c: c.data.startswith("workload_"))
    async def show_employee_workload(callback: types.CallbackQuery, project_service=None, employee_service=None,
                                     task_service=None):
        """Показывает распределение задач по сотрудникам для выбранного проекта"""
        try:
            project_id = int(callback.data.split("_")[1])
        except (ValueError, IndexError):
            await callback.message.edit_text("Ошибка: некорректный идентификатор проекта")
            return

        # Получаем данные о проекте
        project = project_service.get_project_details(project_id)

        await show_workload_report(callback, project_id, employee_service, project, task_service)

    async def show_workload_report(callback, project_id, employee_service, project, task_service):
        """
        Отображает отчет о распределении задач с учетом ограничений Telegram

        Args:
            callback: Callback от Telegram
            project_id: ID проекта
            employee_service: Менеджер сотрудников
            project: Информация о проекте
            task_service: Менеджер задач
        """
        try:
            # Генерируем отчет о распределении задач
            report = employee_service.generate_workload_report(project_id)

            # Проверяем длину отчета
            if len(report) <= 4000:  # Оставляем запас до лимита в 4096 символов
                # Если отчет короткий, отправляем его напрямую
                markup = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Назад к проекту", callback_data=f"view_project_{project_id}")]
                ])
                await callback.message.edit_text(report, reply_markup=markup)
            else:
                # Если отчет слишком длинный, сохраняем его в файл и отправляем как документ
                temp_dir = tempfile.mkdtemp()

                # Создаем безопасное имя файла
                safe_project_name = "".join(
                    c if c.isalnum() or c in [' ', '.', '_', '-'] else '_' for c in project.name
                )
                file_path = os.path.join(temp_dir, f"{safe_project_name}_workload_report.txt")

                # Записываем отчет в файл
                with open(file_path, 'w', encoding='utf-8') as file:
                    file.write(report)

                # Отправляем краткое сообщение
                await callback.message.edit_text(
                    f"Отчет о распределении задач для проекта '{project.name}' прикреплен ниже. "
                    f"В проекте задействовано {len(employee_service.get_employee_workload(project_id))} сотрудников."
                )

                # Отправляем файл с отчетом
                file = FSInputFile(file_path)
                await callback.message.answer_document(
                    file,
                    caption=f"Отчет о распределении задач для проекта '{project.name}'"
                )

                # Отправляем кнопки для дальнейших действий
                markup = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Назад к проекту", callback_data=f"view_project_{project_id}")]
                ])
                await callback.message.answer("Выберите дальнейшее действие:", reply_markup=markup)

                # Очистка временных файлов
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    os.rmdir(temp_dir)
                except Exception as e:
                    logger.error(f"Ошибка при очистке временных файлов: {str(e)}")

            # Генерируем и отправляем диаграмму загрузки сотрудников
            workload_data = employee_service.get_employee_workload(project_id)
            workload_chart = callback.bot.get('workload_chart')

            if workload_chart and workload_data:
                workload_image = workload_chart.generate(project.to_dict(), workload_data)
                if os.path.exists(workload_image):
                    workload_file = FSInputFile(workload_image)
                    await callback.message.answer_photo(
                        workload_file,
                        caption=f"Диаграмма загрузки сотрудников для проекта '{project.name}'"
                    )

        except Exception as e:
            import traceback
            error_msg = f"Ошибка при получении распределения задач: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_msg)

            # Отправляем укороченное сообщение об ошибке
            short_error = f"Ошибка при получении распределения задач: {str(e)}"
            await callback.message.edit_text(
                short_error,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Назад к проекту", callback_data=f"view_project_{project_id}")]
                ])
            )

    @dp.callback_query(lambda c: c.data.startswith("assign_to_project_"))
    async def assign_to_project(callback: types.CallbackQuery):
        """Показывает список задач проекта для назначения сотрудников"""
        try:
            parts = callback.data.split("_")
            if len(parts) < 3:
                await callback.message.edit_text(
                    "Ошибка: неверный формат данных. Пожалуйста, вернитесь в список проектов.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="Вернуться к списку проектов", callback_data="back_to_projects")]
                    ])
                )
                return

            project_id = int(parts[2])
        except ValueError:
            await callback.message.edit_text(
                "Ошибка: некорректный идентификатор проекта. Пожалуйста, вернитесь в список проектов.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Вернуться к списку проектов", callback_data="back_to_projects")]
                ])
            )
            return

        try:
            # Получаем данные о проекте
            project = project_service.get_project_details(project_id)

            # Получаем список задач, на которые можно назначить сотрудников
            tasks = task_service.get_tasks_by_project(project_id)
            assignable_tasks = [task for task in tasks if not task.is_group and not task.parent_id]

            if not assignable_tasks:
                await callback.message.edit_text(
                    f"В проекте '{project.name}' нет задач, на которые можно назначить сотрудников.\n"
                    f"Сначала добавьте задачи с помощью команды /add_task.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="Назад к проекту", callback_data=f"view_project_{project_id}")]
                    ])
                )
                return

            # Создаем кнопки для задач
            buttons = []
            for task in assignable_tasks:
                # Определяем текущий статус назначения
                status = ""
                if task.employee_id:
                    employee = employee_service.get_employee(task.employee_id)
                    status = f" - {employee.name}"

                buttons.append([InlineKeyboardButton(
                    text=f"{task.name}{status}",
                    callback_data=f"assign_task_{task.id}"
                )])

            # Добавляем кнопку возврата
            buttons.append([InlineKeyboardButton(
                text="Назад к распределению",
                callback_data=f"workload_{project_id}"
            )])

            markup = InlineKeyboardMarkup(inline_keyboard=buttons)
            await callback.message.edit_text(
                f"Выберите задачу для назначения сотрудника в проекте '{project.name}':",
                reply_markup=markup
            )

        except Exception as e:
            await callback.message.edit_text(f"Ошибка при загрузке задач: {str(e)}")

    @dp.callback_query(lambda c: c.data.startswith("assign_task_"))
    async def assign_employee_to_task(callback: types.CallbackQuery):
        """Показывает список сотрудников для назначения на задачу"""
        task_id = int(callback.data.split("_")[2])

        try:
            # Получаем информацию о задаче
            task = task_service.get_task(task_id)

            # Если позиция не указана, сообщаем об ошибке
            if not task.position:
                await callback.message.edit_text(
                    f"Для задачи '{task.name}' не указана требуемая должность сотрудника.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="Назад", callback_data=f"assign_to_project_{task.project_id}")]
                    ])
                )
                return

            # Получаем список сотрудников с подходящей должностью
            employees = employee_service.get_employees_by_position(task.position)

            if not employees:
                await callback.message.edit_text(
                    f"Нет сотрудников с должностью '{task.position}' для задачи '{task.name}'.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="Назад", callback_data=f"assign_to_project_{task.project_id}")]
                    ])
                )
                return

            # Создаем кнопки для выбора сотрудника
            buttons = []
            for employee in employees:
                buttons.append([InlineKeyboardButton(
                    text=f"{employee.name} ({employee.position})",
                    callback_data=f"set_employee_{task_id}_{employee.id}"
                )])

            # Добавляем кнопку для отмены назначения, если сотрудник уже назначен
            if task.employee_id:
                buttons.append([InlineKeyboardButton(
                    text="❌ Снять назначение",
                    callback_data=f"unassign_employee_{task_id}"
                )])

            # Добавляем кнопку возврата
            buttons.append([InlineKeyboardButton(
                text="Назад к выбору задачи",
                callback_data=f"assign_to_project_{task.project_id}"
            )])

            markup = InlineKeyboardMarkup(inline_keyboard=buttons)
            await callback.message.edit_text(
                f"Выберите сотрудника для задачи '{task.name}':",
                reply_markup=markup
            )

        except Exception as e:
            await callback.message.edit_text(f"Ошибка при получении списка сотрудников: {str(e)}")

    @dp.callback_query(lambda c: c.data.startswith("set_employee_"))
    async def set_employee(callback: types.CallbackQuery):
        """Назначает сотрудника на задачу"""
        try:
            parts = callback.data.split("_")
            if len(parts) < 4:
                await callback.message.edit_text("Ошибка: некорректный формат данных.")
                return

            task_id = int(parts[2])
            employee_id = int(parts[3])

            # Получаем информацию о задаче
            task = task_service.get_task(task_id)

            # Получаем информацию о сотруднике
            employee = employee_service.get_employee(employee_id)

            # Назначаем сотрудника на задачу
            task_service.assign_employee(task_id, employee_id)

            await callback.message.edit_text(
                f"Сотрудник {employee.name} назначен на задачу '{task.name}'.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(
                        text="Вернуться к распределению",
                        callback_data=f"workload_{task.project_id}"
                    )]
                ])
            )

        except Exception as e:
            await callback.message.edit_text(f"Ошибка при назначении сотрудника: {str(e)}")

    @dp.callback_query(lambda c: c.data.startswith("unassign_employee_"))
    async def unassign_employee(callback: types.CallbackQuery):
        """Снимает назначение сотрудника с задачи"""
        try:
            parts = callback.data.split("_")
            if len(parts) < 3:
                await callback.message.edit_text("Ошибка: некорректный формат данных.")
                return

            task_id = int(parts[2])

            # Получаем информацию о задаче
            task = task_service.get_task(task_id)

            # Снимаем назначение
            db_manager = callback.bot.get('db_manager')
            db_manager.execute("UPDATE tasks SET employee_id = NULL WHERE id = ?", (task_id,))

            await callback.message.edit_text(
                f"Назначение на задачу '{task.name}' снято.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(
                        text="Вернуться к распределению",
                        callback_data=f"workload_{task.project_id}"
                    )]
                ])
            )

        except Exception as e:
            await callback.message.edit_text(f"Ошибка при снятии назначения: {str(e)}")