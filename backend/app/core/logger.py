import logging
import sys
import os
from app.core.config import get_settings

settings = get_settings()

def setup_logger():
    # Use WORKER_ID or just 'backend' as the logger name
    worker_id = os.getenv("WORKER_ID", settings.worker_id)
    
    logger = logging.getLogger("job_scheduler")
    logger.setLevel(logging.INFO)

    # Prevent adding multiple handlers if setup is called multiple times
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.INFO)
        
        # Format include timestamp, worker_id, level and message
        # This is useful for Kubernetes log aggregation
        formatter = logging.Formatter(
            f'[%(asctime)s] [%(levelname)s] [{worker_id}] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return logger

# Create a singleton instance
logger = setup_logger()
