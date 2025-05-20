from fastapi import APIRouter
from app.services.service_container import hfp_service

router = APIRouter(prefix="/hfp", tags=["HandsFreeProfile"])
service = hfp_service 

@router.get("/hangup-call")
def reject_call():
    service.hangup_all()

@router.get("/answer-call")
def accept_call():
    service.answer_call()

