import os
import tempfile
import logging
import traceback
import datetime
from aiogram import Dispatcher, Bot, Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from src.bot.keyboards import create_back_button
from src.utils.date_utils import format_date

logger = logging.getLogger(__name__)


def register_schedule_handlers(
        dp: Dispatcher,
        bot: Bot,
        schedule_service,
        project_service,
        task_service,
        employee_service,
        gantt_chart
):
    """Регистрирует обработчики для календарного планирования"""

    @dp.callback_query(lambda c: c.data.startswith("calculate_"))
    async def calculate_schedule(
            callback: types.CallbackQuery,
            schedule_service=schedule_service,
            project_service=project_service,
            task_service=task_service,
            employee_service=employee_service,
            gantt_chart=gantt_chart
    ):
        project_id = int(callback.data.split("_")[1])

        await callback.message.edit_text("Выполняется расчет календарного плана и распределение задач...")

        try:
            # Получаем данные о проекте и задачах
            project = project_service.get_project_details(project_id)
            tasks = task_service.get_tasks_by_project(project_id)

            # Рассчитываем календарный план
            result = schedule_service.calculate_schedule(project.to_dict(), [task.to_dict() for task in tasks])

            # Извлекаем результаты
            task_dates = result['task_dates']
            critical_path = result['critical_path']
            duration = result['duration']

            # Отладочная информация
            logger.info(f"Критический путь: {critical_path}")
            logger.info(f"Длительность проекта: {duration} дней")

            # Генерируем отчет
            text = f"📊 ОТЧЕТ ПО КАЛЕНДАРНОМУ ПЛАНУ\n"
            text += f"=============================================\n\n"
            text += f"📋 ОБЩАЯ ИНФОРМАЦИЯ О ПРОЕКТЕ\n"
            text += f"Название проекта: '{project.name}'\n"

            # Вычисляем фактическую длительность проекта
            if result['task_dates']:
                start_dates = [datetime.datetime.strptime(dates['start'], '%Y-%m-%d') for dates in
                               result['task_dates'].values()]
                end_dates = [datetime.datetime.strptime(dates['end'], '%Y-%m-%d') for dates in
                             result['task_dates'].values()]

                if start_dates and end_dates:
                    project_start = min(start_dates)
                    project_end = max(end_dates)
                    project_duration = (project_end - project_start).days + 1
                    text += f"Длительность проекта: {project_duration} дней\n"
                    text += f"Дата начала: {project_start.strftime('%d.%m.%Y')}\n"
                    text += f"Дата завершения: {project_end.strftime('%d.%m.%Y')}\n\n"
                    text += f"Общее количество задач: {len(tasks)}\n\n"
                else:
                    text += f"Длительность проекта: {result['duration']} дней\n\n"
            else:
                text += f"Длительность проекта: {result['duration']} дней\n\n"

            # Критический путь
            text += f"🚩 КРИТИЧЕСКИЙ ПУТЬ\n"
            text += f"Критический путь — последовательность задач, определяющая длительность проекта.\n"
            text += f"Задержка любой из этих задач приведет к задержке всего проекта.\n\n"

            if result['critical_path']:
                critical_tasks = []
                total_critical_days = 0

                for task_id in result['critical_path']:
                    task = task_service.get_task(task_id)
                    critical_tasks.append(task)
                    total_critical_days += task.duration - 1

                    # Форматируем даты для отображения
                    start_date = "?"
                    end_date = "?"
                    if task_id in result['task_dates']:
                        start_date = format_date(result['task_dates'][task_id]['start'])
                        end_date = format_date(result['task_dates'][task_id]['end'])

                    # Добавляем информацию о задаче
                    text += f"• {task.name} ({task.duration} дн.)\n"
                    text += f"  Даты: {start_date} - {end_date}\n"

                    # Добавляем информацию о сотруднике, если назначен
                    if task.employee_id:
                        try:
                            employee = employee_service.get_employee(task.employee_id)
                            text += f"  Исполнитель: {employee.name} ({employee.position})\n"
                        except:
                            pass
                    text += "\n"
                text += f"Длина критического пути: {total_critical_days} дней\n\n"
            else:
                text += "Критический путь не определен. Возможные причины:\n"
                text += "• Недостаточно связей между задачами\n"
                text += "• Все задачи могут выполняться независимо\n"
                text += "• Задачи с наибольшей длительностью: "

                # Находим самые длинные задачи
                sorted_tasks = sorted(tasks, key=lambda t: t.duration, reverse=True)
                long_tasks = [t.name for t in sorted_tasks[:3] if t.duration > 0]

                if long_tasks:
                    text += ", ".join(long_tasks) + "\n\n"
                else:
                    text += "не найдены\n\n"

            # Добавляем информацию о распределении задач по сотрудникам
            text += f"👥 РАСПРЕДЕЛЕНИЕ ЗАДАЧ\n"

            employee_workload = employee_service.get_employee_workload(project_id)
            if employee_workload:
                # Группируем по сотрудникам
                for employee_id, data in employee_workload.items():
                    text += f"{data['name']} ({data['position']}):\n"

                    # Сортируем задачи по датам
                    sorted_tasks = sorted(data['tasks'],
                                          key=lambda t: t.get('start_date', '9999-12-31')
                                          if t.get('start_date') else '9999-12-31')

                    for task in sorted_tasks:
                        # Определяем даты
                        start_date = "?"
                        end_date = "?"

                        if task['id'] in result['task_dates']:
                            start_date = format_date(result['task_dates'][task['id']]['start'])
                            end_date = format_date(result['task_dates'][task['id']]['end'])
                        elif task.get('start_date') and task.get('end_date'):
                            start_date = format_date(task['start_date'])
                            end_date = format_date(task['end_date'])

                        # Выводим информацию о задаче
                        text += f"  • {task['name']} ({task['duration']} дн.)\n"
                        text += f"    Даты: {start_date} - {end_date}\n"

                    # Суммарная нагрузка сотрудника
                    total_load = sum(task['duration'] for task in data['tasks'])
                    text += f"  Общая нагрузка: {total_load} дней\n\n"
            else:
                text += "\nНе удалось автоматически распределить задачи."

            # Добавляем рекомендации или замечания
            text += f"📝 РЕКОМЕНДАЦИИ\n"
            text += f"1. Обратите особое внимание на задачи критического пути\n"
            text += f"2. При необходимости перераспределите нагрузку между сотрудниками\n"
            text += f"3. Для сокращения сроков выполнения проекта оптимизируйте критические задачи\n\n"

            # Добавляем подпись
            text += f"=============================================\n"
            text += f"Отчет сгенерирован {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
            text += f"Система автоматизированного календарного планирования"

            # Генерируем диаграмму Ганта
            gantt_image = gantt_chart.generate(project.to_dict(), [task.to_dict() for task in tasks],
                                               result['task_dates'], result['critical_path'])

            # Создаем файл для отчета, чтобы избежать ошибки MESSAGE_TOO_LONG
            # Создаем безопасное имя файла
            safe_project_name = "".join(c if c.isalnum() or c in [' ', '.', '_', '-'] else '_' for c in project.name)

            temp_dir = tempfile.mkdtemp()
            report_file_path = os.path.join(temp_dir, f"{safe_project_name}_report.txt")

            # Записываем отчет в файл
            with open(report_file_path, 'w', encoding='utf-8') as file:
                file.write(text)

            # Отправляем краткое сообщение и файл
            await callback.message.edit_text(
                f"Расчет календарного плана для проекта '{project.name}' завершен.\n"
                f"Длительность проекта: {result.get('duration', 'Не определена')} дней.\n"
                f"Полный отчет прилагается в файле."
            )

            # Отправляем файл с отчетом
            report_file = FSInputFile(report_file_path)
            await bot.send_document(
                callback.from_user.id,
                report_file,
                caption=f"Отчет по проекту '{project.name}'"
            )

            # Отправляем диаграмму Ганта
            gantt_file = FSInputFile(gantt_image)
            await bot.send_photo(
                callback.from_user.id,
                gantt_file,
                caption=f"Диаграмма Ганта для проекта '{project.name}'",
            )

            # Отправляем кнопки для дальнейших действий
            buttons = [
                [InlineKeyboardButton(text="Просмотреть распределение", callback_data=f"workload_{project_id}")],
                [InlineKeyboardButton(text="Назад к проекту", callback_data=f"view_project_{project_id}")]
            ]

            markup = InlineKeyboardMarkup(inline_keyboard=buttons)
            await callback.message.reply("Расчет календарного плана и распределение задач завершены",
                                         reply_markup=markup)

            # Очистка временных файлов
            try:
                if os.path.exists(report_file_path):
                    os.remove(report_file_path)
                if os.path.exists(gantt_image):
                    os.remove(gantt_image)
            except Exception as e:
                logger.error(f"Ошибка при очистке временных файлов: {str(e)}")

        except Exception as e:
            error_msg = f"Ошибка при расчете календарного плана: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_msg)
            await callback.message.edit_text(error_msg)
            return