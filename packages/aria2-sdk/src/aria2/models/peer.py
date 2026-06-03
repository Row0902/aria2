"""BitTorrent peer information."""

from __future__ import annotations

from pydantic import BaseModel


class PeerInfo(BaseModel):
    """BitTorrent peer information."""

    peer_id: str
    ip: str
    port: str
    bitfield: str = ""
    am_choking: str = ""
    peer_choking: str = ""
    download_speed: str = "0"
    upload_speed: str = "0"
    seeder: str = "false"

    @property
    def is_seeder(self) -> bool:
        """Return whether this peer is acting as a seeder."""
        return self.seeder == "true"


__all__ = [
    "PeerInfo",
]
