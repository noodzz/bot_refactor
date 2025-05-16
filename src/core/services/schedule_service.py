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
    find_suitable_employee_with_days_off,
    find_available_date
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
        Рассчитывает календарный план проекта с учетом выходных дней

        Args:
            project: Информация о проекте
            tasks: Список задач проекта

        Returns:
            dict: Результаты расчета (длительность проекта, критический путь, даты задач)
        """
        logger.info(f"Начинаем расчет календарного плана для проекта '{project['name']}'...")

        # Вызываем метод расчета сетевой модели (алгоритм Форда), передавая сервис сотрудников
        # для учета выходных дней при расчете дат
        result = self.network_model.calculate(project, tasks, self.employee_service)

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

            # Сортируем задачи по ранним датам начала
            sorted_task_ids = sorted(
                result['task_dates'].keys(),
                key=lambda tid: result['task_dates'][tid]['start']
            )

            # Назначаем сотрудников на задачи в порядке ранних дат начала
            for task_id in sorted_task_ids:
                try:
                    task = self.task_service.get_task(task_id)
                    dates = result['task_dates'][task_id]

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

                    # Получаем подходящих сотрудников для данной должности
                    suitable_employees = self.employee_service.get_employees_by_position(task.position)

                    if not suitable_employees:
                        logger.warning(f"Не найдены сотрудники с должностью '{task.position}' для задачи {task.name}")
                        continue

                    # Пытаемся найти сотрудника на текущие даты
                    employee_assigned = False

                    # Сортируем сотрудников по загрузке
                    sorted_employees = sorted(suitable_employees, key=lambda e: employee_workload.get(e.id, 0))

                    for employee in sorted_employees:
                        if check_employee_availability(employee.id, dates['start'], task.duration,
                                                       self.employee_service):
                            # Назначаем сотрудника
                            self.task_service.assign_employee(task_id, employee.id)
                            employee_workload[employee.id] = employee_workload.get(employee.id, 0) + task.duration
                            employee_assigned = True
                            logger.info(f"Сотрудник {employee.name} назначен на задачу {task.name}")
                            break

                    # Если не нашли сотрудника на текущие даты, ищем с возможностью сдвига дат
                    if not employee_assigned:
                        for employee in sorted_employees:
                            new_start, new_end = find_available_date(
                                employee.id, dates['start'], task.duration, self.employee_service
                            )

                            if new_start and new_end:
                                # Назначаем сотрудника и обновляем даты
                                self.task_service.assign_employee(task_id, employee.id)
                                self.task_service.update_task_dates({task_id: {'start': new_start, 'end': new_end}})
                                result['task_dates'][task_id] = {'start': new_start, 'end': new_end}

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