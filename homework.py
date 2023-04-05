import logging
import os
import sys
import time
from http import HTTPStatus
from logging.handlers import RotatingFileHandler

import requests
import telegram
from dotenv import load_dotenv

from exceptions import (UnexpectedErrorWithEndpoint,
                        EmptyAnswerFromAPI)

load_dotenv()

PRACTICUM_TOKEN = os.getenv('YA_TOKEN')
TELEGRAM_TOKEN = os.getenv('TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

loger = logging.getLogger(__name__)
loger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(stream=sys.stdout)
loger.addHandler(handler)
formatter = logging.Formatter(
    '%(asctime)s %(funcName)s %(lineno)s [%(levelname)s] %(message)s'
)
handler.setFormatter(formatter)
handler_file = RotatingFileHandler(
    __file__ + '.log', maxBytes=5000000,
    backupCount=5, encoding='utf-8'
)
loger.addHandler(handler_file)
handler_file.setFormatter(formatter)


def check_tokens():
    """Проверяет есть ли токены и ай-ди чата."""
    token_items = (  # знакомый прием :)
        (PRACTICUM_TOKEN, 'PRACTICUM_TOKEN'),
        (TELEGRAM_TOKEN, 'TELEGRAM_TOKEN'),
        (TELEGRAM_CHAT_ID, 'TELEGRAM_CHAT_ID'),
    )
    all_tokens_exist = True
    for token, name in token_items:
        if not token:
            loger.critical(
                f'Отсутствует обязательная переменная окружения: {name}'
            )
            all_tokens_exist = False
    if not all_tokens_exist:
        raise SystemExit(
            'Отсутствует одна из обязательных переменных окружения'
        )


def send_message(bot, message):
    """Отправляет собщение в чат."""
    loger.debug(f'Попытка отправить сообщение {message}')
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        loger.debug(f'Сообщение: {message} - отправлено в чат успешно')
        return True
    except telegram.error.TelegramError as error:
        loger.error(f'Сбой при отправке сообщения. Код ошибки:{error}')
        return False


def get_api_answer(timestamp):
    """Отправка запроса к единственному эндпоинту API-сервиса."""
    payload = {'from_date': timestamp}
    parameters_dict = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': payload,
    }
    loger.debug(
        (
            'Запуск запроса к url:{url}'
            ' c параметрами headers:{headers}'
            ' и params:{params}'
        ).format(**parameters_dict)
    )
    try:
        response = requests.get(**parameters_dict)
    except Exception as error:
        raise ConnectionError(
            (
                'Запрос к url:{url}'
                ' c параметрами headers:{headers}'
                ' и params:{params}'
                ' привел к ошибке: {error}'
            ).format(error=error, **parameters_dict)
        )
    if response.status_code != HTTPStatus.OK:
        error = (
            (
                'Недоступен эндпоинт {uls}'
                ' c параметрами headers:{headers}'
                ' и params:{params}.'
                'Код ответа API:', response.status_code,
                'Причина:', response.reason,
                'Текст:', response.text
            )
        )
        raise UnexpectedErrorWithEndpoint(error)
    return response.json()


def check_response(response):
    """Проверяет ответ АПИ на соответствие документации."""
    loger.debug('Начало проверки ответа АПИ')
    if not isinstance(response, dict):
        raise TypeError('Ответ на запрос не является словарем')
    if 'homeworks' not in response:
        raise EmptyAnswerFromAPI('Нет ключа: homeworks')
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise TypeError('Homeworks не является списком')
    return homeworks


def parse_status(homework):
    """Извлечение статуса работы.

    Извлекает из информации о конкретной домашней
    работе статус этой работы
    """
    if 'homework_name' not in homework:
        raise KeyError(
            'Пустое имя работы "homework_name".'
        )
    if homework.get('status') not in HOMEWORK_VERDICTS:
        raise ValueError(
            'У домашней работы некорректный статус.'
        )
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    # timestamp = int(time.time())
    timestamp = 0
    current_report = {'name': '', 'message': ''}
    prev_report = {'name': '', 'message': ''}
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if homeworks:
                last_work = homeworks[0]
                current_message = parse_status(last_work)
                current_report['name'] = last_work['homework_name']
                current_report['message'] = current_message
            else:
                current_report['message'] = (
                    'Новых статусов нет'
                )
            if current_report != prev_report:
                if send_message(bot, current_report['message']):
                    prev_report = current_report.copy()
                    timestamp = response.get('current_date', timestamp)
            else:
                loger.debug('Новых статусов нет')
        except EmptyAnswerFromAPI as error:
            loger.error(
                f'Пустой ответ от АПИ. Код ошибки:{error}',
                exc_info=True
            )
        except Exception as error:
            message = f'Сбой в работе программы. Код ошибки:{error}'
            loger.error(message, exc_info=True)
            current_report['message'] = message
            if current_report != prev_report:
                send_message(bot, message)
                prev_report = current_report.copy()
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
