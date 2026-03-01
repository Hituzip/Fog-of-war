from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query
from sqlalchemy.orm import Session
from fastapi.responses import JSONResponse

from app.database import get_db
from app.auth import get_current_user
from app.crud import create_track_and_update_explored, add_drawn_area, get_fog_by_bbox, undo_last_draw
from app.utils.gpx import parse_gpx_to_linestring
from app.schemas import GeoJSONGeometry

router = APIRouter()

@router.post("/upload-gpx")
async def upload_gpx(file: UploadFile = File(...), db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if not file.filename.lower().endswith(".gpx"):
        raise HTTPException(400, "Only .gpx files allowed")
    content = await file.read()
    try:
        linestring = parse_gpx_to_linestring(content)
        create_track_and_update_explored(db, current_user.id, linestring)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(400, f"GPX error: {str(e)}")

@router.post("/draw")
async def draw(geojson: GeoJSONGeometry, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    try:
        add_drawn_area(db, current_user.id, geojson.dict())
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(400, str(e))

@router.get("/fog")
async def get_fog(
    minx: float = Query(...),
    miny: float = Query(...),
    maxx: float = Query(...),
    maxy: float = Query(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    fog = get_fog_by_bbox(db, current_user.id, minx, miny, maxx, maxy)
    return JSONResponse(content=fog)

@router.post("/draw/undo")
async def undo(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    undo_last_draw(db, current_user.id)
    return {"status": "ok"}