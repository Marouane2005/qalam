class AppError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status: int,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.headers = headers or {}


class IngestError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__("ingest_failed", message, 422)


class ModelOutputError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__("model_output", message, 502)
