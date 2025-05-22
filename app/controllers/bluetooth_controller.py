# app/controllers/bluetooth_controller.py
from fastapi import APIRouter, WebSocket
from app.services.bluetooth_service import BluetoothService

router = APIRouter()
bluetooth_service = BluetoothService()

@router.get("/scan")
async def get_devices():
    return await bluetooth_service.scan_devices()

@router.get("/connect/{mac}")
async def connect_device(mac: str):
    success = await bluetooth_service.connect_device(mac_address=mac)
    return {"status": "connected" if success else "failed"}

@router.get("/paired-devices")
def paired_devices_list():
    try:
        devices =  bluetooth_service.get_known_devices()
        return devices
    except Exception as e:
        return {"status": "failed", "error": str(e)}

@router.get("/clean-cache")
def clean_cache():
    try:
        bluetooth_service.reset_bluetooth_cache()
        return {"status": "success"}
    except Exception as e:
        return {"status": "failed", "error": str(e)}
    
     
