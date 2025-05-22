import os
import re
import unicodedata

from app.models.schemas import Metadata
from app.containers.logging_container import LoggingContainer
import requests
from pydbus import SystemBus
from dotenv import load_dotenv
from fastapi.responses import JSONResponse
from spotipy import Spotify
from spotipy.oauth2 import SpotifyClientCredentials

logger = LoggingContainer.get_logger("MediaService")

class MediaService:
    def __init__(self):
        load_dotenv()
        self.bus = SystemBus()
        self.sp = self._init_spotify()

    def _init_spotify(self):
        client_id = os.getenv("SPOTIFY_CLIENT_ID")
        client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
        auth_manager = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
        return Spotify(auth_manager=auth_manager)

    def get_metadata(self) -> Metadata | JSONResponse:
        player_path = self._find_avrcp_player_path()
        if not player_path:
            return JSONResponse(status_code=404, content={"error": "AVRCP destekli bağlı cihaz bulunamadı"})

        try:
            player = self.bus.get("org.bluez", player_path)
            props_iface = self.bus.get("org.bluez", player_path)["org.freedesktop.DBus.Properties"]

            try:
                track = props_iface.Get("org.bluez.MediaPlayer1", "Track")
            except Exception:
                track = {}

            try:
                position = props_iface.Get("org.bluez.MediaPlayer1", "Position")
            except Exception:
                position = 0

            try:
                status = props_iface.Get("org.bluez.MediaPlayer1", "Status")
            except Exception:
                status = "unknown"

            return Metadata(
                title=track.get("Title"),
                artist=track.get("Artist"),
                album=track.get("Album"),
                release_date=None,
                cover_url=None,
                spotify_url=None,
                popularity=None,
                duration_ms=int(track.get("Duration", 0) / 1_000_000),
                position=int(position / 1_000_000),
                status=status
            )

        except Exception as e:
            print(f"Metadata alınırken hata oluştu: {e}")
            return JSONResponse(status_code=500, content={"error": "Metadata alınırken hata oluştu."})

    def get_spotify_metadata(self):
        """Bluetooth + Spotify üzerinden detaylı metadata döndürür."""
        base_metadata = self.get_metadata()
        if isinstance(base_metadata, JSONResponse):
            return base_metadata  # Hata varsa direkt dön

        title = base_metadata.title or ""
        artist = base_metadata.artist or ""
        status = base_metadata.status or ""

        if not title or not artist:
            return base_metadata  # Şarkı bilgisi yoksa Bluetooth bilgisi yeterlidir

        try:
            query = f"{title} {artist}".strip()
            if not query:
                return base_metadata

            try:
                result = self.sp.search(q=query, type='track', limit=1)
            except requests.exceptions.Timeout:
                print("Spotify API yanıt vermedi (timeout).")
                return base_metadata
            except Exception as e:
                print(f"Spotify sorgusu sırasında hata oluştu: {e}")
                return base_metadata

            tracks = result.get('tracks', {}).get('items', [])
            if not tracks:
                return base_metadata

            track_sp = tracks[0]
            title_spotify = track_sp['name']
            artist_spotify = track_sp['artists'][0]['name']

            # Eşleşme kontrolü
            if self._normalize(title_spotify) != self._normalize(title) and \
            self._normalize(artist_spotify) != self._normalize(artist):
                return base_metadata

            # Metadata nesnesini güncellenmiş şekilde döndür
            return Metadata(
                title=title_spotify,
                artist=artist_spotify,
                album=track_sp['album']['name'],
                release_date=track_sp['album']['release_date'],
                cover_url=track_sp['album']['images'][0]['url'],
                spotify_url=track_sp['external_urls']['spotify'],
                popularity=track_sp['popularity'],
                duration_ms=track_sp['duration_ms'],
                position=base_metadata.position,
                status=status
            )

        except Exception as e:
            print(f"Spotify sorgusu sırasında hata oluştu: {e}")
            return base_metadata

    def next(self):
        try:
            iface = self._get_player_interface()
            iface.Next()
            return {"status": "skipped to next"}
        except Exception as e:
            return JSONResponse(status_code=500, content={"error": f"Next komutu başarısız: {e}"})

    def previous(self):
        try:
            iface = self._get_player_interface()
            iface.Previous()
            return {"status": "went to previous"}
        except Exception as e:
            return JSONResponse(status_code=500, content={"error": f"Previous komutu başarısız: {e}"})

    def toggle_playback(self):
        try:
            iface = self._get_player_interface()
            status = iface.Status

            if status == "playing":
                iface.Pause()
                return {"status": "paused"}
            else:
                iface.Play()
                return {"status": "playing"}

        except Exception as e:
            return JSONResponse(status_code=500, content={"error": f"toggle_playback başarısız: {e}"})

    def _normalize(self, text):
        text = unicodedata.normalize('NFKD', text)  # Unicode normalize
        text = text.encode('ascii', 'ignore').decode('utf-8')  # Aksanları kaldır
        text = text.lower().strip()  # Küçük harf, baş-son boşluk temizliği
        text = re.sub(r'[^\w\s]', '', text)  # Noktalama işaretlerini kaldır
        return text
    
    def _get_player_interface(self):
        """AVRCP player interface'ini döndürür."""
        player_path = self._find_avrcp_player_path()
        if not player_path:
            raise Exception("AVRCP destekli cihaz bulunamadı.")
        player = self.bus.get("org.bluez", player_path)
        return player["org.bluez.MediaPlayer1"]
    
    def _find_avrcp_player_path(self):
        """BlueZ üzerinden AVRCP destekli bağlı cihazı bulur."""
        try:
            mngr = self.bus.get("org.bluez", "/")
            objects = mngr.GetManagedObjects()
            for path, interfaces in objects.items():
                if "org.bluez.MediaPlayer1" in interfaces:
                    return path
        except Exception as e:
            print(f"AVRCP player path ararken hata oluştu: {e}")
        return None
