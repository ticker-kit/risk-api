"""Logger service - centralized logging configuration"""
import os
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv


load_dotenv()

log_level: str = os.getenv("LOG_LEVEL", "WARNING")
log_file: str = os.getenv("LOG_FILE", "logs/app.log")


def setup_logging():
    """Setup logging configuration with rotation"""
    # Create logs directory if it doesn't exist
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    # Setup rotating file handler
    rotating_handler = RotatingFileHandler(
        log_file,
        maxBytes=1*1024*1024,
        backupCount=10,
        encoding='utf-8'
    )

    # Setup console handler
    console_handler = logging.StreamHandler()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[rotating_handler, console_handler],
        force=True
    )

    return logging.getLogger(__name__)


logger = setup_logging()
