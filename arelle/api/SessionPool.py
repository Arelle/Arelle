"""
See COPYRIGHT.md for copyright information.

The `arelle.api` module is the supported method for integrating Arelle into other Python applications.
"""
from __future__ import annotations

import logging
import multiprocessing
from dataclasses import dataclass
from typing import Callable, Any, TypeVar, Generic

from arelle.RuntimeOptions import RuntimeOptions
from arelle.api.Session import Session

_R = TypeVar("_R")  # Replace when Python 3.11 support is dropped.

@dataclass(frozen=True)
class PooledSessionOptions(Generic[_R]):
    """
    Options for running a Session in a multiprocessing pool.

    Attributes:
        runtime_options: The RuntimeOptions to run the Session with.
        results_callback: A callback function that returns results given a post-execution Session object.
    """
    runtime_options: RuntimeOptions
    result_callback: Callable[[Session], _R]


def _map_func(options: PooledSessionOptions[_R]) -> tuple[RuntimeOptions, _R]:
    """
    Run a Session with the given RuntimeOptions and return the results from the callback.
    This function is designed to be used with multiprocessing pools, and should not be called directly.
    It contains the necessary logic to ensure logging is gracefully completed before terminaiton.
    """
    with Session() as session:
        session.run(options.runtime_options)
        results = options.result_callback(session)
    # Allow logging handlers to flush completely before closing.
    # Otherwise, this Session's logs may be lost if the processed is terminated before the handlers flush.
    logging.shutdown()
    return options.runtime_options, results


class SessionPool:
    """
    A wrapper around multiprocessing.Pool that is designed to run Arelle Sessions in parallel.
    """

    def __init__(self, *args: Any, **kwargs: Any):
        if 'maxtasksperchild' in kwargs and kwargs['maxtasksperchild'] != 1:
            raise ValueError(
                f"SessionPool requires maxtasksperchild=1, but {kwargs['maxtasksperchild']} was provided."
            )
        kwargs['maxtasksperchild'] = 1
        self._pool = multiprocessing.Pool(*args, **kwargs)

    def __enter__(self) -> SessionPool:
        self._pool.__enter__()
        return self

    def __exit__(self, *args: Any, **kwargs: Any) -> None:
        self._pool.__exit__(*args, **kwargs)

    def __reduce__(self) -> str | tuple[Any, ...]:
        return self._pool.__reduce__()

    def map(
            self,
            result_callback: Callable[[Session], _R],
            runtime_options_list: list[RuntimeOptions],
    ) -> list[tuple[RuntimeOptions, _R]]:
        iterable = [
            PooledSessionOptions(
                runtime_options=runtime_options,
                result_callback=result_callback,
            )
            for runtime_options in runtime_options_list
        ]
        return self._pool.map(func=_map_func, iterable=iterable)
