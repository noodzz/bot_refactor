import csv
import io
from typing import List, Dict, Any, Optional

def parse_csv(csv_content: str) -> List[Dict[str, Any]]:
    """
    Разбирает содержимое CSV-файла с информацией о проекте

    Args:
        csv_content (str): Содержимое CSV-файла

    Returns:
        list: Список словарей с данными о задачах
    """
    tasks = []

    csv_file = io.StringIO(csv_content)
    reader = csv.DictReader(csv_file)

    # Словарь для отслеживания групповых задач
    group_tasks = {}

    for row in reader:
        task = {
            "name": row.get("Задача", "").strip(),
            "duration": int(row.get("Длительность", 0)),
            "is_group": row.get("Тип", "").lower().strip() == "групповая",
            "position": row.get("Должность", "").strip(),
        }

        # Обрабатываем предшественников
        predecessors_str = row.get("Предшественники", "").strip()
        if predecessors_str:
            task["predecessors"] = [pred.strip() for pred in predecessors_str.split(',')]
        else:
            task["predecessors"] = []

        # Обрабатываем групповые задачи
        parent_task = row.get("Родительская задача", "").strip()
        if parent_task:
            # Это подзадача
            if parent_task not in group_tasks:
                # Создаем родительскую задачу, если ее еще нет
                group_task = {
                    "name": parent_task,
                    "duration": 0,  # Будет рассчитано позже
                    "is_group": True,
                    "predecessors": [],
                    "subtasks": []
                }
                group_tasks[parent_task] = group_task
                tasks.append(group_task)

            # Добавляем подзадачу
            subtask = {
                "name": task["name"],
                "duration": task["duration"],
                "position": task["position"],
                "parallel": row.get("Параллельная", "").lower().strip() in ("да", "yes", "true", "1")
            }

            group_tasks[parent_task]["subtasks"].append(subtask)

            # Обновляем длительность групповой задачи
            if subtask["parallel"]:
                # При параллельном выполнении берем максимальную длительность
                group_tasks[parent_task]["duration"] = max(
                    group_tasks[parent_task]["duration"],
                    subtask["duration"]
                )
            else:
                # При последовательном выполнении суммируем длительности
                group_tasks[parent_task]["duration"] += subtask["duration"]
        else:
            # Это обычная задача или новая групповая задача
            if task["is_group"]:
                task["subtasks"] = []
                group_tasks[task["name"]] = task

            tasks.append(task)

    return tasks