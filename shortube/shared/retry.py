from __future__ import annotations

import functools
import logging
import time
from typing import Callable, Type

logger = logging.getLogger(__name__)


def retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    exceptions: tuple[Type[Exception], ...] = (Exception,),
) -> Callable:
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception: Exception | None = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_attempts:
                        raise
                    delay = min(
                        base_delay * (exponential_base ** (attempt - 1)),
                        max_delay,
                    )
                    logger.warning(
                        "%s attempt %d/%d failed: %s. Retrying in %.1fs...",
                        func.__name__,
                        attempt,
                        max_attempts,
                        e,
                        delay,
                    )
                    time.sleep(delay)
            if last_exception is not None:
                raise last_exception
            return None

        return wrapper

    return decorator
