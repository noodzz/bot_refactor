from typing import List, Dict, Any, Optional
import datetime
import logging
from collections import defaultdict

from src.core.models.employee import Employee
from src.core.models.task import Task
from src.core.algorithms.network_model import NetworkModel
from src.core.algorithms.resource_allocation import (
    check_employee_availability,
    find_suitable_employee,
    find_suitable_employee_with_days_off, find_available_date, topological_sort
)
from src.core.services.employee_service import EmployeeService
from src.core.services.task_service import TaskService

logger = logging.getLogger(__name__)


class ScheduleService:
    """Сервис для календарного планирования"""

    def __init__(self, task_service: TaskService, employee_service: EmployeeService):
        """
        Инициализирует сервис календарного планирования

        Args:
            task_service: Сервис задач
            employee_service: Сервис сотрудников
        """
        self.task_service = task_service
        self.employee_service = employee_service
        self.network_model = NetworkModel()

    def calculate_schedule(self, project: Dict[str, Any], tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Рассчитывает календарный план проекта

        Args:
            project: Информация о проекте
            tasks: Список задач проекта

        Returns:
            dict: Результаты расчета (длительность проекта, критический путь, даты задач)
        """
        logger.info(f"Начинаем расчет календарного плана для проекта '{project['name']}'...")

        # Вызываем метод расчета сетевой модели
        result = self.network_model.calculate(project, tasks)

        # Если расчет успешен, назначаем сотрудников на задачи
        if result['task_dates']:
            logger.info(f"Расчет календарного плана успешен. Назначаем сотрудников на задачи...")

            # Обновляем даты задач в базе данных
            self.task_service.update_task_dates(result['task_dates'])

            # Получаем всех сотрудников
            employees = self.employee_service.get_all_employees()

            # Словарь для отслеживания загрузки сотрудников (в днях)
            employee_workload = {}
            for employee in employees:
                employee_workload[employee.id] = 0

            # Словарь для отслеживания загрузки сотрудников по дням
            employee_daily_load = {}

            # Назначаем сотрудников на задачи
            for task_id, dates in result['task_dates'].items():
                try:
                    task = self.task_service.get_task(task_id)

                    # Пропускаем групповые задачи и задачи без позиции
                    if task.is_group or not task.position:
                        continue

                    # Если сотрудник уже назначен, проверяем его доступность
                    if task.employee_id:
                        is_available = check_employee_availability(
                            task.employee_id,
                            dates['start'],
                            task.duration,
                            self.employee_service
                        )

                        if is_available:
                            # Обновляем загрузку сотрудника
                            employee_workload[task.employee_id] = employee_workload.get(task.employee_id,
                                                                                        0) + task.duration
                            # Обновляем загрузку по дням
                            if task.employee_id not in employee_daily_load:
                                employee_daily_load[task.employee_id] = {}

                            start_date = datetime.datetime.strptime(dates['start'], '%Y-%m-%d')
                            end_date = datetime.datetime.strptime(dates['end'], '%Y-%m-%d')
                            current_date = start_date

                            while current_date <= end_date:
                                date_str = current_date.strftime('%Y-%m-%d')
                                if date_str not in employee_daily_load[task.employee_id]:
                                    employee_daily_load[task.employee_id][date_str] = 0

                                employee_daily_load[task.employee_id][date_str] += 1
                                current_date += datetime.timedelta(days=1)

                            continue

                    # Если сотрудник не назначен или не доступен, ищем подходящего
                    suitable_employees = self.employee_service.get_employees_by_position(task.position)

                    if not suitable_employees:
                        logger.warning(f"Не найдены сотрудники с должностью '{task.position}' для задачи {task.name}")
                        continue

                    # Проверяем, можно ли назначить какого-то сотрудника на текущие даты
                    employee_assigned = False
                    for employee in suitable_employees:
                        if check_employee_availability(employee.id, dates['start'], task.duration,
                                                       self.employee_service):
                            # Назначаем сотрудника на задачу с текущими датами
                            self.task_service.assign_employee(task_id, employee.id)
                            employee_workload[employee.id] = employee_workload.get(employee.id, 0) + task.duration
                            employee_assigned = True
                            logger.info(f"Сотрудник {employee.name} назначен на задачу {task.name} (даты не менялись)")
                            break

                    # Если никого нельзя назначить на текущие даты, пробуем сдвинуть даты
                    if not employee_assigned:
                        logger.info(
                            f"Никто не доступен для задачи {task.name} на даты {dates['start']} - {dates['end']}, пробуем сдвинуть")

                        # Сортируем сотрудников по загрузке (выбираем наименее загруженных)
                        sorted_employees = sorted(suitable_employees, key=lambda e: employee_workload.get(e.id, 0))

                        # Пробуем каждого сотрудника и ищем для него доступные даты
                        for employee in sorted_employees:
                            new_start, new_end = find_available_date(
                                employee.id, dates['start'], task.duration, self.employee_service
                            )

                            if new_start and new_end:
                                # Назначаем сотрудника и обновляем даты
                                self.task_service.assign_employee(task_id, employee.id)
                                self.task_service.update_task_dates({task_id: {'start': new_start, 'end': new_end}})

                                # Обновляем загрузку
                                employee_workload[employee.id] = employee_workload.get(employee.id, 0) + task.duration

                                logger.info(
                                    f"Задача {task.name} смещена на {new_start} - {new_end} и назначена на {employee.name}")
                                employee_assigned = True
                                break

                        if not employee_assigned:
                            logger.warning(
                                f"Не удалось найти доступные даты для задачи {task.name} ни для одного сотрудника")

                except Exception as e:
                    logger.error(f"Ошибка при назначении сотрудника на задачу {task_id}: {str(e)}")
            # Проверяем корректность зависимостей
            logger.info("Проверка корректности зависимостей между задачами...")
            corrected_task_dates = self._validate_task_dependencies(result['task_dates'], tasks)
            result['task_dates'] = corrected_task_dates
            # Обрабатываем подзадачи для групповых задач
            self._process_subtasks_for_groups(result['task_dates'], employee_workload)

        return result

    def _process_subtasks_for_groups(self, task_dates: Dict[int, Dict[str, str]],
                                     employee_workload: Dict[int, int]) -> None:
        """
        Обрабатывает подзадачи для групповых задач, назначая даты и сотрудников

        Args:
            task_dates: Словарь с датами задач
            employee_workload: Словарь с загрузкой сотрудников
        """
        logger.info("Обработка подзадач для групповых задач...")

        # Получаем список всех групповых задач с датами
        group_tasks = []
        for task_id, task_data in task_dates.items():
            if 'start' in task_data and 'end' in task_data:
                # Проверяем, является ли задача групповой
                task = self.task_service.get_task(task_id)
                if task and task.is_group:
                    group_tasks.append((task_id, task_data))

        logger.info(f"Найдено {len(group_tasks)} групповых задач для обработки")

        # Обрабатываем каждую групповую задачу
        for group_id, group_data in group_tasks:
            # Получаем подзадачи
            subtasks = self.task_service.get_subtasks(group_id)

            if not subtasks:
                continue

            logger.info(f"Обработка {len(subtasks)} подзадач для групповой задачи {group_id}")

            group_start = group_data['start']
            group_end = group_data['end']

            # Стратегия распределения подзадач
            # Если подзадача имеет флаг parallel=True, начинаем с даты начала групповой задачи
            # Иначе распределяем подзадачи последовательно

            # Преобразуем строковые даты в объекты datetime
            try:
                group_start_dt = datetime.datetime.strptime(group_start, '%Y-%m-%d')
                group_end_dt = datetime.datetime.strptime(group_end, '%Y-%m-%d')

                # Находим подзадачи с назначенными сотрудниками
                assigned_subtasks = [st for st in subtasks if st.employee_id]

                # Если есть подзадачи с назначенными сотрудниками, используем их даты
                if assigned_subtasks:
                    for subtask in assigned_subtasks:
                        # Эти подзадачи уже обработаны основным алгоритмом
                        continue

                # Обрабатываем параллельные подзадачи
                parallel_subtasks = [st for st in subtasks if st.parallel]
                for subtask in parallel_subtasks:
                    subtask_id = subtask.id

                    if subtask_id not in task_dates:  # Если подзадача еще не обработана
                        # Устанавливаем даты в зависимости от длительности
                        subtask_duration = subtask.duration
                        subtask_start_dt = group_start_dt
                        subtask_end_dt = min(group_end_dt,
                                             group_start_dt + datetime.timedelta(days=subtask_duration - 1))

                        # Назначаем сотрудника для подзадачи
                        assigned_employee_id = None

                        if subtask.position:
                            position = subtask.position

                            # Пытаемся найти подходящего сотрудника с учетом выходных дней
                            assigned_employee_id = find_suitable_employee_with_days_off(
                                position,
                                subtask_start_dt.strftime('%Y-%m-%d'),
                                subtask_duration,
                                self.employee_service,
                                employee_workload
                            )

                            # Если не нашли подходящего сотрудника, но есть сотрудники с нужной должностью
                            if not assigned_employee_id:
                                suitable_employees = self.employee_service.get_employees_by_position(position)
                                if suitable_employees:
                                    # Выбираем сотрудника с наименьшей загрузкой
                                    best_employee = min(suitable_employees,
                                                        key=lambda e: employee_workload.get(e.id, 0))
                                    assigned_employee_id = best_employee.id

                                    # Ищем подходящую дату с учетом выходных
                                    result = find_suitable_employee(
                                        position,
                                        subtask_start_dt.strftime('%Y-%m-%d'),
                                        subtask_duration,
                                        self.employee_service,
                                        employee_workload
                                    )

                                    if result:
                                        assigned_employee_id, new_start, new_end, _ = result
                                        # Используем найденные доступные даты
                                        subtask_start_dt = datetime.datetime.strptime(new_start, '%Y-%m-%d')
                                        subtask_end_dt = datetime.datetime.strptime(new_end, '%Y-%m-%d')
                                        logger.info(
                                            f"Перенесли даты подзадачи {subtask_id} на {new_start} - {new_end} "
                                            f"для сотрудника {assigned_employee_id}"
                                        )

                        # Если сотрудник уже назначен, используем его
                        if subtask.employee_id:
                            assigned_employee_id = subtask.employee_id

                        # Обновляем даты и назначение в базе данных
                        if assigned_employee_id:
                            # Обновляем даты и назначенного сотрудника
                            self.task_service.assign_employee(subtask_id, assigned_employee_id)
                            self.task_service.update_task_dates({
                                subtask_id: {
                                    'start': subtask_start_dt.strftime('%Y-%m-%d'),
                                    'end': subtask_end_dt.strftime('%Y-%m-%d')
                                }
                            })
                            logger.info(
                                f"Обновлены даты и назначен сотрудник {assigned_employee_id} "
                                f"для параллельной подзадачи {subtask_id}"
                            )
                        else:
                            # Обновляем только даты
                            self.task_service.update_task_dates({
                                subtask_id: {
                                    'start': subtask_start_dt.strftime('%Y-%m-%d'),
                                    'end': subtask_end_dt.strftime('%Y-%m-%d')
                                }
                            })
                            logger.info(
                                f"Обновлены даты для параллельной подзадачи {subtask_id} (сотрудник не назначен)"
                            )

                # Обрабатываем последовательные подзадачи
                sequential_subtasks = [st for st in subtasks if not st.parallel]
                current_date = group_start_dt

                for subtask in sequential_subtasks:
                    subtask_id = subtask.id

                    if subtask_id not in task_dates:  # Если подзадача еще не обработана
                        # Устанавливаем даты в зависимости от длительности
                        subtask_duration = subtask.duration
                        subtask_start = current_date
                        subtask_end = min(group_end_dt, subtask_start + datetime.timedelta(days=subtask_duration - 1))

                        # Назначаем сотрудника для подзадачи
                        assigned_employee_id = None

                        if subtask.position:
                            position = subtask.position
                            suitable_employees = self.employee_service.get_employees_by_position(position)

                            if suitable_employees:
                                # Пытаемся найти подходящего сотрудника с учетом выходных дней
                                result = find_suitable_employee(
                                    position,
                                    subtask_start.strftime('%Y-%m-%d'),
                                    subtask_duration,
                                    self.employee_service,
                                    employee_workload
                                )

                                if result:
                                    assigned_employee_id, new_start, new_end, _ = result
                                    # Используем найденные доступные даты
                                    subtask_start = datetime.datetime.strptime(new_start, '%Y-%m-%d')
                                    subtask_end = datetime.datetime.strptime(new_end, '%Y-%m-%d')
                                else:
                                    # Если не нашли подходящего сотрудника, выбираем наименее загруженного
                                    best_employee = min(suitable_employees,
                                                        key=lambda e: employee_workload.get(e.id, 0))
                                    assigned_employee_id = best_employee.id

                        # Если сотрудник уже назначен, используем его
                        if subtask.employee_id:
                            assigned_employee_id = subtask.employee_id

                        # Обновляем даты и назначение в базе данных
                        if assigned_employee_id:
                            # Обновляем даты и назначенного сотрудника
                            self.task_service.assign_employee(subtask_id, assigned_employee_id)
                            self.task_service.update_task_dates({
                                subtask_id: {
                                    'start': subtask_start.strftime('%Y-%m-%d'),
                                    'end': subtask_end.strftime('%Y-%m-%d')
                                }
                            })
                            logger.info(
                                f"Обновлены даты и назначен сотрудник {assigned_employee_id} "
                                f"для последовательной подзадачи {subtask_id}"
                            )
                        else:
                            # Обновляем только даты
                            self.task_service.update_task_dates({
                                subtask_id: {
                                    'start': subtask_start.strftime('%Y-%m-%d'),
                                    'end': subtask_end.strftime('%Y-%m-%d')
                                }
                            })
                            logger.info(
                                f"Обновлены даты для последовательной подзадачи {subtask_id} (сотрудник не назначен)"
                            )

                        # Переходим к следующей дате
                        current_date = subtask_end + datetime.timedelta(days=1)

            except Exception as e:
                logger.error(f"Ошибка при обработке подзадач для групповой задачи {group_id}: {str(e)}")

    def _validate_task_dependencies(self, task_dates: Dict[int, Dict[str, str]],
                                    tasks: List[Dict[str, Any]]) -> Dict[int, Dict[str, str]]:
        """
        Проверяет и корректирует даты задач с учетом зависимостей

        Args:
            task_dates: Словарь с датами задач
            tasks: Список задач проекта

        Returns:
            Dict[int, Dict[str, str]]: Скорректированный словарь с датами задач
        """
        # Создаем копию, чтобы не изменять оригинальный словарь
        corrected_dates = {}
        for task_id, dates in task_dates.items():
            corrected_dates[task_id] = dates.copy()

        # Строим словарь зависимостей для быстрого доступа
        dependencies = {}
        task_by_id = {}

        for task in tasks:
            task_id = task.get('id')
            if not task_id:
                continue

            task_by_id[task_id] = task

            # Получаем список предшественников
            predecessors = []
            pred_data = task.get('predecessors', [])
            if isinstance(pred_data, list):
                predecessors = pred_data
            elif isinstance(pred_data, str) and pred_data.strip():
                try:
                    import json
                    # Пробуем парсить JSON
                    predecessors = json.loads(pred_data)
                except Exception as e:
                    logger.warning(f"Не удалось разобрать предшественников для задачи {task_id}: {e}")

            dependencies[task_id] = predecessors

        sorted_tasks = topological_sort(dependencies)

        # Проверяем зависимости для каждой задачи
        for task_id in sorted_tasks:
            if task_id not in corrected_dates:
                continue  # Пропускаем задачи без дат

            # Получаем предшественников текущей задачи
            predecessors = dependencies.get(task_id, [])

            # Если нет предшественников, переходим к следующей задаче
            if not predecessors:
                continue

            # Получаем дату начала текущей задачи
            task_dates = corrected_dates[task_id]
            task_start_str = task_dates['start']
            task_start = datetime.datetime.strptime(task_start_str, '%Y-%m-%d')

            # Проверяем всех предшественников
            needs_adjustment = False
            latest_end_date = None

            for pred_id in predecessors:
                if pred_id not in corrected_dates:
                    continue  # Пропускаем предшественников без дат

                # Получаем дату окончания предшественника
                pred_dates = corrected_dates[pred_id]
                pred_end_str = pred_dates['end']
                pred_end = datetime.datetime.strptime(pred_end_str, '%Y-%m-%d')

                # Если предшественник заканчивается позже текущей даты начала задачи
                if pred_end >= task_start:
                    needs_adjustment = True
                    if latest_end_date is None or pred_end > latest_end_date:
                        latest_end_date = pred_end

            # Если требуется корректировка
            if needs_adjustment and latest_end_date:
                # Рассчитываем новые даты
                new_start_date = latest_end_date + datetime.timedelta(days=1)

                # Получаем длительность задачи
                task_duration = 0
                if task_id in task_by_id:
                    task_info = task_by_id[task_id]
                    task_duration = task_info.get('duration', 0) - 1  # -1 т.к. включаем последний день
                else:
                    # Вычисляем длительность из дат
                    task_end = datetime.datetime.strptime(task_dates['end'], '%Y-%m-%d')
                    task_duration = (task_end - task_start).days

                # Вычисляем новую дату окончания
                new_end_date = new_start_date + datetime.timedelta(days=task_duration)

                # Обновляем даты
                old_dates = corrected_dates[task_id].copy()
                corrected_dates[task_id] = {
                    'start': new_start_date.strftime('%Y-%m-%d'),
                    'end': new_end_date.strftime('%Y-%m-%d')
                }

                logger.info(
                    f"Скорректированы даты для задачи {task_id} '{task_by_id.get(task_id, {}).get('name', f'Задача {task_id}')}' "
                    f"с {old_dates['start']} - {old_dates['end']} "
                    f"на {corrected_dates[task_id]['start']} - {corrected_dates[task_id]['end']} "
                    f"из-за зависимостей от предшественников"
                )

                # После изменения дат текущей задачи
                # необходимо проверить задачи, зависящие от нее
                self._adjust_dependent_tasks(task_id, corrected_dates, dependencies, task_by_id)

        return corrected_dates

    def _adjust_dependent_tasks(self, task_id: int, task_dates: Dict[int, Dict[str, str]],
                                dependencies: Dict[int, List[int]], task_by_id: Dict[int, Dict[str, Any]]):
        """
        Рекурсивно корректирует даты зависимых задач

        Args:
            task_id: ID задачи, даты которой были изменены
            task_dates: Словарь с датами задач
            dependencies: Словарь зависимостей
            task_by_id: Словарь задач по ID
        """
        import datetime

        # Находим все задачи, зависящие от данной
        dependent_tasks = []
        for dep_id, preds in dependencies.items():
            if task_id in preds:
                dependent_tasks.append(dep_id)

        # Корректируем даты зависимых задач
        for dep_id in dependent_tasks:
            if dep_id not in task_dates:
                continue

            # Получаем даты текущей задачи и зависимой
            task_end_date = datetime.datetime.strptime(task_dates[task_id]['end'], '%Y-%m-%d')
            dep_start_date = datetime.datetime.strptime(task_dates[dep_id]['start'], '%Y-%m-%d')

            # Если начало зависимой задачи раньше окончания текущей, корректируем
            if dep_start_date <= task_end_date:
                # Новое начало - день после окончания текущей задачи
                new_start_date = task_end_date + datetime.timedelta(days=1)

                # Длительность зависимой задачи
                dep_duration = 0
                if dep_id in task_by_id:
                    dep_duration = task_by_id[dep_id].get('duration', 1) - 1  # -1 т.к. включаем последний день
                else:
                    # Вычисляем длительность из дат
                    dep_end_date = datetime.datetime.strptime(task_dates[dep_id]['end'], '%Y-%m-%d')
                    dep_duration = (dep_end_date - dep_start_date).days

                # Новое окончание
                new_end_date = new_start_date + datetime.timedelta(days=dep_duration)

                # Обновляем даты
                old_dates = task_dates[dep_id].copy()
                task_dates[dep_id] = {
                    'start': new_start_date.strftime('%Y-%m-%d'),
                    'end': new_end_date.strftime('%Y-%m-%d')
                }

                logger.info(
                    f"Скорректированы даты для зависимой задачи {dep_id} с {old_dates['start']} - {old_dates['end']} "
                    f"на {task_dates[dep_id]['start']} - {task_dates[dep_id]['end']} "
                    f"из-за изменения дат задачи {task_id}"
                )

                # Рекурсивно проверяем задачи, зависящие от этой
                self._adjust_dependent_tasks(dep_id, task_dates, dependencies, task_by_id)