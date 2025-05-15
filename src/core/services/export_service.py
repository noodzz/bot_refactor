import csv
import tempfile
import os
import json
import datetime
import logging
from typing import List, Dict, Any, Optional
import requests
from requests.auth import HTTPBasicAuth

from src.utils.file_utils import create_safe_filename
from src.core.services.employee_service import EmployeeService

logger = logging.getLogger(__name__)


class ExportService:
    """Сервис для экспорта проектов в другие системы"""

    def __init__(self, jira_url: str, jira_username: str, jira_api_token: str, jira_project: str):
        """
        Инициализирует сервис экспорта

        Args:
            jira_url: URL Jira
            jira_username: Имя пользователя Jira
            jira_api_token: API-токен Jira
            jira_project: Код проекта Jira
        """
        self.temp_dir = tempfile.mkdtemp()
        self.jira_url = jira_url
        self.jira_username = jira_username
        self.jira_api_token = jira_api_token
        self.jira_project = jira_project
        self.START_DATE_FIELD_ID = 'customfield_10015'
        self.CATEGORY_FIELD_ID = 'customfield_10035'
        self.employee_service = None

    def export_to_csv(self, project: Dict[str, Any], tasks: List[Dict[str, Any]]) -> str:
        """
        Создает CSV файл для импорта в Jira

        Args:
            project: Информация о проекте
            tasks: Список задач проекта

        Returns:
            str: Путь к созданному файлу
        """
        export_file = os.path.join(self.temp_dir, f"{create_safe_filename(project['name'])}_jira_export.csv")

        # Определяем поля для экспорта
        fieldnames = [
            'Summary', 'Description', 'Issue Type', 'Priority',
            'Assignee', 'Reporter', 'Original Estimate',
            'Due Date', 'Start Date', 'Parent', 'Predecessors', 'Project'
        ]

        # Создаем CSV-файл
        with open(export_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for task in tasks:
                row = {
                    'Summary': task.get('name', ''),
                    'Description': f"Длительность: {task.get('duration', 0)} дн.",
                    'Issue Type': 'Task',
                    'Priority': 'Medium',
                    'Project': self.jira_project
                }
                writer.writerow(row)

        return export_file

    def import_to_jira(self, project: Dict[str, Any], tasks: List[Dict[str, Any]],
                       employee_service: Optional[EmployeeService] = None) -> Dict[str, Any]:
        """
        Экспортирует задачи в Jira

        Args:
            project: Информация о проекте
            tasks: Список задач проекта
            employee_service: Сервис сотрудников (опционально)

        Returns:
            dict: Результаты экспорта
        """
        if employee_service:
            self.employee_service = employee_service

        try:
            # Проверяем доступность Jira
            if not self.jira_url or not self.jira_username or not self.jira_api_token:
                raise ValueError("Не указаны параметры подключения к Jira")

            # Проверяем соединение с Jira
            try:
                response = requests.get(
                    f"{self.jira_url}/rest/api/2/myself",
                    auth=HTTPBasicAuth(self.jira_username, self.jira_api_token)
                )
                response.raise_for_status()
                logger.info("Успешное подключение к Jira API")
            except Exception as e:
                logger.error(f"Ошибка при подключении к Jira: {str(e)}")
                raise ValueError(f"Не удалось подключиться к Jira: {str(e)}")

            # Получаем доступные типы задач для проекта
            response = requests.get(
                f"{self.jira_url}/rest/api/2/issue/createmeta?projectKeys={self.jira_project}&expand=projects.issuetypes",
                auth=HTTPBasicAuth(self.jira_username, self.jira_api_token)
            )
            response.raise_for_status()

            meta = response.json()
            project_meta = meta['projects'][0]
            project_issue_types = project_meta.get('issuetypes', [])

            # Ищем нужные типы задач
            task_type = None
            subtask_type = None
            epic_type = None

            for itype in project_issue_types:
                if itype['name'] == 'Задача' or itype['name'] == 'Task':
                    task_type = itype
                    logger.info(f"Тип задачи: {task_type['name']} (ID: {task_type['id']})")
                elif itype['name'] == 'Подзадача' or itype['name'] == 'Sub-task':
                    subtask_type = itype
                    logger.info(f"Тип подзадачи: {subtask_type['name']} (ID: {subtask_type['id']})")
                elif itype['name'] == 'Эпик' or itype['name'] == 'Epic':
                    epic_type = itype
                    logger.info(f"Тип эпика: {epic_type['name']} (ID: {epic_type['id']})")

            # Если не нашли нужные типы, используем первый доступный
            if not task_type and project_issue_types:
                task_type = next((t for t in project_issue_types if not t.get('subtask')), project_issue_types[0])
                logger.info(f"Используем тип по умолчанию: {task_type['name']} (ID: {task_type['id']})")

            # Проверка, что у нас есть хотя бы тип задачи
            if not task_type:
                raise ValueError("Не удалось найти подходящий тип задачи в проекте")

            # Создаем главную задачу проекта
            project_name = project.get('name', 'Неизвестный проект')

            main_issue_type = epic_type if epic_type else task_type

            epic_data = {
                'fields': {
                    'project': {'key': self.jira_project},
                    'summary': f"Проект: {project_name}",
                    'description': f"Календарный план проекта '{project_name}'",
                    'issuetype': {'id': main_issue_type['id']}
                }
            }

            response = requests.post(
                f"{self.jira_url}/rest/api/2/issue",
                json=epic_data,
                auth=HTTPBasicAuth(self.jira_username, self.jira_api_token)
            )
            response.raise_for_status()

            epic_issue = response.json()
            logger.info(f"Создана родительская задача проекта: {epic_issue['key']}")

            # Словарь для отслеживания созданных задач
            created_issues = [{'key': epic_issue['key'], 'name': f"Проект: {project_name}"}]
            task_keys = {}  # id задачи -> ключ в Jira

            # Шаг 1: Идентифицируем все групповые задачи и подзадачи
            group_tasks = {}  # id -> task
            child_tasks = {}  # parent_id -> [tasks]

            for task in tasks:
                # Если это групповая задача
                if task.get('is_group') == 1:
                    try:
                        task_id = int(task['id'])
                    except (ValueError, TypeError):
                        task_id = task['id']  # fallback
                    group_tasks[task_id] = task
                    logger.info(f"Найдена групповая задача: {task['name']} (ID: {task_id})")

                parent_id_raw = task.get('parent_id')
                try:
                    parent_id = int(parent_id_raw) if parent_id_raw is not None else None
                except (ValueError, TypeError):
                    parent_id = None

                # Если это подзадача (имеет parent_id)
                if parent_id is not None:
                    if parent_id not in child_tasks:
                        child_tasks[parent_id] = []
                    child_tasks[parent_id].append(task)
                    logger.info(f"Найдена подзадача: {task['name']} для родителя ID={parent_id}")

            # Шаг 2: Создаем групповые задачи и их подзадачи
            for task_id, task in group_tasks.items():
                try:
                    # Определяем категорию для каждой задачи индивидуально
                    category_value = None
                    if self.employee_service and task.get('position'):
                        category = self.employee_service.get_category_by_position(task.get('position'))
                        if category:
                            category_value = {"value": category}

                    # Определяем исполнителя
                    assignee = self._get_assignee_for_task(task_id, task.get('employee_id'))

                    # Создаем групповую задачу
                    task_data = {
                        'fields': {
                            'project': {'key': self.jira_project},
                            'summary': task['name'],
                            'description': f"Длительность: {task.get('duration', 0)} дн.",
                            'issuetype': {'id': task_type['id']},
                            'duedate': task.get('end_date') if task.get('end_date') else None,
                            self.START_DATE_FIELD_ID: task.get('start_date') if task.get('start_date') else None,
                            self.CATEGORY_FIELD_ID: category_value
                        }
                    }

                    if assignee:
                        task_data['fields']['assignee'] = assignee

                    response = requests.post(
                        f"{self.jira_url}/rest/api/2/issue",
                        json=task_data,
                        auth=HTTPBasicAuth(self.jira_username, self.jira_api_token)
                    )
                    response.raise_for_status()

                    task_issue = response.json()
                    task_keys[task_id] = task_issue['key']
                    created_issues.append({'key': task_issue['key'], 'name': task['name']})
                    logger.info(f"Создана групповая задача: {task_issue['key']} - {task['name']}")

                    # Если у этой групповой задачи есть подзадачи, создаем их
                    if task_id in child_tasks and child_tasks[task_id]:
                        logger.info(
                            f"У задачи {task['name']} (ID={task_id}) найдено {len(child_tasks[task_id])} подзадач")

                        for subtask in child_tasks[task_id]:
                            # Определяем категорию для подзадачи
                            subtask_category_value = None
                            if self.employee_service and subtask.get('position'):
                                subtask_category = self.employee_service.get_category_by_position(
                                    subtask.get('position'))
                                if subtask_category:
                                    subtask_category_value = {"value": subtask_category}

                            subtask_assignee = self._get_assignee_for_task(subtask['id'], subtask.get('employee_id'))

                            # Проверка типа подзадачи и правильное создание подзадачи
                            if subtask_type:
                                try:
                                    # Создаем подзадачу с правильным типом
                                    subtask_data = {
                                        'fields': {
                                            'project': {'key': self.jira_project},
                                            'summary': subtask['name'],
                                            'description': f"Длительность: {subtask.get('duration', 0)} дн.\nДолжность: {subtask.get('position', 'Не указана')}",
                                            'issuetype': {'id': subtask_type['id']},
                                            'parent': {'key': task_issue['key']},
                                            'duedate': subtask.get('end_date') if subtask.get('end_date') else None,
                                            self.START_DATE_FIELD_ID: subtask.get('start_date') if subtask.get(
                                                'start_date') else None,
                                            self.CATEGORY_FIELD_ID: subtask_category_value
                                        }
                                    }

                                    if subtask_assignee:
                                        subtask_data['fields']['assignee'] = subtask_assignee

                                    response = requests.post(
                                        f"{self.jira_url}/rest/api/2/issue",
                                        json=subtask_data,
                                        auth=HTTPBasicAuth(self.jira_username, self.jira_api_token)
                                    )
                                    response.raise_for_status()

                                    subtask_issue = response.json()
                                    task_keys[subtask['id']] = subtask_issue['key']
                                    created_issues.append({'key': subtask_issue['key'], 'name': subtask['name']})
                                    logger.info(f"  Создана подзадача: {subtask_issue['key']} - {subtask['name']}")
                                except Exception as e:
                                    logger.error(f"  Ошибка при создании подзадачи {subtask['name']}: {str(e)}")

                                    # План Б: создаем обычную задачу
                                    try:
                                        subtask_task_data = {
                                            'fields': {
                                                'project': {'key': self.jira_project},
                                                'summary': f"{task['name']} - {subtask['name']}",
                                                'description': f"Длительность: {subtask.get('duration', 0)} дн.\nДолжность: {subtask.get('position', 'Не указана')}",
                                                'issuetype': {'id': task_type['id']},
                                                'duedate': subtask.get('end_date') if subtask.get('end_date') else None,
                                                self.START_DATE_FIELD_ID: subtask.get('start_date') if subtask.get(
                                                    'start_date') else None
                                            }
                                        }

                                        response = requests.post(
                                            f"{self.jira_url}/rest/api/2/issue",
                                            json=subtask_task_data,
                                            auth=HTTPBasicAuth(self.jira_username, self.jira_api_token)
                                        )
                                        response.raise_for_status()

                                        subtask_task = response.json()

                                        # Связываем с родительской задачей
                                        link_data = {
                                            'type': {'name': 'Relates'},
                                            'inwardIssue': {'key': subtask_task['key']},
                                            'outwardIssue': {'key': task_issue['key']}
                                        }

                                        response = requests.post(
                                            f"{self.jira_url}/rest/api/2/issueLink",
                                            json=link_data,
                                            auth=HTTPBasicAuth(self.jira_username, self.jira_api_token)
                                        )
                                        response.raise_for_status()

                                        task_keys[subtask['id']] = subtask_task['key']
                                        created_issues.append(
                                            {'key': subtask_task['key'], 'name': f"{task['name']} - {subtask['name']}"}
                                        )
                                        logger.info(f"  Создана обычная задача вместо подзадачи: {subtask_task['key']}")
                                    except Exception as e2:
                                        logger.error(f"  Не удалось создать даже обычную задачу: {str(e2)}")
                            else:
                                # Если тип подзадачи недоступен, создаем обычную задачу
                                try:
                                    subtask_task_data = {
                                        'fields': {
                                            'project': {'key': self.jira_project},
                                            'summary': f"{task['name']} - {subtask['name']}",
                                            'description': f"Длительность: {subtask.get('duration', 0)} дн.\nДолжность: {subtask.get('position', 'Не указана')}",
                                            'issuetype': {'id': task_type['id']}
                                        }
                                    }

                                    response = requests.post(
                                        f"{self.jira_url}/rest/api/2/issue",
                                        json=subtask_task_data,
                                        auth=HTTPBasicAuth(self.jira_username, self.jira_api_token)
                                    )
                                    response.raise_for_status()

                                    subtask_task = response.json()

                                    # Связываем с родительской задачей
                                    link_data = {
                                        'type': {'name': 'Relates'},
                                        'inwardIssue': {'key': subtask_task['key']},
                                        'outwardIssue': {'key': task_issue['key']}
                                    }

                                    response = requests.post(
                                        f"{self.jira_url}/rest/api/2/issueLink",
                                        json=link_data,
                                        auth=HTTPBasicAuth(self.jira_username, self.jira_api_token)
                                    )
                                    response.raise_for_status()

                                    task_keys[subtask['id']] = subtask_task['key']
                                    created_issues.append(
                                        {'key': subtask_task['key'], 'name': f"{task['name']} - {subtask['name']}"}
                                    )
                                    logger.info(
                                        f"  Создана связанная задача (нет типа подзадачи): {subtask_task['key']}")
                                except Exception as e:
                                    logger.error(f"  Ошибка при создании связанной задачи: {str(e)}")
                    else:
                        logger.info(f"У задачи {task['name']} (ID={task_id}) нет подзадач")
                except Exception as e:
                    logger.error(f"Ошибка при создании групповой задачи {task['name']}: {str(e)}")

            # Шаг 3: Создаем обычные задачи (не групповые и не подзадачи)
            for task in tasks:
                # Пропускаем групповые задачи (они уже созданы)
                if task['id'] in group_tasks:
                    continue

                # Пропускаем подзадачи (они уже созданы)
                parent_id = task.get('parent_id')
                if parent_id and parent_id in group_tasks:
                    continue

                try:
                    # Определяем категорию
                    category_value = None
                    if self.employee_service and task.get('position'):
                        category = self.employee_service.get_category_by_position(task.get('position'))
                        if category:
                            category_value = {"value": category}

                    # Определяем исполнителя
                    task_assignee = self._get_assignee_for_task(task['id'], task.get('employee_id'))

                    # Создаем обычную задачу
                    task_data = {
                        'fields': {
                            'project': {'key': self.jira_project},
                            'summary': task['name'],
                            'description': f"Длительность: {task.get('duration', 0)} дн.\nДолжность: {task.get('position', 'Не указана')}",
                            'issuetype': {'id': task_type['id']},
                            'duedate': task.get('end_date') if task.get('end_date') else None,
                            self.START_DATE_FIELD_ID: task.get('start_date') if task.get('start_date') else None,
                            self.CATEGORY_FIELD_ID: category_value
                        }
                    }

                    # Добавляем исполнителя, если найден
                    if task_assignee:
                        task_data['fields']['assignee'] = task_assignee

                    response = requests.post(
                        f"{self.jira_url}/rest/api/2/issue",
                        json=task_data,
                        auth=HTTPBasicAuth(self.jira_username, self.jira_api_token)
                    )
                    response.raise_for_status()

                    task_issue = response.json()

                    # Связываем с эпиком
                    link_data = {
                        'type': {'name': 'Relates'},
                        'inwardIssue': {'key': task_issue['key']},
                        'outwardIssue': {'key': epic_issue['key']}
                    }

                    response = requests.post(
                        f"{self.jira_url}/rest/api/2/issueLink",
                        json=link_data,
                        auth=HTTPBasicAuth(self.jira_username, self.jira_api_token)
                    )
                    response.raise_for_status()

                    task_keys[task['id']] = task_issue['key']
                    created_issues.append({'key': task_issue['key'], 'name': task['name']})
                    logger.info(f"Создана задача: {task_issue['key']} - {task['name']}")
                except Exception as e:
                    logger.error(f"Ошибка при создании задачи {task['name']}: {str(e)}")

            # Шаг 4: Создаем зависимости между задачами
            logger.info("Создание зависимостей между задачами")
            for task in tasks:
                # Получаем предшественников
                predecessors_str = task.get('predecessors')
                if not predecessors_str or task['id'] not in task_keys:
                    continue

                task_key = task_keys[task['id']]
                task_name = task['name']

                # Парсим предшественников
                predecessors = []
                try:
                    if isinstance(predecessors_str, str):
                        if predecessors_str.strip() == "NULL" or not predecessors_str.strip():
                            continue

                        # Пытаемся распарсить строку
                        if predecessors_str.strip().startswith('[') and predecessors_str.strip().endswith(']'):
                            pred_str = predecessors_str.strip().strip('[]')
                            predecessors = [int(p.strip()) for p in pred_str.split(',') if p.strip()]
                        else:
                            predecessors = [int(predecessors_str.strip())]
                    elif isinstance(predecessors_str, list):
                        predecessors = predecessors_str
                except Exception as e:
                    logger.error(f"Ошибка при парсинге предшественников '{predecessors_str}': {str(e)}")

                # Создаем связи
                for pred_id in predecessors:
                    if pred_id in task_keys:
                        pred_key = task_keys[pred_id]
                        pred_task = next((t for t in tasks if t['id'] == pred_id), None)
                        pred_name = pred_task['name'] if pred_task else f"Задача {pred_id}"

                        try:
                            # Создаем связь "Blocks"
                            link_data = {
                                'type': {'name': 'Blocks'},
                                'inwardIssue': {'key': task_key},
                                'outwardIssue': {'key': pred_key}
                            }

                            response = requests.post(
                                f"{self.jira_url}/rest/api/2/issueLink",
                                json=link_data,
                                auth=HTTPBasicAuth(self.jira_username, self.jira_api_token)
                            )
                            response.raise_for_status()

                            logger.info(f"Создана связь: '{pred_name}' блокирует '{task_name}'")
                        except Exception as e:
                            logger.error(f"Ошибка при создании связи: {str(e)}")
                            try:
                                # Пробуем создать связь "Relates"
                                link_data = {
                                    'type': {'name': 'Relates'},
                                    'inwardIssue': {'key': task_key},
                                    'outwardIssue': {'key': pred_key}
                                }

                                response = requests.post(
                                    f"{self.jira_url}/rest/api/2/issueLink",
                                    json=link_data,
                                    auth=HTTPBasicAuth(self.jira_username, self.jira_api_token)
                                )
                                response.raise_for_status()

                                logger.info(
                                    f"Создана альтернативная связь 'Relates' между '{task_name}' и '{pred_name}'")
                            except Exception as e2:
                                logger.error(f"Не удалось создать даже связь 'Relates': {str(e2)}")

            return {
                'success': True,
                'epic_key': epic_issue['key'],
                'created_issues': created_issues,
                'count': len(created_issues),
                'jira_project_url': f"{self.jira_url}/projects/{self.jira_project}"
            }

        except Exception as e:
            logger.error(f"Критическая ошибка при экспорте в Jira: {str(e)}")

            # Создаем CSV-файл как резервный вариант
            csv_export_file = self.export_to_csv(project, tasks)

            return {
                'success': False,
                'message': f"Ошибка при экспорте в Jira: {str(e)}. Создан CSV-файл для ручного импорта.",
                'csv_export_file': csv_export_file,
                'error': str(e)
            }

    def _get_assignee_for_task(self, task_id: int, employee_id: Optional[int]) -> Optional[Dict[str, str]]:
        """
        Возвращает данные исполнителя для задачи

        Args:
            task_id: ID задачи
            employee_id: ID сотрудника

        Returns:
            Optional[Dict[str, str]]: Словарь с данными исполнителя для Jira или None
        """
        if not employee_id or not self.employee_service:
            return None

        try:
            # Получаем информацию о сотруднике
            employee = self.employee_service.get_employee(employee_id)

            if employee:
                # Для GDPR-совместимого API Jira Cloud используем accountId
                # В реальном приложении здесь должен быть код для поиска пользователя в Jira
                # и сопоставления с сотрудником из вашей системы

                # Пример заглушки:
                employee_map = {
                    "Иванов И.И.": "637f0d8ae7fb394fe88d67e7",  # accountId в Jira
                    "Петров П.П.": "64b0e4fbe7fb394fe88d67e8",
                    "Сидоров С.С.": "64b0e4fbe7fb394fe88d67e9",
                }

                if employee.name in employee_map:
                    return {"accountId": employee_map[employee.name]}

                # В реальной системе здесь должен быть API-запрос к Jira
                # для поиска пользователя по имени

                return None
        except Exception as e:
            logger.error(f"Ошибка при получении исполнителя для задачи {task_id}: {str(e)}")

        return None