import time
from typing import Optional

import click


def micros_to_seconds(micros: int) -> float:
    return micros / 1_000_000.0


def seconds_to_micros(seconds: float) -> int:
    return int(seconds * 1_000_000)


def parse_lookback(lookback: str) -> int:
    value = lookback.strip().lower()
    if value.endswith("h"):
        return int(value[:-1]) * 3600
    elif value.endswith("m"):
        return int(value[:-1]) * 60
    elif value.endswith("s"):
        return int(value[:-1])
    else:
        try:
            return int(value)
        except ValueError:
            raise click.BadParameter(
                f"Invalid lookback format: '{lookback}'. "
                "Use suffixes: 1h, 30m, 15m, or plain seconds."
            )


def rate_limited(delay_ms: int = 100):
    def decorator(func):
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            time.sleep(delay_ms / 1000.0)
            return result
        return wrapper
    return decorator
