# Эти переменные будут импортированы и установлены при запуске бота
is_authorized = None
is_admin = None

def setup_auth_functions(auth_middleware):
    """Настраивает функции авторизации"""
    global is_authorized, is_admin
    is_authorized = auth_middleware.is_authorized
    is_admin = auth_middleware.is_admin