"""Base download status model — private, shared by all status variants."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator

from aria2.models.file import FileInfo
from aria2.types import DownloadStatus


class _BaseDownloadStatus(BaseModel):
    """Common fields shared by all download status variants."""

    model_config = ConfigDict(populate_by_name=True)

    gid: str
    status: DownloadStatus
    total_length: str = "0"
    completed_length: str = "0"
    upload_length: str = "0"
    download_speed: str = "0"
    upload_speed: str = "0"
    piece_length: str = "0"
    num_pieces: str = "0"
    dir: str = ""
    files: list[FileInfo] = []
    followed_by: list[str] = []
    following: str = ""
    belongs_to: str = ""

    # ── Properties shared by all variants ─────────────────

    @property
    def progress_pct(self) -> float:
        total = int(self.total_length)
        if total == 0:
            return 0.0
        return int(self.completed_length) / total * 100

    @property
    def speed_kbps(self) -> float:
        return int(self.download_speed) / 1024

    @property
    def is_active(self) -> bool:
        return False

    @property
    def is_complete(self) -> bool:
        return False

    @property
    def is_error(self) -> bool:
        return False

    @field_validator("status", mode="before")
    @classmethod
    def _coerce_status(cls, v: object) -> str:
        if isinstance(v, DownloadStatus):
            return v.value
        return str(v) if v else "active"
