"""Модуль для централизованного доступа к сервисам и функциям"""

# Глобальные переменные для сервисов и функций
db_manager = None
project_service = None
task_service = None
employee_service = None
schedule_service = None
export_service = None
gantt_chart = None
workload_chart = None
is_authorized = None
is_admin = None


def init_services(dispatcher):
    """Инициализация глобальных переменных из контекста диспетчера"""
    global db_manager, project_service, task_service, employee_service
    global schedule_service, export_service, gantt_chart, workload_chart
    global is_authorized, is_admin

    db_manager = dispatcher["db_manager"]
    project_service = dispatcher["project_service"]
    task_service = dispatcher["task_service"]
    employee_service = dispatcher["employee_service"]
    schedule_service = dispatcher["schedule_service"]
    export_service = dispatcher["export_service"]
    gantt_chart = dispatcher["gantt_chart"]
    workload_chart = dispatcher["workload_chart"]
    is_authorized = dispatcher["is_authorized"]
    is_admin = dispatcher["is_admin"]


def get_service(name):
    """Получить сервис по имени"""
    global db_manager, project_service, task_service, employee_service
    global schedule_service, export_service, gantt_chart, workload_chart

    services = {
        "db_manager": db_manager,
        "project_service": project_service,
        "task_service": task_service,
        "employee_service": employee_service,
        "schedule_service": schedule_service,
        "export_service": export_service,
        "gantt_chart": gantt_chart,
        "workload_chart": workload_chart
    }

    return services.get(name)