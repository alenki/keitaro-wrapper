class KeitaroError(Exception):
    """Talking to Keitaro failed."""

    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


class KeitaroUnavailable(KeitaroError):
    """Timeout, connection problem or a 5xx answer."""


class KeitaroAuthError(KeitaroError):
    """Keitaro did not accept the API key."""


class KeitaroNotFound(KeitaroError):
    """The campaign, stream or offer does not exist in Keitaro."""


class KeitaroRejected(KeitaroError):
    """Keitaro refused the request (4xx), usually a validation error with a message."""
