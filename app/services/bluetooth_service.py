import asyncio
import os
import shutil
import subprocess
import time
import re
from pydbus import SystemBus
import pexpect

class BluetoothService:
    def __init__(self):
        pass
    
    async def auto_connect_paired_devices(self) -> bool:
        """Eşleşmiş tüm cihazları dener ve ilk başarılı bağlantıda durur."""
        known_devices = self._get_known_devices()
        
        if not known_devices:
            print("⚠️ Eşleşmiş cihaz bulunamadı")
            return False

        print(f"🔍 {len(known_devices)} eşleşmiş cihaz taranıyor...")
        
        for index, mac in enumerate(known_devices, 1):
            print(f"\n🔌 ({index}/{len(known_devices)}) {mac} deneniyor...")
            
            # Cihaz durumunu kontrol et
            status = await self._check_device_status(mac)
            if status.get("connected"):
                print("ℹ️ Cihaz zaten bağlı")
                return True
                
            # Bağlantı denemesi
            try:
                if await self.connect_paired_device(mac):
                    print(f"✅ Başarıyla bağlandı: {mac}")
                    return True
                    
                print(f"❌ Bağlantı başarısız: {mac}")
                
            except Exception as e:
                print(f"⛔ Hata oluştu: {str(e)}")
                continue

        print("❌ Hiçbir cihaza bağlanılamadı")
        return False

    async def scan_devices(self, scan_duration=10):
        """Bluetooth cihazlarını tarar ve döndürür."""
        print("🔍 Bluetooth taraması başlatılıyor...")

        process = subprocess.Popen(
            ["bluetoothctl"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        try:
            process.stdin.write("scan on\n")
            process.stdin.flush()
            print(f"⏳ {scan_duration} saniye tarama yapılıyor...")
            time.sleep(scan_duration)

            process.stdin.write("scan off\n")
            process.stdin.write("devices\n")
            process.stdin.write("exit\n")
            process.stdin.flush()
        except Exception as e:
            print(f"❌ Tarama sırasında hata: {e}")
            process.terminate()

        output, _ = process.communicate()
        return self._parse_devices(output)  
    
    async def disconnect_device(self):
        return await self._run_bluetoothctl_commands(["disconnect"])
    
    async def connect_device(self, mac_address: str):
        """MAC adresine göre cihaz bağlanma akışı"""
        known_devices = self._get_known_devices()

        if mac_address in known_devices:
            print("🔒 Cihaz daha önce biliniyor, eşleştirilmiş olabilir.")
            return await self.connect_paired_device(mac_address)
        else:
            print("🆕 Cihaz bilinmiyor, ilk kez bağlanılıyor.")
            return await self.connect_new_device(mac_address)

    async def connect_paired_device(self, mac_address: str):
        await self.disconnect_device()
        print(f"🔗 Eşleştirilmiş cihaza bağlanılıyor: {mac_address}")
        await self._run_bluetoothctl_commands([
            f"connect {mac_address}",
            "exit"
        ]) 
        return self._try_activate_profiles(mac_address)

    async def connect_new_device(self, mac_address: str):
        """Yeni cihazı pexpect ile otomatik onaylayarak eşle ve bağlan."""
        await self.disconnect_device()
        print(f"🔐 [pexpect] Yeni cihazla eşleşme başlatılıyor: {mac_address}")
        child = None
        
        try:
            # 1. bluetoothctl oturumu başlat
            child = pexpect.spawn("bluetoothctl", encoding="utf-8", timeout=15)
            child.delaybeforesend = 0.5  # Gönderimler arası bekleme
            
            # 2. Başlangıç prompt'unu bekle
            child.expect(r"\[bluetooth\].*#", timeout=10)
            
            # 3. Agent yapılandırması
            child.sendline("agent NoInputNoOutput")
            child.expect("Agent is already registered", timeout=5)
            
            child.sendline("default-agent")
            child.expect("Default agent request successful", timeout=5)
            
            # 4. Eşleştirme işlemi
            child.sendline(f"pair {mac_address}")
            
            # 5. Tüm olası senaryoları yönet
            patterns = [
                "Confirm passkey.*yes/no",    # 0 - Passkey onayı
                "Enter PIN code:",            # 1 - PIN girişi
                "Pairing successful",         # 2 - Başarılı
                "Already paired",             # 3 - Zaten eşli
                "Failed to pair",             # 4 - Hata
                "Device not available",       # 5 - Cihaz yok
                pexpect.TIMEOUT               # 6 - Zaman aşımı
            ]
            
            while True:
                index = child.expect(patterns)
                
                if index == 0:  # Passkey onayı
                    child.sendline("yes")
                    print("✅ Passkey otomatik onaylandı")
                    
                elif index == 1:  # PIN girişi
                    child.sendline("0000")  # Varsayılan PIN
                    print("🔑 Varsayılan PIN (0000) gönderildi")
                    
                elif index == 2:  # Başarılı
                    print("✅ Eşleştirme tamamlandı")
                    break
                    
                elif index == 3:  # Zaten eşli
                    print("ℹ️ Cihaz zaten eşleşmiş")
                    break
                    
                elif index in [4,5,6]:  # Hatalar
                    print(f"❌ Hata: {child.before}")
                    return False
            # 6. Güvenilir olarak işaretle
            child.sendline(f"trust {mac_address}")
            child.expect("trust succeeded", timeout=10)
            
            # 7. Bağlantıyı kur
            child.sendline(f"connect {mac_address}")
            
            # 8. Bağlantı sonucunu kontrol et
            connection_result = child.expect([
                "Connection successful.*#", 
                "Failed to connect",
                pexpect.TIMEOUT
            ], timeout=20)
            
            if connection_result == 0:
                print("✅ Bağlantı başarılı")
                # 9. A2DP profilini aktifleştir
                child.sendline("pairable off")
                child.sendline("discoverable off")
                print("🎧 A2DP profili aktif")
                return True
                
            print(f"❌ Bağlantı hatası: {child.before}")
            return False
            
        except Exception as e:
            print(f"⛔ Kritik hata: {str(e)}")
            return False
            
        finally:
            if child and child.isalive():
                child.sendline("exit")
                child.close()

    async def _run_bluetoothctl_commands(self, commands):
        """bluetoothctl içine komutları gönder ve çıktıyı kontrol et."""
        process = subprocess.Popen(
            ["bluetoothctl"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        try:
            for cmd in commands:
                process.stdin.write(cmd + "\n")
                process.stdin.flush()
                time.sleep(3)
        except Exception as e:
            print(f"❌ Komut gönderme hatası: {e}")
            process.terminate()

        output, _ = process.communicate()
        print("📄 bluetoothctl çıktısı:")
        print(output)

        return "Connected: yes" in output
    
    def reset_bluetooth_cache(self):
        try:
            # 1. Bluetooth servisini durdur
            subprocess.run(["sudo", "systemctl", "stop", "bluetooth"], check=True)
            
            # 2. Bluetooth önbellek dizinini sil
            cache_path = "/var/lib/bluetooth"
            if os.path.exists(cache_path):
                shutil.rmtree(cache_path)
                print(f"✅ Bluetooth önbelleği silindi: {cache_path}")
            else:
                print("ℹ️ Önbellek dizini zaten mevcut değil")

            # 3. Bluetooth servisini yeniden başlat
            subprocess.run(["sudo", "systemctl", "start", "bluetooth"], check=True)
            print("♻️ Bluetooth servisi yeniden başlatıldı")
            
            return True
        
        except Exception as e:
            print(f"❌ Hata oluştu: {str(e)}")
            return False

    # Utils

    async def _check_device_status(self, mac_address: str) -> dict:
        """Cihazın bağlantı durumunu kontrol eder"""
        try:
            proc = await asyncio.create_subprocess_exec(
                "bluetoothctl", "info", mac_address,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL
            )
            stdout, _ = await proc.communicate()
            
            return {
                "connected": b"Connected: yes" in stdout,
                "paired": b"Paired: yes" in stdout,
                "trusted": b"Trusted: yes" in stdout
            }
            
        except Exception as e:
            print(f"Durum kontrol hatası: {str(e)}")
            return {}
        
## Sorunsuz Çalışan Ve Değiştirilmemesi Gerekenler

    def get_known_devices(self):
        try:
            process = subprocess.Popen(
                ["bluetoothctl"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1  # Satır tamponlamayı aktif et
            )

            # Komutları gönder ve çıktıyı oku
            commands = [
                "devices Paired\n",  # Doğru komut
                "exit\n"
            ]
            output, error = process.communicate("".join(commands), timeout=10)

            # Satır örneği: "Device 40:4E:36:AA:BB:CC JBL Speaker"
            device_pattern = re.compile(r"Device\s+([0-9A-Fa-f:]{17})\s+(.+)")
            
            devices = []
            for line in output.strip().splitlines():
                match = device_pattern.match(line.strip())
                if match:
                    mac = match.group(1)
                    name = match.group(2)
                    devices.append({"name": name, "mac": mac})

            return devices

        except (subprocess.CalledProcessError, FileNotFoundError, PermissionError) as e:
            print(f"Hata oluştu: {str(e)}")
            return []
    
    def _get_known_devices(self):
        """Eşleştirilmiş cihazların MAC adreslerini döndürür."""
        try:
            # bluetoothctl'i etkileşimli modda başlat
            process = subprocess.Popen(
                ["bluetoothctl"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1  # Satır tamponlamayı aktif et
            )

            # Komutları gönder ve çıktıyı oku
            commands = [
                "devices Paired\n",  # Doğru komut
                "exit\n"
            ]
            output, error = process.communicate("".join(commands), timeout=10)

            # Hata kontrolü
            if error:
                print(f"Hata: {error}")
                return []

            # MAC adreslerini bul (büyük-küçük harf duyarsız)
            mac_pattern = re.compile(
                r"Device\s+((?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2})", 
                re.IGNORECASE
            )
            devices = mac_pattern.findall(output)

            return list(set(devices))  # Tekrar edenleri filtrele

        except Exception as e:
            print(f"Kritik hata: {str(e)}")
            return []
        
    def _parse_devices(self, output: str):
        """bluetoothctl çıktısını düzenli ifadeyle parse eder."""
        pattern = re.compile(r'Device ((?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}) (.+)')
        devices = []

        for line in output.splitlines():
            match = pattern.search(line)
            if match:
                mac, name = match.groups()
                devices.append({"mac": mac.strip(), "name": name.strip()})

        unique_devices = {d['mac']: d for d in devices}.values()
        return list(unique_devices)
    
    def _try_activate_profiles(self,mac_address: str):
        bus = SystemBus()
        device_path = f"/org/bluez/hci0/dev_{mac_address.replace(':', '_')}"
        
        try:
            device = bus.get("org.bluez", device_path)
            print(f"🔗 Cihaz bağlanıyor: {mac_address}")
            device.Connect()
            time.sleep(2)
        except Exception as e:
            print(f"❌ Bağlantı hatası: {e}")
            return

        # UUID'ler üzerinden desteklenen profilleri kontrol edelim
        try:
            uuids = device.UUIDs
            print("📋 Desteklenen profiller:")
            for uuid in uuids:
                print(f" → {uuid}")
        except Exception as e:
            print(f"⚠️ UUID okunamadı: {e}")
            uuids = []

        # A2DP tetikle
        try:
            print("🎵 A2DP (player0) tetikleniyor...")
            player = bus.get("org.bluez", f"{device_path}/player0")
            player.Play()
            time.sleep(1)
            player.Pause()
            print("✅ A2DP aktif.")
        except Exception as e:
            print(f"❌ A2DP açılırken hata: {e}")

        # AVRCP kontrolü (player zaten tetikliyor ama ayrı log için)
        if any("110e" in uuid or "110c" in uuid for uuid in uuids):
            print("🎮 AVRCP destekleniyor (player0 üzerinden zaten tetiklendi).")
        else:
            print("⚠️ AVRCP UUID bulunamadı.")

        # HFP Audio Gateway (not: BlueZ tek başına HFP desteklemez)
        try:
            if any("111f" in uuid for uuid in uuids):
                print("📞 HFP destekleniyor, tetiklenmeye çalışılıyor (oFono gerekebilir).")
                # BlueZ üzerinden doğrudan bağlanamaz, sadece bilgilendirme
            else:
                print("⚠️ HFP UUID bulunamadı.")
        except Exception as e:
            print(f"❌ HFP kontrol hatası: {e}")
