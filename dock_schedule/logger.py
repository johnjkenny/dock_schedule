import logging
from os import makedirs
from os.path import join
from time import gmtime
from pathlib import Path


def _log_mapping(level: str) -> int:
    """Maps the log level to the logging level. Will default to INFO if the level is not found.

    Args:
        level (str): The log level

    Returns:
        int: The logging level
    """
    level = level.upper()
    level_map = {'DEBUG': logging.DEBUG,
                 'INFO': logging.INFO,
                 'WARNING': logging.WARNING,
                 'ERROR': logging.ERROR,
                 'CRITICAL': logging.CRITICAL}
    return level_map.get(level, logging.INFO)


def _create_log_dir(dir_name: str) -> bool:
    """Create the log directory if it does not exist.

    Args:
        dir_name (str): The directory name to create

    Returns:
        bool: True if the directory was created, False otherwise
    """
    try:
        makedirs(dir_name)
        return True
    except Exception as error:
        print(f'Failed to create log directory: {error}')
    return False


def _set_stream_handler(logger: logging.Logger, level: int, formatter: logging.Formatter) -> bool:
    """Set the stream handler for the logger.

    Args:
        logger (logging.Logger): the logger object to set the stream handler for
        level (int): the logging level
        formatter (logging.Formatter): the logging formatter

    Returns:
        bool: True if the stream handler was set, False otherwise
    """
    try:
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(level)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)
        return True
    except Exception as error:
        print(f'Failed to set stream handler: {error}')
    return False


def _set_file_handler(logger: logging.Logger, name: str, dir_name: str, level: int,
                      formatter: logging.Formatter) -> bool:
    """Set the file handler for the logger.

    Args:
        logger (logging.Logger): logging object
        name (str): name of the log file
        dir_name (str): log directory name
        level (int): the logging level
        formatter (logging.Formatter): the logging formatter

    Returns:
        bool: True if the file handler was set, False otherwise
    """
    try:
        if not dir_name:
            dir_name = f'{Path(__file__).parent}/logs'
        else:
            dir_name = Path(dir_name)
        log_file = join(dir_name, f'{name}.log')
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        return True
    except FileNotFoundError as error:
        if _create_log_dir(dir_name):
            return _set_file_handler(logger, name, dir_name, level, formatter)
        print(f'Failed to create log file: {error}')
    except Exception as error:
        print(f'Failed to create log file: {error}')
    return False


def get_logger(name: str, level: str = 'info', dir_name: str = ''):
    """Get the logger or create it if it does not exist.

    Args:
        name (str): The name of the logger
        level (str, optional): logging level. Defaults to 'info'.
        dir_name (str, optional): directory to store logs. Defaults to ''.

    Returns:
        logging.Logger: The logger object
    """
    logger = logging.getLogger(name)
    level = _log_mapping(level)
    logger.setLevel(level)
    if not logger.hasHandlers():
        formatter = logging.Formatter('[%(asctime)s][%(levelname)s][%(module)s,%(lineno)d]: %(message)s')
        formatter.converter = gmtime
        _set_stream_handler(logger, level, formatter)
        _set_file_handler(logger, name, dir_name, level, formatter)
    return logger
