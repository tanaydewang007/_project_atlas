class AtlasError(Exception):
    pass


class ClientNotFound(AtlasError):
    pass


class SqlRejected(AtlasError):
    pass


class LLMUnavailable(AtlasError):
    pass


class AgentTimeout(AtlasError):
    pass


class AdminError(AtlasError):
    def __init__(self, message: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
