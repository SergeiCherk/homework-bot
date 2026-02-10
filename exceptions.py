"""Пользовательские исключения для бота-ассистента."""


class APIError(Exception):
    """Исключение при ошибке запроса к API."""

    pass


class ResponseError(Exception):
    """Исключение при некорректном ответе API."""

    pass
