from fastapi import APIRouter, Depends
from app.services.media_service import MediaService

router = APIRouter(prefix="/media", tags=["Media"])

@router.get("/metadata")
def get_metadata():
    media_service = MediaService()
    return media_service.get_metadata()

@router.get("/spotify-metadata")
def get_spotify_metadata():
    media_service = MediaService()
    return media_service.get_spotify_metadata()

@router.get("/next")
def next_music():
    service = MediaService()
    return service.next()

@router.get("/previous")
def previous_music():
    service = MediaService()
    return service.previous()

@router.get("/toggle")
def toggle_music():
    service = MediaService()
    return service.toggle_playback()
