class ServiceError(Exception):
    """Raised by the service layer; routes turn it into a JSON error."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status
