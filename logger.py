from datetime import datetime

_LOG_BUFFER: list[str] = []


def log(message: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _LOG_BUFFER.append(f"[{timestamp}] {message}")


def get_log() -> str:
    return "\n".join(_LOG_BUFFER)


def clear_log() -> None:
    _LOG_BUFFER.clear()
