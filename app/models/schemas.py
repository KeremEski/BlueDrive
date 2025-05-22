from pydantic import BaseModel
from typing import Optional

class Metadata(BaseModel):
    title: Optional[str] = None
    artist: Optional[str] = None
    album: Optional[str] = None
    release_date: Optional[str] = None
    cover_url: Optional[str] = None
    spotify_url: Optional[str] = None
    popularity: Optional[int] = None
    duration_ms: Optional[int] = None
    position: Optional[int] = None
    status: Optional[str] = None

class HandsFreeData(BaseModel):
    device_name: Optional[str] = None
    call_active: bool = False
    caller_info: Optional[str] = None

class WifiCredentials(BaseModel):
    ssid: str
    password: str

class WifiNetwork(BaseModel):
    ssid: str
    signal: int
    security: str
    bssid: str
    interface: str