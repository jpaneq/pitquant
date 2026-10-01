"""Source configuration status. A missing credential never breaks PITQuant: the source
reports ``SOURCE_NOT_CONFIGURED`` and any fetch raises ``SourceNotConfiguredError``.

Keys are read from the environment only. They are never logged, archived or put in a
``source_identifier`` (``redact`` strips them from URLs before anything is stored).
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from enum import StrEnum

from pitquant.core.errors import PITQuantError


class SourceStatus(StrEnum):
    CONFIGURED = "CONFIGURED"
    SOURCE_NOT_CONFIGURED = "SOURCE_NOT_CONFIGURED"


class SourceNotConfiguredError(PITQuantError):
    """The provider needs a credential that is not configured (BLOCKED_BY_CREDENTIAL)."""


@dataclass(frozen=True)
class Credential:
    env_var: str

    def status(self) -> SourceStatus:
        return (
            SourceStatus.CONFIGURED
            if os.environ.get(self.env_var)
            else (SourceStatus.SOURCE_NOT_CONFIGURED)
        )

    def get(self) -> str:
        v = os.environ.get(self.env_var)
        if not v:
            raise SourceNotConfiguredError(f"{self.env_var} not set: SOURCE_NOT_CONFIGURED")
        return v


_SECRET_PARAMS = re.compile(r"([?&](?:api_key|apikey|api_token|token)=)[^&]*", re.I)


def redact(url: str) -> str:
    """URL safe to store/log: credential query parameters replaced by ``REDACTED``."""
    return _SECRET_PARAMS.sub(r"\1REDACTED", url)
