"""Бот-ассистент для проверки статуса домашних работ в Практикуме."""

import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telebot
from dotenv import load_dotenv

from exceptions import APIError, ResponseError, StatusError, CurrentDateError

# Загрузка переменных окружения из .env файла
load_dotenv()

# Инициализация логгера
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)

# Константы
PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600  # 10 минут в секундах
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """
    Проверяет доступность переменных окружения.

    Проверяет наличие всех необходимых токенов и ID чата.
    Если отсутствует хотя бы одна переменная, возвращает False.

    Returns:
        bool: True если все переменные присутствуют, False в противном случае.
    """
    required_tokens = ('PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID')
    missing_tokens = [
        token_name for token_name in required_tokens
        if not globals().get(token_name)
    ]

    if missing_tokens:
        logger.critical(
            f"Отсутствуют обязательные переменные окружения: "
            f"{', '.join(missing_tokens)}"
        )
        return False

    return True


def send_message(bot, message):
    """
    Отправляет сообщение в Telegram-чат.

    Args:
        bot: Экземпляр класса TeleBot.
        message (str): Текст сообщения для отправки.

    Raises:
        Exception: При ошибке отправки сообщения.
    """
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(f'Бот отправил сообщение "{message}"')
    except Exception as error:
        logger.error(f'Сбой при отправке сообщения в Telegram: {error}')
        raise


def get_api_answer(timestamp):
    """
    Делает запрос к API сервиса Практикум Домашка.

    Args:
        timestamp (int): Временная метка для запроса.

    Returns:
        dict: Ответ API в формате Python dict.

    Raises:
        APIError: При проблемах с доступностью эндпоинта.
    """
    params = {'from_date': timestamp}

    try:
        logger.debug(f'Начало запроса к API с параметрами: {params}')
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)

        if response.status_code != HTTPStatus.OK:
            error_msg = (
                f'Эндпоинт {ENDPOINT} недоступен. '
                f'Код ответа API: {response.status_code}'
            )
            logger.error(error_msg)
            raise APIError(error_msg)

        return response.json()

    except requests.RequestException as error:
        error_msg = f'Ошибка при запросе к API: {error}'
        logger.error(error_msg)
        raise APIError(error_msg)


def check_response(response):
    """
    Проверяет ответ API на соответствие документации.

    Args:
        response (dict): Ответ API в формате Python dict.

    Returns:
        list: Список домашних работ.

    Raises:
        ResponseError: При несоответствии ответа ожидаемой структуре.
        TypeError: При некорректном типе данных в ответе.
        CurrentDateError: При проблемах с ключом current_date.
    """
    if not isinstance(response, dict):
        raise TypeError('Ответ API не является словарём')

    if 'homeworks' not in response:
        raise ResponseError('Отсутствует ключ "homeworks" в ответе API')

    if 'current_date' not in response:
        raise CurrentDateError('Отсутствует ключ "current_date" в ответе API')

    if not isinstance(response['current_date'], int):
        raise CurrentDateError('Значение "current_date" не является числом')

    homeworks = response['homeworks']

    if not isinstance(homeworks, list):
        raise TypeError(
            'Данные под ключом "homeworks" не являются списком'
        )

    return homeworks


def parse_status(homework):
    """
    Извлекает статус домашней работы.

    Args:
        homework (dict): Элемент из списка домашних работ.

    Returns:
        str: Строка для отправки в Telegram с вердиктом о работе.

    Raises:
        KeyError: При отсутствии ожидаемых ключей в данных.
        StatusError: При неожиданном статусе домашней работы.
    """
    if 'homework_name' not in homework:
        raise KeyError('Отсутствует ключ "homework_name" в ответе API')

    if 'status' not in homework:
        raise KeyError('Отсутствует ключ "status" в ответе API')

    homework_name = homework['homework_name']
    status = homework['status']

    if status not in HOMEWORK_VERDICTS:
        raise StatusError(f'Неожиданный статус домашней работы: {status}')

    verdict = HOMEWORK_VERDICTS[status]

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    # Проверка наличия токенов
    if not check_tokens():
        logger.critical('Программа принудительно остановлена.')
        sys.exit(1)

    # Инициализация бота
    bot = telebot.TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    # Переменная для хранения последней ошибки
    last_error_message = ''

    logger.info('Бот запущен')

    while True:
        try:
            # Получение ответа от API
            response = get_api_answer(timestamp)

            # Проверка ответа
            homeworks = check_response(response)

            # Обработка домашних работ
            if homeworks:
                for homework in homeworks:
                    message = parse_status(homework)
                    send_message(bot, message)

                # Обновление временной метки
                timestamp = response.get('current_date', timestamp)
            else:
                logger.debug('Отсутствие в ответе новых статусов')

            # Сброс последней ошибки при успешном выполнении
            last_error_message = ''

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)

            # Отправка сообщения об ошибке, если это новая ошибка
            if message != last_error_message:
                last_error_message = message
                send_message(bot, message)

        finally:
            # Ожидание перед следующей проверкой
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
