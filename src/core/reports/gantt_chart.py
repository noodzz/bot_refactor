import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import os
import tempfile
import datetime
import logging
from typing import List, Dict, Any, Optional, Set

logger = logging.getLogger(__name__)


class GanttChart:
    """Генератор диаграммы Ганта для проекта с корректным отображением критического пути"""

    def __init__(self):
        """Инициализирует генератор диаграммы Ганта"""
        self.temp_dir = tempfile.mkdtemp()

    def generate(self, project: Dict[str, Any], tasks: List[Dict[str, Any]],
                 task_dates: Dict[int, Dict[str, str]], critical_path: Optional[List[int]] = None,
                 dependencies: Optional[Dict[int, List[int]]] = None) -> str:
        """
        Генерирует диаграмму Ганта для проекта с учетом зависимостей

        Args:
            project (dict): Информация о проекте
            tasks (list): Список задач проекта
            task_dates (dict): Словарь с датами начала и окончания задач
            critical_path (list, optional): Список ID задач, входящих в критический путь
            dependencies (dict, optional): Словарь зависимостей между задачами

        Returns:
            str: Путь к созданному файлу диаграммы
        """
        logger.info(f"Генерация диаграммы Ганта для проекта '{project.get('name')}'")

        # Фильтруем только основные задачи (без подзадач)
        main_tasks = [task for task in tasks if not task.get('parent_id')]

        # Создаем словарь для быстрого доступа к задачам
        task_dict = {task.get('id'): task for task in tasks}

        # Проверяем наличие данных для генерации диаграммы
        if not task_dates:
            logger.warning("Нет данных о датах задач для генерации диаграммы Ганта")
            return self._generate_empty_chart(project)

        logger.info(f"Получено {len(task_dates)} записей с датами для диаграммы Ганта")

        # Формируем список задач с датами, сортируя по дате начала
        task_list = []
        for task_id, dates in task_dates.items():
            if task_id in task_dict:
                task = task_dict[task_id]

                # Пропускаем подзадачи для основной диаграммы
                if task.get('parent_id'):
                    continue

                try:
                    start_date = datetime.datetime.strptime(dates['start'], '%Y-%m-%d')
                    end_date = datetime.datetime.strptime(dates['end'], '%Y-%m-%d')
                    is_critical = task_id in critical_path if critical_path else False

                    task_list.append({
                        'id': task_id,
                        'name': task.get('name', f'Задача {task_id}'),
                        'duration': task.get('duration', 1),
                        'start': start_date,
                        'end': end_date,
                        'is_critical': is_critical
                    })

                    logger.debug(
                        f"Задача {task_id} '{task.get('name')}': "
                        f"{start_date.strftime('%Y-%m-%d')} - {end_date.strftime('%Y-%m-%d')}"
                    )
                except Exception as e:
                    logger.error(f"Ошибка при обработке дат для задачи {task_id}: {e}")

        # Сортируем задачи по дате начала
        task_list.sort(key=lambda x: x['start'])

        # Создаем списки для построения диаграммы
        sorted_tasks = []
        start_dates = []
        end_dates = []
        colors = []

        for task in task_list:
            sorted_tasks.append(task)
            start_dates.append(task['start'])
            # КРИТИЧЕСКИ ВАЖНО: для правильного отображения прямоугольников
            # конечная дата должна быть на следующий день после фактического окончания
            end_dates.append(task['end'] + datetime.timedelta(days=1))

            # Определяем цвет задачи (красный для критического пути)
            colors.append('r' if task['is_critical'] else 'b')

        # Определяем общие даты проекта
        if start_dates and end_dates:
            project_start = min(start_dates)
            project_end = max([end - datetime.timedelta(days=1) for end in end_dates])
        else:
            # Если нет задач с датами, используем даты проекта
            project_start = datetime.datetime.strptime(project.get('start_date', '2025-01-01'), '%Y-%m-%d')
            project_end = project_start + datetime.timedelta(days=30)

        # Конец проекта для отображения (на день больше)
        project_end_display = project_end + datetime.timedelta(days=1)

        # Создаем фигуру с нужными размерами
        fig_height = max(8, len(sorted_tasks) * 0.4 + 2)
        fig, ax = plt.subplots(figsize=(12, fig_height))

        # Названия задач
        labels = [f"{task['name']} ({task['duration']} дн.)" for task in sorted_tasks]
        y_positions = np.arange(len(labels))

        # Рисуем горизонтальные полосы для задач
        for i, (start, end, task, color) in enumerate(zip(start_dates, end_dates, sorted_tasks, colors)):
            # Вычисляем ширину полосы в днях
            width_days = (end - start).days

            # Рисуем прямоугольник
            ax.barh(y_positions[i], width_days, left=start, height=0.5, align='center',
                    color=color, alpha=0.8, edgecolor='black')

            # Добавляем даты по бокам прямоугольника
            # Начальная дата
            ax.text(start - datetime.timedelta(days=0.2), y_positions[i],
                    start.strftime('%d.%m'),
                    va='center', ha='right', fontsize=8)

            # Конечная дата (невключительная)
            ax.text(end + datetime.timedelta(days=0.2), y_positions[i],
                    (end - datetime.timedelta(days=1)).strftime('%d.%m'),
                    va='center', ha='left', fontsize=8)

        # Если есть информация о зависимостях, отображаем их стрелками
        if dependencies:
            self._draw_dependencies(ax, sorted_tasks, dependencies, task_dict, y_positions)

        # Настраиваем оси
        ax.set_yticks(y_positions)
        ax.set_yticklabels(labels)
        ax.set_xlabel('Дата')
        ax.set_ylabel('Задача')

        # Устанавливаем диапазон дат с небольшим запасом
        date_padding = datetime.timedelta(days=max(3, int((project_end_display - project_start).days * 0.05)))
        ax.set_xlim(project_start - date_padding, project_end_display + date_padding)

        # Форматируем заголовок с добавлением длительности проекта
        project_duration = (project_end - project_start).days + 1  # +1 т.к. включительно
        ax.set_title(f'Диаграмма Ганта для проекта "{project.get("name", "Проект")}"'
                     f'\nДлительность: {project_duration} дней')

        # Добавляем сетку
        ax.grid(True, axis='x', linestyle='--', alpha=0.7)

        # Форматируем даты на оси x
        date_format = mdates.DateFormatter('%d.%m.%Y')
        ax.xaxis.set_major_formatter(date_format)

        # Устанавливаем интервал для делений оси X
        if project_duration <= 14:
            ax.xaxis.set_major_locator(mdates.DayLocator(interval=1))
        elif project_duration <= 60:
            ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=0))
        else:
            ax.xaxis.set_major_locator(mdates.MonthLocator())

        # Поворачиваем метки
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)

        # Добавляем даты начала и окончания проекта
        ax.axvline(x=project_start, color='g', linestyle='--', alpha=0.7)
        ax.axvline(x=project_end_display, color='g', linestyle='--', alpha=0.7)

        # Подписываем даты начала и окончания проекта
        ax.text(project_start, -1, f"Начало: {project_start.strftime('%d.%m.%Y')}",
                ha='center', va='top', color='g', fontweight='bold')
        ax.text(project_end_display, -1, f"Окончание: {project_end.strftime('%d.%m.%Y')}",
                ha='center', va='top', color='g', fontweight='bold')

        # Добавляем легенду
        from matplotlib.lines import Line2D
        legend_elements = [
            Line2D([0], [0], color='r', lw=4, label='Критический путь'),
            Line2D([0], [0], color='b', lw=4, label='Обычные задачи')
        ]
        ax.legend(handles=legend_elements, loc='upper right')

        # Добавляем примечание о формате дат
        fig.text(0.5, 0.01,
                 "Примечание: Конечные даты указаны невключительно. Например, задача '19.05 - 21.05' продолжается до конца дня 20.05.",
                 ha='center', fontsize=9)

        # Плотная компоновка
        fig.tight_layout(rect=[0, 0.03, 1, 0.97])  # Оставляем место для примечания

        # Создаем безопасное имя файла
        safe_project_name = "".join(
            c if c.isalnum() or c in [' ', '.', '_', '-'] else '_' for c in project.get('name', 'project')
        )

        # Сохраняем диаграмму
        chart_file = os.path.join(self.temp_dir, f"{safe_project_name}_gantt.png")
        plt.savefig(chart_file, dpi=200, bbox_inches='tight')
        plt.close(fig)

        logger.info(f"Диаграмма Ганта сохранена в файл: {chart_file}")
        return chart_file

    def _draw_dependencies(self, ax, tasks, dependencies, task_dict, y_positions):
        """
        Отображает зависимости между задачами стрелками

        Args:
            ax: Объект графика matplotlib
            tasks: Список задач с датами
            dependencies: Словарь зависимостей
            task_dict: Словарь задач для быстрого доступа
            y_positions: Позиции задач по оси Y
        """
        # Создаем словарь для быстрого доступа к позициям задач
        task_positions = {}
        for i, task in enumerate(tasks):
            task_positions[task['id']] = i

        # Для каждой задачи отображаем ее зависимости
        for task in tasks:
            task_id = task['id']

            # Получаем предшественников задачи
            preds = dependencies.get(task_id, [])

            # Отображаем зависимости стрелками
            for pred_id in preds:
                # Проверяем, что предшественник есть в списке задач
                if pred_id not in task_positions:
                    continue

                # Получаем позиции задач
                pred_pos = task_positions[pred_id]
                task_pos = task_positions[task_id]

                # Получаем даты окончания предшественника и начала текущей задачи
                pred_end = tasks[pred_pos]['end'] + datetime.timedelta(days=1)
                task_start = tasks[task_pos]['start']

                # Отображаем стрелку зависимости, если даты соблюдают зависимость
                if pred_end <= task_start:
                    # Уже все корректно, стрелку не рисуем
                    continue

                # Стрелка зависимости
                ax.annotate('',
                            xy=(tasks[task_pos]['start'], y_positions[task_pos]),
                            xytext=(tasks[pred_pos]['end'] + datetime.timedelta(days=1), y_positions[pred_pos]),
                            arrowprops=dict(arrowstyle='->', linestyle='--', color='gray', alpha=0.6))

    def _generate_empty_chart(self, project):
        """
        Генерирует пустую диаграмму, если нет данных о задачах

        Args:
            project: Информация о проекте

        Returns:
            str: Путь к созданному файлу диаграммы
        """
        fig, ax = plt.subplots(figsize=(10, 6))

        ax.text(0.5, 0.5, "Нет данных для построения диаграммы Ганта",
                horizontalalignment='center', verticalalignment='center',
                transform=ax.transAxes, fontsize=14)

        ax.set_title(f'Диаграмма Ганта для проекта "{project.get("name", "Проект")}"')

        # Удаляем оси
        ax.set_axis_off()

        # Создаем безопасное имя файла
        safe_project_name = "".join(
            c if c.isalnum() or c in [' ', '.', '_', '-'] else '_' for c in project.get('name', 'project')
        )

        # Сохраняем диаграмму
        chart_file = os.path.join(self.temp_dir, f"{safe_project_name}_gantt.png")
        plt.savefig(chart_file, dpi=200, bbox_inches='tight')
        plt.close(fig)

        return chart_file