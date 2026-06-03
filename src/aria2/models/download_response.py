"""Discriminated union for download status responses.

Provides the ``DownloadStatusResponse`` union type and the ``_parse_status``
function that selects the correct variant based on the ``status`` field.
"""

from __future__ import annotations

from typing import Annotated, Any, cast

from pydantic import Discriminator, Tag, TypeAdapter

from aria2.models.status_active import ActiveStatus
from aria2.models.status_complete import CompleteStatus
from aria2.models.status_error import ErrorStatus
from aria2.models.status_paused import PausedStatus
from aria2.models.status_removed import RemovedStatus
from aria2.types import DownloadStatus


def _status_discriminator(v: Any) -> str:
    """Return the tag that selects which variant to parse."""
    if isinstance(v, dict):
        raw = v.get("status", "active")
    elif hasattr(v, "status"):
        raw = v.status
    else:
        raw = "active"

    if isinstance(raw, DownloadStatus):
        raw = raw.value
    return str(raw) if raw else "active"


_disc = Discriminator(_status_discriminator)

DownloadStatusResponse = Annotated[
    Annotated[ActiveStatus, Tag("active")]
    | Annotated[ActiveStatus, Tag("waiting")]
    | Annotated[PausedStatus, Tag("paused")]
    | Annotated[ErrorStatus, Tag("error")]
    | Annotated[CompleteStatus, Tag("complete")]
    | Annotated[RemovedStatus, Tag("removed")],
    _disc,
]
"""Discriminated union of all download status variants.

Parsed automatically based on the ``status`` field:

- ``"active"`` / ``"waiting"`` → :class:`ActiveStatus`
  (fields: bitfield, connections, bittorrent, …)
- ``"paused"`` → :class:`PausedStatus`
- ``"error"`` → :class:`ErrorStatus` (fields: error_code, error_message)
- ``"complete"`` → :class:`CompleteStatus`
- ``"removed"`` → :class:`RemovedStatus`

Common fields (gid, total_length, completed_length, download_speed, …)
and properties (progress_pct, speed_kbps, is_active, is_error, …) are
available on all variants.
"""

_status_adapter: Any = TypeAdapter(DownloadStatusResponse)


def _parse_status(
    data: dict[str, Any],
) -> ActiveStatus | PausedStatus | ErrorStatus | CompleteStatus | RemovedStatus:
    """Parse raw download status data into the correct variant."""
    return cast(
        "ActiveStatus | PausedStatus | ErrorStatus | CompleteStatus | RemovedStatus",
        _status_adapter.validate_python(data),
    )
