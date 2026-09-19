class AppError(Exception):
    pass

class NotFoundError(AppError):
    pass

class PermissionDeniedError(AppError):
    pass

class ContentValidationError(AppError):

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__('\n'.join(errors))
