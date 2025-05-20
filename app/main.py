import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.services.service_container import hfp_service

from app.controllers import bluetooth_controller, media_controller, ws_controller,hfp_controller

# Lifespan context

@asynccontextmanager
async def lifespan(app: FastAPI):
    hfp_service.start()
    try:
        yield
    except asyncio.CancelledError:
        print("🛑 Lifespan iptal edildi")
    finally:
        hfp_service.stop()

""" @asynccontextmanager
async def lifespan(app: FastAPI):
    bluetooth_service = BluetoothService()
    time.sleep(2)  # ⏳ Başlangıçta biraz bekle
    await bluetooth_service.auto_connect_paired_devices()  # ✅ Başlangıçta otomatik bağlan
    yield  # ⬅️ Burada uygulama çalışır
    # (isteğe bağlı) kapanış işlemleri yapılabilir  """

# FastAPI uygulaması oluşturulurken lifespan veriyoruz
app = FastAPI(
    title="Araba Multimedya API",
    description="Bluetooth AVRCP ve Spotify üzerinden medya servisi",
    version="1.0.0",
    lifespan=lifespan  # ✅ burada lifespan tanımlanıyor
)

# CORS ayarları
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Route'lar
app.include_router(hfp_controller.router)
app.include_router(media_controller.router)
app.include_router(bluetooth_controller.router)
app.include_router(ws_controller.router)

# sudo env PATH=$PATH uvicorn app.main:app --reload