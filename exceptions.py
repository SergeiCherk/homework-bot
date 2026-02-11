"""Пользовательские исключения для бота-ассистента."""


class APIError(Exception):
    """Исключение при ошибке запроса к API."""

    pass


class ResponseError(Exception):
    """Исключение при некорректном ответе API."""

    pass


class StatusError(Exception):
    """Исключение при неожиданном статусе домашней работы."""

    pass


class CurrentDateError(Exception):
    """Исключение при проблемах с ключом current_date."""

    pass
