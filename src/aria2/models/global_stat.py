"""Global statistics about the aria2 daemon."""

from __future__ import annotations

from pydantic import BaseModel


class GlobalStat(BaseModel):
    """Global statistics about the aria2 daemon."""

    download_speed: str = "0"
    upload_speed: str = "0"
    num_active: str = "0"
    num_waiting: str = "0"
    num_stopped: str = "0"
    num_stopped_total: str = "0"

    @property
    def download_speed_kbps(self) -> float:
        return int(self.download_speed) / 1024

    @property
    def upload_speed_kbps(self) -> float:
        return int(self.upload_speed) / 1024


__all__ = [
    "GlobalStat",
]
