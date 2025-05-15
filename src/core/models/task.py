from typing import List, Dict, Any, Optional, Union


class Task:
    """Модель данных задачи"""

    def __init__(self,
                 id: Optional[int] = None,
                 project_id: int = 0,
                 parent_id: Optional[int] = None,
                 name: str = "",
                 duration: int = 0,
                 is_group: bool = False,
                 parallel: bool = False,
                 start_date: Optional[str] = None,
                 end_date: Optional[str] = None,
                 employee_id: Optional[int] = None,
                 position: Optional[str] = None,
                 predecessors: Optional[Union[List[int], str]] = None,
                 working_duration: Optional[int] = None):
        self.id = id
        self.project_id = project_id
        self.parent_id = parent_id
        self.name = name
        self.duration = duration
        self.is_group = is_group
        self.parallel = parallel
        self.start_date = start_date
        self.end_date = end_date
        self.employee_id = employee_id
        self.position = position
        self.predecessors = predecessors or []
        self.working_duration = working_duration or duration

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Task':
        """
        Создает объект задачи из словаря

        Args:
            data: Словарь с данными задачи

        Returns:
            Task: Созданный объект задачи
        """
        # Обработка предшественников
        predecessors = data.get('predecessors', [])
        if isinstance(predecessors, str):
            try:
                import json
                predecessors = json.loads(predecessors)
            except:
                # Если не JSON, предполагаем пустой список
                predecessors = []

        return cls(
            id=data.get('id'),
            project_id=data.get('project_id', 0),
            parent_id=data.get('parent_id'),
            name=data.get('name', ''),
            duration=data.get('duration', 0),
            is_group=bool(data.get('is_group', False)),
            parallel=bool(data.get('parallel', False)),
            start_date=data.get('start_date'),
            end_date=data.get('end_date'),
            employee_id=data.get('employee_id'),
            position=data.get('position'),
            predecessors=predecessors,
            working_duration=data.get('working_duration')
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        Преобразует объект задачи в словарь

        Returns:
            dict: Словарь с данными задачи
        """
        import json

        # Сериализуем предшественников, если они не строка
        predecessors = self.predecessors
        if not isinstance(predecessors, str) and predecessors:
            predecessors = json.dumps(predecessors)

        return {
            'id': self.id,
            'project_id': self.project_id,
            'parent_id': self.parent_id,
            'name': self.name,
            'duration': self.duration,
            'is_group': self.is_group,
            'parallel': self.parallel,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'employee_id': self.employee_id,
            'position': self.position,
            'predecessors': predecessors,
            'working_duration': self.working_duration
        }