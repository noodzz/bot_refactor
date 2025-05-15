import logging
from aiogram import Dispatcher, Bot, Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile

logger = logging.getLogger(__name__)


def register_export_handlers(dp: Dispatcher, bot: Bot, export_service, project_service, task_service, employee_service):
    """Регистрирует обработчики для экспорта в Jira"""

    @dp.callback_query(lambda c: c.data.startswith("export_jira_"))
    async def export_to_jira(callback: types.CallbackQuery):
        project_id = int(callback.data.split("_")[2])

        await callback.message.edit_text("Выполняется экспорт в Jira...")

        try:
            project = project_service.get_project_details(project_id)
            tasks = task_service.get_all_tasks_by_project(project_id)

            # Пробуем прямую интеграцию с Jira API
            result = export_service.import_to_jira(project.to_dict(), [task.to_dict() for task in tasks],
                                                   employee_service)

            if result['success']:
                # API-интеграция успешна
                message_text = (
                    f"Проект '{project.name}' успешно экспортирован в Jira!\n\n"
                    f"Эпик: {result['epic_key']}\n"
                    f"Создано задач: {len(result['created_issues'])}\n\n"
                    f"Ссылка на проект в Jira: {result['jira_project_url']}"
                )
                await callback.message.edit_text(message_text)
            else:
                # Если API не сработал, отправляем файл
                file = FSInputFile(result['csv_export_file'])
                await bot.send_document(
                    callback.from_user.id,
                    file,
                    caption=f"Файл для импорта в Jira (проект '{project.name}')\n\n{result['message']}"
                )

                await callback.message.edit_text(
                    "Экспорт в Jira через API не удался. Отправлен CSV-файл для ручного импорта."
                )

            buttons = [
                [InlineKeyboardButton(text="Назад к проекту", callback_data=f"view_project_{project_id}")]
            ]

            markup = InlineKeyboardMarkup(inline_keyboard=buttons)
            await callback.message.reply("Экспорт завершен", reply_markup=markup)

        except Exception as e:
            await callback.message.edit_text(f"Ошибка при экспорте в Jira: {str(e)}")