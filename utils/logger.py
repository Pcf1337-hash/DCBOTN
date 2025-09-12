import logging
from logging.handlers import RotatingFileHandler
from utils.constants import LOG_FORMAT, LOG_DATE_FORMAT, LOG_LEVEL

logging.getLogger('discord').setLevel(logging.WARNING)
logging.getLogger('asyncio').setLevel(logging.WARNING)

logging.basicConfig(handlers=[logging.NullHandler()])

class SimpleFormatter(logging.Formatter):
    def format(self, record):
        return f"{self.formatTime(record, self.datefmt)} - {record.levelname} - {record.getMessage()}"

def setup_logger(name='bot', log_file='bot.log', level=LOG_LEVEL):
    logger = logging.getLogger(name)
    
    # Nur einrichten, wenn der Logger noch keine Handler hat
    if not logger.handlers:
        logger.setLevel(level)
        logger.propagate = False
        
        file_handler = RotatingFileHandler(log_file, maxBytes=20*1024*1024, backupCount=2, encoding='utf-8')
        file_handler.setFormatter(SimpleFormatter())
        
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(SimpleFormatter())
        
        logger.addHandler(file_handler)
        logger.addHandler(stream_handler)
        
        # Verhindern, dass Logs an den Root-Logger weitergeleitet werden
        logger.propagate = False
    
    return logger

