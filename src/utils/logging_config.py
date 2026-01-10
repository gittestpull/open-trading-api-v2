# -*- coding: utf-8 -*-
import logging
import os
from datetime import datetime
from typing import Optional


def setup_logging(
    name: str = "trading",
    log_dir: str = "logs",
    console_level: int = logging.INFO,
    file_level: int = logging.DEBUG
) -> logging.Logger:
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    log_filename = os.path.join(
        log_dir, 
        f"{name}_{datetime.now().strftime('%Y%m%d')}.log"
    )
    
    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    console_handler.setFormatter(
        logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
    )
    
    file_handler = logging.FileHandler(log_filename, encoding='utf-8')
    file_handler.setLevel(file_level)
    file_handler.setFormatter(
        logging.Formatter('%(asctime)s [%(levelname)s] %(name)s - %(message)s')
    )
    
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    return logging.getLogger(name)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
