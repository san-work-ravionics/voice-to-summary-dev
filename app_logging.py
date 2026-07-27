"""Shared logging setup for webapp/server.py — writes every logger to both
stdout (so `docker compose logs` keeps working) and a size-capped rotating
file under LOG_DIR, so log history survives a container restart/recreate
the same way the data volumes do, instead of living only in Docker's
container-scoped log store (gone once the container is `rm`'d).
"""
import logging
import logging.handlers
import os

LOG_DIR = os.environ.get("LOG_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs"))


def get_logger(name):
    logger = logging.getLogger(name)
    if logger.handlers:  # idempotent — safe to call more than once per name
        return logger
    logger.setLevel(logging.INFO)

    os.makedirs(LOG_DIR, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")

    file_handler = logging.handlers.RotatingFileHandler(
        os.path.join(LOG_DIR, f"{name}.log"), maxBytes=5_000_000, backupCount=3,
    )
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(fmt)
    logger.addHandler(stream_handler)

    return logger
