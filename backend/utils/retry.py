"""
novaTech — Centralized Retry Utilities

Provides async and sync retry decorators with exponential backoff, jitter,
and logging for external APIs, LLM calls, embeddings, vector databases,
and network operations.
"""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable, Tuple, Type, Union

from tenacity import (
    AsyncRetrying,
    Retrying,
    before_sleep_log,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

logger = logging.getLogger(__name__)


def async_retry(
    max_attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 10.0,
    exceptions: Union[Type[BaseException], Tuple[Type[BaseException], ...]] = Exception,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator to retry asynchronous functions with exponential backoff and jitter.

    Args:
        max_attempts: Maximum number of retry attempts.
        min_wait: Minimum wait time in seconds.
        max_wait: Maximum wait time in seconds.
        exceptions: Exception class or tuple of exception classes to catch and retry.
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(max_attempts),
                wait=wait_exponential_jitter(initial=min_wait, max=max_wait),
                retry=retry_if_exception_type(exceptions),
                before_sleep=before_sleep_log(logger, logging.WARNING),
                reraise=True,
            ):
                with attempt:
                    return await func(*args, **kwargs)
        return wrapper
    return decorator


def sync_retry(
    max_attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 10.0,
    exceptions: Union[Type[BaseException], Tuple[Type[BaseException], ...]] = Exception,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator to retry synchronous functions with exponential backoff and jitter.

    Args:
        max_attempts: Maximum number of retry attempts.
        min_wait: Minimum wait time in seconds.
        max_wait: Maximum wait time in seconds.
        exceptions: Exception class or tuple of exception classes to catch and retry.
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            for attempt in Retrying(
                stop=stop_after_attempt(max_attempts),
                wait=wait_exponential_jitter(initial=min_wait, max=max_wait),
                retry=retry_if_exception_type(exceptions),
                before_sleep=before_sleep_log(logger, logging.WARNING),
                reraise=True,
            ):
                with attempt:
                    return func(*args, **kwargs)
        return wrapper
    return decorator
