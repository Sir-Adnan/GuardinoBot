import logging
import os

LOG_LEVEL = os.getenv("LOG_LEVEL", "info").upper()


class MarzFormatter(logging.Formatter):
    green = "\x1b[32;1m"
    yellow = "\x1b[1;33m"
    red = "\x1b[1;31m"
    blue = "\x1b[1;34m"
    reset = "\x1b[0m"
    fmt = "%(asctime)s [%(levelname)s]\t[%(name)s:%(filename)s:%(lineno)d]: %(message)s"
    date_fmt = "%Y-%m-%d %H:%M:%S"

    FORMATS = {
        logging.DEBUG: blue + fmt + reset,
        logging.INFO: green + fmt + reset,
        logging.WARNING: yellow + fmt + reset,
        logging.ERROR: red + fmt + reset,
        logging.CRITICAL: red + fmt + reset,
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, datefmt=self.date_fmt)
        return formatter.format(record)


handler = logging.StreamHandler()
handler.setLevel(LOG_LEVEL)
handler.setFormatter(MarzFormatter())


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(LOG_LEVEL)
    logger.addHandler(handler)
    logger.propagate = False
    return logger


logger_db_client = logging.getLogger("db_client")
logger_db_client.setLevel(LOG_LEVEL)
logger_db_client.addHandler(handler)

logger_tortoise = logging.getLogger("tortoise")
logger_tortoise.setLevel(LOG_LEVEL)
logger_tortoise.addHandler(handler)
