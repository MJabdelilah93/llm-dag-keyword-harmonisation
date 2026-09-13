"""Shared paid-execution gate. Every LLM-based frozen-inference runner in
this package must go through this gate. Default behaviour is always a
dry run: build the exact request payload(s) and count them, never call
any API. A real call requires BOTH an explicit ``execute_paid=True``
argument (or ``--execute-paid`` on the CLI) AND the relevant API key
present in the environment -- and even then, this gate itself makes no
network call; it only decides whether the caller is authorised to
proceed to one.
"""
from __future__ import annotations

import os


class PaidExecutionNotAuthorisedError(Exception):
    pass


def require_paid_execution_authorised(execute_paid: bool, api_key_env_var: str) -> str:
    if not execute_paid:
        raise PaidExecutionNotAuthorisedError(
            "Paid execution not authorised -- pass execute_paid=True (or --execute-paid on the CLI) "
            "to make real API calls. The default invocation never does."
        )
    api_key = os.environ.get(api_key_env_var)
    if not api_key:
        raise PaidExecutionNotAuthorisedError(
            f"{api_key_env_var} is not set -- refusing to attempt a real API call without a key present."
        )
    return api_key
