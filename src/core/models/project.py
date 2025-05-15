from typing import List, Dict, Any, Optional
from datetime import datetime


class Project:
    """Модель данных проекта"""

    def __init__(self,
                 id: Optional[int] = None,
                 name: str = "",
                 start_date: str = "",
                 status: str = "active",
                 created_at: Optional[str] = None,
                 user_id: Optional[int] = None):
        self.id = id
        self.name = name
        self.start_date = start_date
        self.status = status
        self.created_at = created_at or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.user_id = user_id

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Project':
        """
        Создает объект проекта из словаря

        Args:
            data: Словарь с данными проекта

        Returns:
            Project: Созданный объект проекта
        """
        return cls(
            id=data.get('id'),
            name=data.get('name', ''),
            start_date=data.get('start_date', ''),
            status=data.get('status', 'active'),
            created_at=data.get('created_at'),
            user_id=data.get('user_id')
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        Преобразует объект проекта в словарь

        Returns:
            dict: Словарь с данными проекта
        """
        return {
            'id': self.id,
            'name': self.name,
            'start_date': self.start_date,
            'status': self.status,
            'created_at': self.created_at,
            'user_id': self.user_id
        }