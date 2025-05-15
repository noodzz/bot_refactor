from typing import List, Optional, Dict, Any
import json
from src.core.models.employee import Employee


class EmployeeRepository:
    """Репозиторий для работы с сотрудниками в базе данных"""

    def __init__(self, db_manager):
        """
        Инициализирует репозиторий сотрудников

        Args:
            db_manager: Менеджер базы данных
        """
        self.db = db_manager

    def create_employee(self, employee: Employee) -> int:
        """
        Создает нового сотрудника в базе данных

        Args:
            employee: Объект сотрудника

        Returns:
            int: ID созданного сотрудника
        """
        self.db.connect()

        # Сериализуем days_off, если это список
        days_off = employee.days_off
        if not isinstance(days_off, str):
            days_off = json.dumps(days_off)

        query = "INSERT INTO employees (id, name, position, days_off) VALUES (?, ?, ?, ?)"
        params = (employee.id, employee.name, employee.position, days_off)

        try:
            self.db.cursor.execute(query, params)
            self.db.connection.commit()
            return self.db.cursor.lastrowid if employee.id is None else employee.id
        finally:
            self.db.close()

    def get_employee(self, employee_id: int) -> Optional[Employee]:
        """
        Возвращает информацию о сотруднике

        Args:
            employee_id: ID сотрудника

        Returns:
            Optional[Employee]: Объект сотрудника или None, если сотрудник не найден
        """
        result = self.db.execute("SELECT * FROM employees WHERE id = ?", (employee_id,))
        if result:
            return Employee.from_dict(dict(result[0]))
        return None

    def get_employees(self) -> List[Employee]:
        """
        Возвращает список всех сотрудников

        Returns:
            List[Employee]: Список сотрудников
        """
        result = self.db.execute("SELECT * FROM employees ORDER BY position, name")
        return [Employee.from_dict(dict(row)) for row in result]

    def get_employees_by_position(self, position: str) -> List[Employee]:
        """
        Возвращает список сотрудников определенной должности

        Args:
            position: Должность

        Returns:
            List[Employee]: Список сотрудников
        """
        result = self.db.execute(
            "SELECT * FROM employees WHERE position = ? ORDER BY name",
            (position,)
        )

        return [Employee.from_dict(dict(row)) for row in result]

    def update_employee(self, employee: Employee) -> bool:
        """
        Обновляет информацию о сотруднике

        Args:
            employee: Объект сотрудника с обновленными данными

        Returns:
            bool: True, если обновление успешно, иначе False
        """
        if employee.id is None:
            return False

        # Сериализуем days_off, если это список
        days_off = employee.days_off
        if not isinstance(days_off, str):
            days_off = json.dumps(days_off)

        try:
            self.db.execute(
                "UPDATE employees SET name = ?, position = ?, days_off = ? WHERE id = ?",
                (employee.name, employee.position, days_off, employee.id)
            )
            return True
        except Exception:
            return False

    def delete_employee(self, employee_id: int) -> bool:
        """
        Удаляет сотрудника из базы данных

        Args:
            employee_id: ID сотрудника

        Returns:
            bool: True, если удаление успешно, иначе False
        """
        try:
            # Сначала отменяем все назначения этого сотрудника на задачи
            self.db.execute("UPDATE tasks SET employee_id = NULL WHERE employee_id = ?", (employee_id,))

            # Затем удаляем сотрудника
            self.db.execute("DELETE FROM employees WHERE id = ?", (employee_id,))
            return True
        except Exception:
            return False