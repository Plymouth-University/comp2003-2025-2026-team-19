import logging


class EndpointFilter(logging.Filter):
    def __init__(self, exclude_endpoints: list[str], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.exclude_endpoints = exclude_endpoints

    def filter(self, record: logging.LogRecord) -> bool:
        for endpoint in self.exclude_endpoints:
            if endpoint in record.getMessage():
                return False
        return True
