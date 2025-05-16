from typing import Dict, Any, Callable, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, Update
from aiogram.dispatcher.flags import get_flag
import logging

logger = logging.getLogger(__name__)


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
            handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
            event: Update,
            data: Dict[str, Any]
    ) -> Any:
        """
        Проверяет, авторизован ли пользователь для использования бота

        Args:
            handler: Обработчик события
            event: Входящее событие (объект Update)
            data: Дополнительные данные

        Returns:
            Результат выполнения обработчика
        """
        try:
            # Получаем db_manager из данных
            db_manager = data.get("db_manager")

            # Пропускаем проверку, если обработчик помечен флагом skip_auth
            if get_flag(data, "skip_auth"):
                return await handler(event, data)

            # Пытаемся получить ID пользователя из события Update
            user_id = None

            # Для сообщений
            if event.message and event.message.from_user:
                user_id = event.message.from_user.id
            # Для callback-запросов
            elif event.callback_query and event.callback_query.from_user:
                user_id = event.callback_query.from_user.id

            logger.debug(f"Проверка авторизации для пользователя: {user_id}")

            # Проверяем, авторизован ли пользователь
            if not self.is_authorized(user_id, db_manager):
                logger.info(f"Пользователь {user_id} не авторизован")

                # Для сообщений
                if event.message:
                    await event.message.answer(
                        f"Извините, у вас нет доступа к этому боту.\n"
                        f"Ваш ID: {user_id}\n"
                        f"Обратитесь к администратору для получения доступа."
                    )
                # Для колбэк-запросов
                elif event.callback_query:
                    await event.callback_query.answer("У вас нет доступа к этому боту", show_alert=True)

                # Не продолжаем выполнение обработчика
                return None

            # Добавляем функции проверки в data для доступа в обработчиках
            data["is_authorized"] = lambda uid: self.is_authorized(uid, db_manager)
            data["is_admin"] = lambda uid: self.is_admin(uid, db_manager)

            # Пользователь авторизован, продолжаем выполнение обработчика
            return await handler(event, data)

        except Exception as e:
            logger.error(f"Ошибка в мидлваре авторизации: {e}")
            # В случае ошибки, пропускаем событие дальше
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
        if user_id is None:
            return False

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
        if user_id is None:
            return False

        if db_manager:
            # Проверяем права администратора в базе данных
            user = db_manager.get_user(user_id)
            return user is not None and user['is_admin'] == 1
        else:
            # Резервный вариант - проверка по первому ID в списке
            return self.allowed_user_ids and user_id == self.allowed_user_ids[0]