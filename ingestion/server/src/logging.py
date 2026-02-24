import logging

uvicorn_logger = logging.getLogger("uvicorn")

logger = uvicorn_logger.getChild("web.ingestion")
