import datetime
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


def generate_schedule_report(project: Dict[str, Any],
                             tasks: List[Dict[str, Any]],
                             result: Dict[str, Any],
                             employee_service=None) -> str:
    """
    Генерирует отчет по результатам расчета календарного плана

    Args:
        project: Информация о проекте
        tasks: Список задач
        result: Результаты расчета
        employee_service: Сервис сотрудников (опционально)

    Returns:
        str: Текстовый отчет
    """
    # Создаем словарь задач для быстрого доступа
    task_dict = {task['id']: task for task in tasks}

    # Извлекаем данные из результата
    task_dates = result.get('task_dates', {})
    critical_path = result.get('critical_path', [])
    duration = result.get('duration', 0)

    # Начинаем формировать отчет
    report = "📊 ОТЧЕТ ПО КАЛЕНДАРНОМУ ПЛАНУ\n"
    report += "=============================================\n\n"

    # Общая информация о проекте
    report += "📋 ОБЩАЯ ИНФОРМАЦИЯ О ПРОЕКТЕ\n"
    report += f"Название проекта: '{project.get('name', 'Неизвестный проект')}'\n"

    # Определяем даты проекта
    if task_dates:
        start_dates = [datetime.datetime.strptime(dates['start'], '%Y-%m-%d') for dates in task_dates.values()]
        end_dates = [datetime.datetime.strptime(dates['end'], '%Y-%m-%d') for dates in task_dates.values()]

        if start_dates and end_dates:
            project_start = min(start_dates)
            project_end = max(end_dates)
            project_duration = (project_end - project_start).days + 1

            report += f"Длительность проекта: {project_duration} дней\n"
            report += f"Дата начала: {project_start.strftime('%d.%m.%Y')}\n"
            report += f"Дата завершения: {project_end.strftime('%d.%m.%Y')}\n\n"
            report += f"Общее количество задач: {len(tasks)}\n\n"
    else:
        report += f"Длительность проекта: {duration} дней\n\n"

    # Критический путь
    report += "🚩 КРИТИЧЕСКИЙ ПУТЬ\n"
    report += "Критический путь — последовательность задач, определяющая длительность проекта.\n"
    report += "Задержка любой из этих задач приведет к задержке всего проекта.\n\n"

    if critical_path:
        critical_tasks = []
        total_critical_days = 0

        for task_id in critical_path:
            task = next((t for t in tasks if t.get('id') == task_id), None)
            if not task:
                continue

            critical_tasks.append(task)
            total_critical_days += task.get('duration', 0)

            # Форматируем даты для отображения
            start_date = "?"
            end_date = "?"

            if task_id in task_dates:
                start_date = datetime.datetime.strptime(task_dates[task_id]['start'], '%Y-%m-%d').strftime('%d.%m.%Y')
                end_date = datetime.datetime.strptime(task_dates[task_id]['end'], '%Y-%m-%d').strftime('%d.%m.%Y')

            # Добавляем информацию о задаче
            report += f"• {task.get('name', f'Задача {task_id}')} ({task.get('duration', 0)} дн.)\n"
            report += f"  Даты: {start_date} - {end_date}\n"

            # Добавляем информацию о сотруднике, если есть
            if employee_service and 'employee_id' in task and task['employee_id']:
                try:
                    employee = employee_service.get_employee(task['employee_id'])
                    report += f"  Исполнитель: {employee.name} ({employee.position})\n"
                except:
                    pass

            report += "\n"

        report += f"Длина критического пути: {total_critical_days} дней\n\n"
    else:
        report += "Критический путь не определен. Возможные причины:\n"
        report += "• Недостаточно связей между задачами\n"
        report += "• Все задачи могут выполняться независимо\n\n"

    # Распределение задач по сотрудникам
    if employee_service:
        report += "👥 РАСПРЕДЕЛЕНИЕ ЗАДАЧ\n"

        try:
            # Получаем распределение задач
            employee_workload = {}

            # Группируем задачи по сотрудникам
            for task in tasks:
                if 'employee_id' in task and task['employee_id']:
                    employee_id = task['employee_id']

                    if employee_id not in employee_workload:
                        try:
                            employee = employee_service.get_employee(employee_id)
                            employee_workload[employee_id] = {
                                'name': employee.name,
                                'position': employee.position,
                                'tasks': []
                            }
                        except:
                            employee_workload[employee_id] = {
                                'name': f"Сотрудник {employee_id}",
                                'position': "Не указана",
                                'tasks': []
                            }

                    # Добавляем задачу
                    employee_workload[employee_id]['tasks'].append(task)

            # Выводим информацию по сотрудникам
            for employee_id, data in employee_workload.items():
                report += f"{data['name']} ({data['position']}):\n"

                # Сортируем задачи по датам
                sorted_tasks = data['tasks']
                if task_dates:
                    sorted_tasks = sorted(
                        data['tasks'],
                        key=lambda t: task_dates.get(t['id'], {}).get('start', '9999-12-31')
                        if t['id'] in task_dates else '9999-12-31'
                    )

                for task in sorted_tasks:
                    # Определяем даты задачи
                    start_date = "?"
                    end_date = "?"

                    if task['id'] in task_dates:
                        start_date = datetime.datetime.strptime(task_dates[task['id']]['start'], '%Y-%m-%d').strftime(
                            '%d.%m.%Y')
                        end_date = datetime.datetime.strptime(task_dates[task['id']]['end'], '%Y-%m-%d').strftime(
                            '%d.%m.%Y')

                    # Выводим информацию о задаче
                    report += f"  • {task.get('name', f'Задача {task['id']}')} ({task.get('duration', 0)} дн.)\n"
                    report += f"    Даты: {start_date} - {end_date}\n"

                # Суммарная нагрузка сотрудника
                total_load = sum(task.get('duration', 0) for task in data['tasks'])
                report += f"  Общая нагрузка: {total_load} дней\n\n"
        except Exception as e:
            logger.error(f"Ошибка при формировании раздела распределения задач: {str(e)}")
            report += "\nНе удалось автоматически распределить задачи.\n\n"

    # Рекомендации
    report += "\n📝 РЕКОМЕНДАЦИИ\n"
    report += "1. Обратите особое внимание на задачи критического пути\n"
    report += "2. При необходимости перераспределите нагрузку между сотрудниками\n"
    report += "3. Для сокращения сроков выполнения проекта оптимизируйте критические задачи\n\n"

    # Завершение отчета
    report += "=============================================\n"
    report += f"Отчет сгенерирован {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
    report += "Система автоматизированного календарного планирования"

    return report