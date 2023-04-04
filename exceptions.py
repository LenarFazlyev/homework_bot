class NotTokenOrIdProvided(Exception):
    """Исключение для ситуации когда один из Токенов/Id отсутствует."""

    pass


class NotAvailableEndpoint(Exception):
    """Недоступность эндпоинта."""

    pass


class UnexpectedErrorWithEndpoint(Exception):
    """Неожиданная ошибка эндпоинта."""

    pass


class NoOrEmptyStatus(Exception):
    """Пустой статус домашней работы."""

    pass

class EmptyAnswerFromAPI(Exception):
    "Пустой ответ от АПИ"

    pass
