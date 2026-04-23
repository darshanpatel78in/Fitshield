import os
import logging
from datetime import datetime

# Base directory for logs
LOG_BASE_DIR = r'C:\Users\asus\logs'


def create_log_files(restro_id):
    """
    Create empty log files (success, error, calculation) for a restaurant folder.

    Args:
        restaurant_id (str): The unique restaurant ID.
    """
    log_types = ["success", "error", "calculation"]
    for log_type in log_types:
        log_file_path = get_dynamic_log_path(restro_id, log_type)
        try:
            if not os.path.exists(log_file_path):
                # Ensure the file exists by creating it
                with open(log_file_path, "w") as file:
                    file.write("")  # Create an empty file
        except Exception as e:
            print(f"Error creating log file {log_file_path}: {e}")


def get_dynamic_log_path(restro_id, log_type):
    """
    Generate the dynamic path for logs based on year, month, date, and restaurant ID.
    This method will be used to generate dynamic log paths.

    Args:
        restaurant_id (str): The unique restaurant ID.
        log_type (str): The type of log (e.g., 'success', 'error').

    Returns:
        str: The full path to the log file.
    """
    today = datetime.now()
    year_folder = today.strftime("%Y")
    month_folder = today.strftime("%m")
    date_folder = today.strftime("%d")

    # Construct the dynamic log directory
    log_dir = os.path.join(LOG_BASE_DIR, year_folder, month_folder, date_folder, restro_id)
    os.makedirs(log_dir, exist_ok=True)  # Ensure all directories exist

    return os.path.join(log_dir, f"{log_type}.log")


def get_logger(restro_id, log_type):
    """
    Get a logger for a specific restaurant and log type.

    Args:
        restaurant_id (str): The restaurant ID for grouping logs.
        log_type (str): The type of log (e.g., 'success', 'error').

    Returns:
        logging.Logger: A configured logger.
    """
    logger_name = f"logger_{restro_id}_{log_type}"
    logger = logging.getLogger(logger_name)

    if not logger.hasHandlers():  # Avoid duplicate handlers
        logger.setLevel(logging.DEBUG)

        # File handler
        log_file_path = get_dynamic_log_path(restro_id, log_type)
        file_handler = logging.FileHandler(log_file_path)
        file_handler.setLevel(logging.DEBUG)

        # Formatter
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        file_handler.setFormatter(formatter)

        logger.addHandler(file_handler)

    return logger

