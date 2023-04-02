from http import HTTPStatus
import logging
import sys
import time
import requests
import telegram

import os

from dotenv import load_dotenv

from exceptions import (
    NotAvailableEndpoint,
    UnexpectedErrorWithEndpoint,
    NoOrEmptyStatus,

)

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

loger = logging.getLogger('__name__')
loger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(stream=sys.stdout)
loger.addHandler(handler)
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
handler.setFormatter(formatter)


def check_tokens():
    """Проверяет есть ли токены и ай-ди чата."""
    token_items = (  # знакомый прием :)
        (PRACTICUM_TOKEN, 'PRACTICUM_TOKEN'),
        (TELEGRAM_TOKEN, 'TELEGRAM_TOKEN'),
        (TELEGRAM_CHAT_ID, 'TELEGRAM_CHAT_ID'),
    )
    for token, name in token_items:
        if not token:
            loger.critical(
                f'Отсутствует обязательная переменная окружения: {name}'
            )
            raise SystemExit()


def send_message(bot, message):
    """Отправляет собщение в чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        loger.debug('Сообщение отправлено в чат успешно')
    except Exception as error:
        loger.error(f'Сбой при отправке сообщения. Код ошибки:{error}')


def get_api_answer(timestamp):
    """Отправка запроса к единственному эндпоинту API-сервиса."""
    payload = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
    except Exception:
        raise NotAvailableEndpoint('Запрос не удалось обработать')
    else:
        if response.status_code != HTTPStatus.OK:
            error = (
                f'Эндпоинт {ENDPOINT} недоступен. Код ответа API:',
                response.status_code
            )
            raise UnexpectedErrorWithEndpoint(error)
    return response.json()


def check_response(response):
    """Проверяет ответ АПИ на соответствие документации."""
    if type(response) != dict:
        raise TypeError('Ответ на запрос не является словарем')
    if 'homeworks' not in response:
        raise KeyError('Нет ключа: homeworks')
    if type(response['homeworks']) != list:
        raise TypeError('Homeworks не является списком')


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
        raise NoOrEmptyStatus(
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
    timestamp = int(time.time())

    error_message_to_bot = ''
    current_message = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            check_response(response)
            if response['homeworks']:
                last_work = response.get('homeworks')[0]
                current_message = parse_status(last_work)
                send_message(bot, current_message)
            else:
                loger.debug('Статус проверки работы не изменился')
            timestamp = response.get('current_date', timestamp)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if message != error_message_to_bot:
                send_message(bot, message)
                error_message_to_bot = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
