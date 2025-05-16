from typing import Dict, Any, Callable, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from aiogram.dispatcher.flags import get_flag


class AuthMiddleware(BaseMiddleware):
    """
    Промежуточное ПО для авторизации пользователей
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Инициализирует промежуточное ПО авторизации

        Args:
            config: Конфигурация бота
        """
        self.config = config
        self.allowed_user_ids = config.get('ALLOWED_USER_IDS', [])
        super().__init__()

    async def __call__(
            self,
            handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
            event: Message | CallbackQuery,
            data: Dict[str, Any]
    ) -> Any:
        """
        Проверяет, авторизован ли пользователь для использования бота

        Args:
            handler: Обработчик события
            event: Входящее событие (сообщение или колбэк)
            data: Дополнительные данные

        Returns:
            Результат выполнения обработчика
        """
        # Получаем db_manager из данных диспетчера
        db_manager = event.bot.dispatcher.get("db_manager")

        # Пропускаем проверку, если обработчик помечен флагом skip_auth
        if get_flag(data, "skip_auth"):
            return await handler(event, data)

        # Получаем ID пользователя из события
        user_id = event.from_user.id if hasattr(event, 'from_user') else None

        # Проверяем, авторизован ли пользователь
        if not self.is_authorized(user_id, db_manager):
            # Для сообщений
            if isinstance(event, Message):
                await event.answer(
                    f"Извините, у вас нет доступа к этому боту.\n"
                    f"Ваш ID: {user_id}\n"
                    f"Обратитесь к администратору для получения доступа."
                )
            # Для колбэк-запросов
            elif isinstance(event, CallbackQuery):
                await event.answer("У вас нет доступа к этому боту", show_alert=True)

            # Не продолжаем выполнение обработчика
            return None

        # Добавляем функции проверки в data для доступа в обработчиках
        data["is_authorized"] = lambda user_id: self.is_authorized(user_id, db_manager)
        data["is_admin"] = lambda user_id: self.is_admin(user_id, db_manager)

        # Пользователь авторизован, продолжаем выполнение обработчика
        return await handler(event, data)

    def is_authorized(self, user_id: int, db_manager=None) -> bool:
        """
        Проверяет, авторизован ли пользователь для использования бота

        Args:
            user_id: ID пользователя
            db_manager: Менеджер базы данных

        Returns:
            bool: True, если пользователь авторизован, False в противном случае
        """
        if db_manager:
            # Проверяем пользователя в базе данных
            user = db_manager.get_user(user_id)
            # Администраторы всегда авторизованы, независимо от статуса активности
            if user and user['is_admin'] == 1:
                return True
            # Обычные пользователи должны быть активными
            return user is not None and user['is_active'] == 1
        else:
            # Резервный вариант - проверка по списку разрешенных ID
            return user_id in self.allowed_user_ids

    def is_admin(self, user_id: int, db_manager=None) -> bool:
        """
        Проверяет, является ли пользователь администратором

        Args:
            user_id: ID пользователя
            db_manager: Менеджер базы данных

        Returns:
            bool: True, если пользователь имеет права администратора, иначе False
        """
        if db_manager:
            # Проверяем права администратора в базе данных
            user = db_manager.get_user(user_id)
            return user is not None and user['is_admin'] == 1
        else:
            # Резервный вариант - проверка по первому ID в списке
            return self.allowed_user_ids and user_id == self.allowed_user_ids[0]