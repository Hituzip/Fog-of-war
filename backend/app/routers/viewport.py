from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..auth import get_current_user
from ..crud import save_last_viewport, get_last_viewport

router = APIRouter()

@router.post("/viewport")
async def save_viewport(data: dict, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    save_last_viewport(db, current_user.id, data)
    return {"status": "ok"}

@router.get("/viewport")
async def get_viewport(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return get_last_viewport(db, current_user.id)