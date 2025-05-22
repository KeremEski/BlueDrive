import subprocess
import time
import re
from typing import List, Dict, Optional

from app.models.schemas import WifiNetwork


class WifiService:
    def __init__(self, interface: str = 'wlan0', scan_timeout: int = 10):
        self.interface = interface
        self.scan_timeout = scan_timeout
        self._validate_interface()

    def _validate_interface(self):
        try:
            subprocess.run(['nmcli', '-t', 'device', 'status'], check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Geçersiz ağ arayüzü: {self.interface}") from e

    def _trigger_scan(self) -> bool:
        try:
            subprocess.run(
                ['nmcli', 'device', 'wifi', 'rescan'],
                check=True,
                timeout=15,
                capture_output=True,
                text=True
            )
            return True
        except subprocess.TimeoutExpired:
            print("Tarama işlemi zaman aşımına uğradı")
            return False
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Tarama başlatma hatası: {e.stderr}") from e

    def scan_networks(self) -> List[Dict[str, str]]:
        try:
            if not self._trigger_scan():
                return []

            print(f"Tarama tamamlanması bekleniyor ve veri bekleniyor...")

            # 3 kez tekrar dene
            for attempt in range(5):
                time.sleep(self.scan_timeout)
                result = subprocess.run(
                    ['nmcli', '-t', '-f', 'SSID,SIGNAL,SECURITY,BSSID', 'device', 'wifi', 'list'],
                    capture_output=True,
                    text=True
                )
                if result.stdout.strip():
                    return self._parse_scan_results(result.stdout)
                print(f"❗ Tarama boş döndü. Yeniden deneme: {attempt+1}/5")

            raise RuntimeError("Hiçbir WiFi ağı bulunamadı.")

        except Exception as e:
            raise RuntimeError(f"Tarama hatası: {str(e)}") from e

    def _parse_scan_results(self, output: str) -> List[WifiNetwork]:
        networks = []
        seen_bssids = set()

        for line in output.strip().splitlines():
            parts = line.split(":")
            if len(parts) < 4:
                continue

            ssid, signal, security, bssid = parts[0].strip(), parts[1], parts[2], parts[3]
            if not ssid or bssid in seen_bssids:
                continue

            network = WifiNetwork(
                ssid=ssid,
                signal=int(signal),
                security=security if security else 'Open',
                bssid=bssid,
                interface=self.interface
            )
            networks.append(network)
            seen_bssids.add(bssid)

        return sorted(networks, key=lambda x: x.signal, reverse=True)
    
    def connect(self, ssid: str, password: Optional[str] = None) -> bool:
        """
        Belirtilen WiFi ağına bağlanır
        """
        try:
            cmd = ['nmcli', 'device', 'wifi', 'connect', ssid]
            if password:
                cmd += ['password', password]

            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # Bağlantı başarı kontrolü
            if "successfully activated" in result.stdout:
                return True
            return False
            
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.lower()
            if 'secrets' in error_msg:
                raise PermissionError("Geçersiz şifre") from e
            if 'no network' in error_msg:
                raise ConnectionError("Ağ bulunamadı") from e
            raise RuntimeError(f"Bağlantı hatası: {e.stderr}") from e

    def disconnect(self) -> bool:
        """
        Mevcut WiFi bağlantısını keser
        """
        try:
            subprocess.run(
                ['nmcli', 'device', 'disconnect', self.interface],
                check=True,
                capture_output=True,
                text=True
            )
            return True
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Bağlantı kesme hatası: {e.stderr}") from e

    def get_wifi_status(self) -> Dict[str, str]:
        """
        WiFi bağlantı durumunu ve genel durumu döndürür
        """
        try:
            # Genel WiFi durumu
            radio_status = subprocess.run(
                ['nmcli', 'radio', 'wifi'],
                capture_output=True,
                text=True
            ).stdout.strip()
            
            # Aktif bağlantı bilgisi
            connection = subprocess.run(
                ['nmcli', '-t', '-f', 'NAME,DEVICE,TYPE', 'connection', 'show', '--active'],
                capture_output=True,
                text=True
            ).stdout
            
            current_connection = None
            for line in connection.splitlines():
                if 'wifi' in line:
                    parts = line.split(':')
                    current_connection = {
                        'name': parts[0],
                        'device': parts[1],
                        'type': parts[2]
                    }
                    break

            return {
                'radio': radio_status,
                'connected': current_connection is not None,
                'connection': current_connection
            }

        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Durum bilgisi alınamadı: {e.stderr}") from e

    def get_current_connection(self) -> Optional[WifiNetwork]:
        """
        Aktif bağlantıyı WifiNetwork nesnesi olarak döndürür
        """
        status = self.get_wifi_status()
        if not status['connected']:
            return None

        try:
            result = subprocess.run(
                ['nmcli', '-t', '-f', 'SSID,SIGNAL,BSSID', 'device', 'wifi'],
                capture_output=True,
                text=True
            )
            
            for line in result.stdout.splitlines():
                if status['connection']['name'] in line:
                    ssid, signal, bssid = line.split(':')[:3]
                    return WifiNetwork(
                        ssid=ssid,
                        signal=int(signal),
                        security='',  # Aktif bağlantıda security bilgisi mevcut değil
                        bssid=bssid,
                        interface=self.interface
                    )
            return None
            
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Bağlantı detayları alınamadı: {e.stderr}") from e
