class ServiceError(Exception):
    """Ошибка бизнес-логики: отдаётся клиенту как {"detail": message} с кодом status_code."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
