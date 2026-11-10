"""Safe, user-facing failures shared by downloads, extraction, and the API."""


class InputError(Exception):
    def __init__(self, code: str, message: str, status: int = 422):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status

    def payload(self):
        return {'error': {'code': self.code, 'message': self.message}}
