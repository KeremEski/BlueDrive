import asyncio
import os
import shutil
import subprocess
import time
import re
from app.containers.logging_container import LoggingContainer
from pydbus import SystemBus
import pexpect

logger = LoggingContainer.get_logger("BluetoothService")

class BluetoothService:
    def __init__(self):
        pass
    
    # Need to be updated
    async def auto_connect_paired_devices(self) -> bool:
        return True

    # Completed
    async def scan_devices(self, scan_duration=10):
        """Scan bluetooth devices for a given duration."""
        logger.info(f"Scanning is started. Scan duration is {scan_duration}")
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
            time.sleep(scan_duration)
            process.stdin.write("scan off\n")
            process.stdin.write("devices\n")
            process.stdin.write("exit\n")
            process.stdin.flush()
        except Exception as e:
            logger.error(f"Error while sending commands: {e}")
            process.terminate()

        output, _ = process.communicate()
        return self._parse_devices(output)  
    
    # It can be better
    async def disconnect_device(self):
        """Disconnect connected device."""
        logger.info("Disconnecting device...")
        return await self._run_bluetoothctl_commands(["disconnect"])
    
    # Completed
    async def connect_device(self, mac_address: str):
        """ Trys to connect to a device. If the device is already paired, it will connect directly. If not, it will pair and connect."""
        logger.info(f"Connecting to device: {mac_address}")
        known_devices = self._get_known_devices_mac_address()
        if mac_address in known_devices:
            logger.info(f"Device {mac_address} is already paired.")
            return await self.connect_paired_device(mac_address)
        else:
            logger.info(f"Device {mac_address} is new. Pairing and connecting...")
            return await self.connect_new_device(mac_address)
    
    # Completed
    async def connect_paired_device(self, mac_address: str):
        """Connect to a paired device."""
        await self.disconnect_device()
        logger.info(f"Connecting to paired device: {mac_address}")
        try:
            await self._run_bluetoothctl_commands([
                f"connect {mac_address}",
                "exit"
            ])  
            return self._try_activate_profiles(mac_address)
        except Exception as e:
            logger.error(f"Connecting to paired device failed: {e}")
            return False

    # Check if this function is working
    async def connect_new_device(self, mac_address: str):
        """Pair and connect a new device using pexpect with auto-confirmation."""
        await self.disconnect_device()
        logger.info(f"🔐 [pexpect] Starting pairing with new device: {mac_address}")
        child = None
        
        try:
            # 1. Start bluetoothctl session
            child = pexpect.spawn("bluetoothctl", encoding="utf-8", timeout=15)
            child.delaybeforesend = 0.5  # Delay between sends
            
            # 2. Wait for initial prompt
            child.expect(r"\[bluetooth\].*#", timeout=10)
            
            # 3. Agent configuration
            child.sendline("agent NoInputNoOutput")
            child.expect("Agent is already registered", timeout=5)
            
            child.sendline("default-agent")
            child.expect("Default agent request successful", timeout=5)
            
            # 4. Begin pairing
            child.sendline(f"pair {mac_address}")
            
            # 5. Handle possible responses
            patterns = [
                "Confirm passkey.*yes/no",    # 0 - Confirm passkey
                "Enter PIN code:",            # 1 - Request PIN
                "Pairing successful",         # 2 - Success
                "Already paired",             # 3 - Already paired
                "Failed to pair",             # 4 - Failed
                "Device not available",       # 5 - Not found
                pexpect.TIMEOUT               # 6 - Timeout
            ]
            
            while True:
                index = child.expect(patterns)
                
                if index == 0:  # Passkey confirmation
                    child.sendline("yes")
                    logger.info("✅ Passkey automatically confirmed")
                    
                elif index == 1:  # Enter PIN
                    child.sendline("0000")  # Default PIN
                    logger.info("🔑 Default PIN (0000) sent")
                    
                elif index == 2:  # Success
                    logger.info("✅ Pairing completed successfully")
                    break
                    
                elif index == 3:  # Already paired
                    logger.info("ℹ️ Device already paired")
                    break
                    
                elif index in [4, 5, 6]:  # Errors
                    logger.error(f"❌ Pairing error: {child.before}")
                    return False

            # 6. Mark device as trusted
            child.sendline(f"trust {mac_address}")
            child.expect("trust succeeded", timeout=10)
            
            # 7. Attempt to connect
            child.sendline(f"connect {mac_address}")
            
            # 8. Check connection result
            connection_result = child.expect([
                "Connection successful.*#", 
                "Failed to connect",
                pexpect.TIMEOUT
            ], timeout=20)
            
            if connection_result == 0:
                logger.info("✅ Device connected successfully")
                # 9. Disable pairable/discoverable modes
                child.sendline("pairable off")
                child.sendline("discoverable off")
                logger.info("🎧 A2DP profile activated")
                return True
                
            logger.error(f"❌ Connection failed: {child.before}")
            return False
            
        except Exception as e:
            logger.exception(f"⛔ Critical error during device connection: {str(e)}")
            return False
            
        finally:
            if child and child.isalive():
                child.sendline("exit")
                child.close()

    # Completed
    async def _run_bluetoothctl_commands(self, commands):
        """Send commands into bluetoothctl and check the output."""
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
            logger.error(f"❌ Error while sending commands: {e}")
            process.terminate()

        output, _ = process.communicate()
        logger.debug("📄 bluetoothctl output:")
        logger.debug(output)

        return "Connected: yes" in output
    
    # Completed
    def reset_bluetooth_cache(self):
        try:
            # 1. Stop the Bluetooth service
            subprocess.run(["sudo", "systemctl", "stop", "bluetooth"], check=True)
            
            # 2. Delete the Bluetooth cache directory
            cache_path = "/var/lib/bluetooth"
            if os.path.exists(cache_path):
                shutil.rmtree(cache_path)
                logger.info(f"✅ Bluetooth cache deleted: {cache_path}")
            else:
                logger.info("ℹ️ Cache directory does not exist")

            # 3. Restart the Bluetooth service
            subprocess.run(["sudo", "systemctl", "start", "bluetooth"], check=True)
            logger.info("♻️ Bluetooth service restarted")
            
            return True
        
        except Exception as e:
            logger.error(f"❌ An error occurred while resetting Bluetooth cache: {str(e)}")
            return False
        
    # Completed
    def get_known_devices(self):
        try:
            # Launch bluetoothctl in interactive mode
            process = subprocess.Popen(
                ["bluetoothctl"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1  # Enable line buffering
            )

            # Send commands and read the output
            commands = [
                "devices Paired\n",  # Correct command to list paired devices
                "exit\n"
            ]
            output, error = process.communicate("".join(commands), timeout=10)

            # Example line: "Device 40:4E:36:AA:BB:CC JBL Speaker"
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
            logger.error(f"Error occurred while retrieving paired devices: {str(e)}")
            return []
    
    # Completed
    def _get_known_devices_mac_address(self) -> list[str]:
        """Returns the list of paired Bluetooth device MAC addresses using bluetoothctl."""
        try:
            logger.info("Retrieving paired devices using bluetoothctl...")

            # Launch bluetoothctl in interactive mode
            process = subprocess.Popen(
                ["bluetoothctl"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1  # Enable line buffering
            )

            # Send commands to bluetoothctl
            commands = [
                "devices Paired\n",  # Lists paired devices
                "exit\n"
            ]
            output, error = process.communicate("".join(commands), timeout=10)

            # Check for any error output
            if error:
                logger.error(f"bluetoothctl error: {error}")
                return []

            # Extract MAC addresses from output using regex
            mac_pattern = re.compile(
                r"Device\s+((?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2})",
                re.IGNORECASE
            )
            devices = mac_pattern.findall(output)
            unique_devices = list(set(devices))  # Remove duplicates

            logger.info(f"Found {len(unique_devices)} paired device(s).")
            return unique_devices

        except subprocess.TimeoutExpired:
            logger.error("bluetoothctl command timed out.")
            return []

        except Exception as e:
            logger.exception(f"Unexpected error while retrieving paired devices: {e}")
            return []
        
    # Completed
    def _parse_devices(self, output: str):
        """Get bluetooth devices from the output of bluetoothctl."""
        pattern = re.compile(r'Device ((?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}) (.+)')
        devices = []
        for line in output.splitlines():
            match = pattern.search(line)
            if match:
                mac, name = match.groups()
                devices.append({"mac": mac.strip(), "name": name.strip()})
        unique_devices = {d['mac']: d for d in devices}.values()
        return list(unique_devices)
    
    # Completed -- Need to be more tests
    def _try_activate_profiles(self, mac_address: str) -> bool:
        """Try to activate supported Bluetooth profiles for a connected device."""
        logger.info(f"Activating profiles for device: {mac_address}")
        bus = SystemBus()
        device_path = f"/org/bluez/hci0/dev_{mac_address.replace(':', '_')}"

        try:
            device = bus.get("org.bluez", device_path)

            # Do not reconnect if already connected
            if not device.Connected:
                logger.warning("Device is not connected. Skipping profile activation.")
                return False

        except Exception as e:
            logger.error(f"Device retrieval error: {e}")
            return False

        # Try to read supported UUIDs
        try:
            uuids = device.UUIDs
            logger.debug(f"UUIDs: {uuids}")
        except Exception as e:
            logger.error(f"Error retrieving UUIDs: {e}")
            uuids = []

        # Attempt to activate A2DP via MediaPlayer1 (if available)
        try:
            player = bus.get("org.bluez", f"{device_path}/player0")
            player.Play()
            time.sleep(1)
            player.Pause()
            logger.info("✅ A2DP activated successfully.")
        except Exception as e:
            logger.warning(f"❌ Failed to activate A2DP: {e}")

        # AVRCP profile detection (optional log only)
        if any("110e" in uuid or "110c" in uuid for uuid in uuids):
            logger.info("🎵 AVRCP is supported by the device.")
        else:
            logger.warning("⚠️ AVRCP UUID not found.")

        # HFP (Hands-Free Profile) detection only
        try:
            if any("111f" in uuid for uuid in uuids):
                logger.info("📞 HFP is supported (info only, not activated via BlueZ).")
            else:
                logger.warning("⚠️ HFP UUID not found.")
        except Exception as e:
            logger.error(f"❌ Error while checking HFP support: {e}")

        return True
    
    """ def _try_activate_profiles(self,mac_address: str) -> bool:
        Connect device and try to activate profiles.
        logger.info(f"Profiles are being activated for {mac_address}")
        bus = SystemBus()
        device_path = f"/org/bluez/hci0/dev_{mac_address.replace(':', '_')}"
        
        try:
            device = bus.get("org.bluez", device_path)
            device.Connect()
            time.sleep(1)
        except Exception as e:
            logger.error(f"Connection error: {e}")
            return False

        # UUID'ler üzerinden desteklenen profilleri kontrol edelim
        try:
            uuids = device.UUIDs
            for uuid in uuids:
                print(f" → {uuid}")
        except Exception as e:
            logger.error(f"Error catched on UUID retrieval: {e}")
            uuids = []

        # A2DP tetikle
        try:
            player = bus.get("org.bluez", f"{device_path}/player0")
            player.Play()
            time.sleep(1)
            player.Pause()
            logger.info(f"✅ A2DP  Activated")
        except Exception as e:
            logger.warning(f"❌ A2DP error when opening: {e}")

        # AVRCP kontrolü (player zaten tetikliyor ama ayrı log için)
        if any("110e" in uuid or "110c" in uuid for uuid in uuids):
            logger.info("🎵 AVRCP is supported. Try to trigger.")
        else:
            logger.warning("⚠️ AVRCP UUID is not found.")

        # HFP Audio Gateway (not: BlueZ tek başına HFP desteklemez)
        try:
            if any("111f" in uuid for uuid in uuids):
                logger.info("📞 HFP is supported, try to trigger.")
                # BlueZ üzerinden doğrudan bağlanamaz, sadece bilgilendirme
            else:
                logger.warning("⚠️ HFP UUID is not found.")
        except Exception as e:
            logger.error(f"❌ HFP control error: {e}")
        return True """

