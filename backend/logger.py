import logging
import sys
import contextvars
import uuid

_request_id: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


class _RequestIDFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id.get()  # type: ignore[attr-defined]
        return True


def setup_logging() -> None:
    fmt = logging.Formatter(
        '{"time":"%(asctime)s","level":"%(levelname)s","name":"%(name)s",'
        '"request_id":"%(request_id)s","message":"%(message)s"}',
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(fmt)
    handler.addFilter(_RequestIDFilter())

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers = [handler]

    # Quiet noisy third-party loggers
    for name in ("httpx", "httpcore", "uvicorn.access", "litellm"):
        logging.getLogger(name).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def set_request_id(rid: str) -> contextvars.Token:
    return _request_id.set(rid)


def reset_request_id(token: contextvars.Token) -> None:
    _request_id.reset(token)


def new_request_id() -> str:
    return uuid.uuid4().hex[:8]
