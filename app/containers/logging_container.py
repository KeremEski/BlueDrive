import logging
from pathlib import Path

class LoggingContainer:
    _loggers = {}

    @staticmethod
    def get_logger(name: str, log_level=logging.DEBUG):
        if name in LoggingContainer._loggers:
            return LoggingContainer._loggers[name]

        logger = logging.getLogger(name)
        logger.setLevel(log_level)
        logger.propagate = False  # Üst loglara yollama

        # Log klasörü ve dosyası
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / f"{name}.log"

        # Dosya handler (üzerine yazar)
        file_handler = logging.FileHandler(log_file, mode='w')  # <-- 'w' = overwrite
        file_handler.setLevel(log_level)
        formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s")
        file_handler.setFormatter(formatter)

        logger.addHandler(file_handler)

        LoggingContainer._loggers[name] = logger
        return logger
