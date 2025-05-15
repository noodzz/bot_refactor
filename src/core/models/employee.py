from typing import List, Dict, Any, Optional, Union


class Employee:
    """Модель данных сотрудника"""

    def __init__(self,
                 id: Optional[int] = None,
                 name: str = "",
                 position: str = "",
                 days_off: Union[List[int], str] = None):
        self.id = id
        self.name = name
        self.position = position

        # Обрабатываем days_off
        if days_off is None:
            self.days_off = []
        elif isinstance(days_off, str):
            try:
                import json
                self.days_off = json.loads(days_off)
            except:
                self.days_off = []
        else:
            self.days_off = days_off

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Employee':
        """
        Создает объект сотрудника из словаря

        Args:
            data: Словарь с данными сотрудника

        Returns:
            Employee: Созданный объект сотрудника
        """
        return cls(
            id=data.get('id'),
            name=data.get('name', ''),
            position=data.get('position', ''),
            days_off=data.get('days_off', [])
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        Преобразует объект сотрудника в словарь

        Returns:
            dict: Словарь с данными сотрудника
        """
        import json

        # Сериализуем days_off, если это не строка
        days_off = self.days_off
        if not isinstance(days_off, str):
            days_off = json.dumps(days_off)

        return {
            'id': self.id,
            'name': self.name,
            'position': self.position,
            'days_off': days_off
        }

    def is_available(self, date_str: str) -> bool:
        """
        Проверяет, доступен ли сотрудник в указанную дату

        Args:
            date_str: Дата в формате YYYY-MM-DD

        Returns:
            bool: True, если сотрудник доступен, иначе False
        """
        from datetime import datetime

        # Получаем день недели (0 - понедельник, 6 - воскресенье)
        date = datetime.strptime(date_str, '%Y-%m-%d')
        weekday = date.weekday() + 1  # +1 чтобы привести к формату 1=пн, 7=вс

        # Проверяем, не выходной ли это день
        return weekday not in self.days_off