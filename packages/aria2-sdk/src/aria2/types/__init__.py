"""Core types for the aria2 SDK."""

from __future__ import annotations

from enum import StrEnum
from typing import NewType

GID = NewType("GID", str)
"""A 32-character hex string identifying a download in aria2."""


class DownloadStatus(StrEnum):
    """Status of a download as returned by aria2.

    Inherits from ``StrEnum`` for direct string comparison with
    the raw values returned by the aria2 JSON-RPC API.
    """

    ACTIVE = "active"
    WAITING = "waiting"
    PAUSED = "paused"
    ERROR = "error"
    COMPLETE = "complete"
    REMOVED = "removed"


class StatusType(StrEnum):
    """Status classification with behavioral properties.

    Extends ``DownloadStatus`` with computed flags so that
    status-checking logic lives in one place rather than being
    scattered across model subclasses.
    """

    ACTIVE = "active"
    WAITING = "waiting"
    PAUSED = "paused"
    ERROR = "error"
    COMPLETE = "complete"
    REMOVED = "removed"

    @property
    def is_active(self) -> bool:
        """Whether this status represents an actively running download."""
        return self in (StatusType.ACTIVE, StatusType.WAITING)

    @property
    def is_complete(self) -> bool:
        """Whether this status represents a completed download."""
        return self == StatusType.COMPLETE

    @property
    def is_error(self) -> bool:
        """Whether this status represents a failed download."""
        return self == StatusType.ERROR


class PositionHow(StrEnum):
    """How to interpret the position argument in ``change_position``."""

    SET = "POS_SET"
    """Position relative to the start of the queue."""
    CUR = "POS_CUR"
    """Position relative to the current position."""
    END = "POS_END"
    """Position relative to the end of the queue."""


__all__ = [
    "GID",
    "DownloadStatus",
    "PositionHow",
    "StatusType",
]
