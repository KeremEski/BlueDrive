import asyncio
from fastapi import APIRouter, WebSocket, HTTPException, status, Depends
from app.services.wifi_service import WifiService
from app.containers.service_container import wifi_service
from app.models.schemas import WifiCredentials

router = APIRouter(prefix="/wifi", tags=["Wifi Service"])
service = wifi_service

@router.get("/scan")
async def scan_networks():
    try:
        return wifi_service.scan_networks()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/connect")
async def connect(request: WifiCredentials):
    try:
        success = wifi_service.connect(request.ssid, request.password)
        if success:
            return {"status": "connected", "ssid": request.ssid}
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Connection failed"
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    except ConnectionError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/disconnect")
async def disconnect():
    try:
        success = wifi_service.disconnect()
        if success:
            return {"status": "disconnected"}
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Disconnection failed"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/status")
async def get_status():
    try:
        return wifi_service.get_wifi_status()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/current-connection")
async def current_connection():
    try:
        connection = wifi_service.get_current_connection()
        if connection:
            return connection
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not connected to any network"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.websocket("/ws/scan")
async def websocket_scan(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            networks = wifi_service.scan_networks()
            await websocket.send_json(networks)
            await asyncio.sleep(10)  # 10 saniyede bir güncelle
    except Exception as e:
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR)

    
     
