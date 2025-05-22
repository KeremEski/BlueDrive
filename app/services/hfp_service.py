from app.models.schemas import HandsFreeData
from app.containers.logging_container import LoggingContainer
import dbus
import threading
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
import time

logger = LoggingContainer.get_logger("HandsFreeService")

class HandsFreeService:
    def __init__(self):
        DBusGMainLoop(set_as_default=True)
        self.bus = dbus.SystemBus()
        self.modem_path = None
        self.voice_call_manager = None
        self.active_call = None
        self.incoming_number = None
        self.device_name = None

        self.loop_running = False
        self.main_loop = GLib.MainLoop()

        # Ana GLib döngüsü ayrı thread
        self.mainloop_thread = threading.Thread(target=self._run_glib_loop)
        self.mainloop_thread.daemon = True

        # Modem kontrolü ayrı thread
        self.monitor_thread = threading.Thread(target=self._monitor_loop)
        self.monitor_thread.daemon = True

        #sinyal dinleyici
        self.bus.add_signal_receiver(
            self._modem_removed_handler,
            signal_name="PropertyChanged",
            dbus_interface="org.freedesktop.DBus.Properties",
            path_keyword="path"
        )

    def start(self):
        print("🎧 HandsFreeService başlatılıyor")
        self.loop_running = True
        self.mainloop_thread.start()
        self.monitor_thread.start()

    def stop(self):
        print("🛑 HandsFreeService durduruluyor")
        self.loop_running = False
        if self.main_loop.is_running():
            self.main_loop.quit()

    def _run_glib_loop(self):
        try:
            self.main_loop.run()
        except Exception as e:
            print(f"⚠️ GLib loop hatası: {e}")

    def _monitor_loop(self):
        while self.loop_running:
            try:
                if not self.modem_path:
                    self._try_initialize()
                else:
                    # modem hâlâ online mı kontrol et
                    try:
                        
                        online = self.get_modem_online_status()
                        if not online:
                            print(f"🛑 Modem bağlantısı kesildi (polling): {self.modem_path}")
                            self.modem_path = None
                            self.voice_call_manager = None
                            self.device_name = ""
                    except dbus.DBusException as e:
                        print("🛑 D-BusException türü:", type(e).__name__)
                        print("📄 Hata mesajı:", str(e))
                        self.modem_path = None
                        self.voice_call_manager = None
                        self.device_name = ""
            except Exception as e:
                print(f"[HFP Monitor] Genel hata: {e}")
            time.sleep(5)


    def _modem_removed_handler(self, interface, changed, invalidated, path=None):
        if (
            interface == "org.ofono.Modem"
            and "Online" in changed
            and changed["Online"] == False
            and path == self.modem_path
        ):
            print(f"🛑 Modem bağlantısı kesildi: {path}")
            self.modem_path = None
            self.voice_call_manager = None
            self.device_name = ""

    def _try_initialize(self):
        """Modem varsa başlatma işlemi yap"""
        try:
            manager = dbus.Interface(self.bus.get_object("org.ofono", "/"), "org.ofono.Manager")
            modems = manager.GetModems()
            for path, props in modems:
                if props.get("Online", False) and props.get("Powered", False):
                    self.modem_path = path
                    self.voice_call_manager = dbus.Interface(self.bus.get_object("org.ofono", self.modem_path), "org.ofono.VoiceCallManager")
                    self.device_name = props.get("Name", "Bilinmeyen")
                    self._setup_call_handlers()
                    print(f"📱 Cihaz bağlandı: {self.device_name} ({self.modem_path})")
                    return
            print("⏳ Bekleniyor: Bağlı modem yok.")
        except Exception as e:
            print(f"[HFP] Modem kontrol hatası: {e}")

    def _setup_call_handlers(self):
        self.bus.add_signal_receiver(
            self._call_added_handler,
            signal_name="CallAdded",
            path=self.modem_path,
            dbus_interface="org.ofono.VoiceCallManager"
        )
        self.bus.add_signal_receiver(
            self._call_ended_handler,
            signal_name="CallRemoved",
            path=self.modem_path,
            dbus_interface="org.ofono.VoiceCallManager"
        )

    def _call_added_handler(self, path, properties):
        state = properties.get("State", "")
        number = properties.get("LineIdentification", "Numara Yok")
        if state == "incoming":
            self.incoming_number = number
            self.active_call = path
            print(f"🔔 Gelen Çağrı! Arayan: {number}")
        elif state == "active":
            print(f"📞 Aktif Çağrı: {number}")

    def _call_ended_handler(self, path):
        if path == self.active_call:
            print("📴 Çağrı sonlandı")
            self.active_call = None
            self.incoming_number = None

    def get_call_status(self) -> dict:
        hpf_schema = HandsFreeData()
        hpf_schema.device_name = self.device_name or None
        hpf_schema.call_active = self.active_call is not None
        hpf_schema.caller_info = self.incoming_number or None
        return hpf_schema.model_dump_json()

    def answer_call(self):
        if self.voice_call_manager:
            calls = self.voice_call_manager.GetCalls()
            for path, props in calls:
                if props.get("State") == "incoming":
                    call_iface = dbus.Interface(self.bus.get_object("org.ofono", path), "org.ofono.VoiceCall")
                    print(f"📲 Çağrı cevaplanıyor: {path}")
                    call_iface.Answer()
                    return

    def hangup_all(self):
        if self.voice_call_manager:
            calls = self.voice_call_manager.GetCalls()
            for path, _ in calls:
                call_iface = dbus.Interface(self.bus.get_object("org.ofono", path), "org.ofono.VoiceCall")
                call_iface.Hangup()
            print("❌ Tüm çağrılar kapatıldı.")

    def start_call_monitoring(self):
        print("🎧 Çağrı izleme başlatıldı")
        try:
            self.main_loop.run()
        except KeyboardInterrupt:
            print("⏹️ İzleme durduruldu")

    def get_modem_online_status(self) -> bool:
        """Modemin online durumunu güvenli şekilde kontrol eder"""
        try:
            # 1. Modem objesini al
            modem_obj = self.bus.get_object("org.ofono", self.modem_path)
            
            # 2. Doğru arayüzü kullan (org.ofono.Modem)
            modem_iface = dbus.Interface(
                modem_obj,
                dbus_interface="org.ofono.Modem"
            )
            
            # 3. Tüm özellikleri al
            properties = modem_iface.GetProperties()
            
            # 4. Online özelliğini parse et
            return bool(properties.get('Online', False))
            
        except dbus.exceptions.DBusException as e:
            print(f"⚠️ D-Bus Hatası: {str(e)}")
            return False
        except Exception as e:
            print(f"⚠️ Genel Hata: {str(e)}")
            return False

