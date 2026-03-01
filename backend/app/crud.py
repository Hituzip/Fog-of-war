from sqlalchemy.orm import Session
from sqlalchemy import text
import json
from geoalchemy2.shape import from_shape
from shapely.geometry import shape
from .models import Track, ExploredArea, User
from .utils.gpx import parse_gpx_to_linestring

def create_user(db: Session, email: str, hashed_password: str):
    user = User(email=email, hashed_password=hashed_password)
    db.add(user)
    db.commit()
    db.refresh(user)

    # Пустая explored_area по всему миру
    explored = ExploredArea(
        user_id=user.id,
        geom=text("ST_GeomFromText('MULTIPOLYGON EMPTY', 4326)")
    )
    db.add(explored)
    db.commit()
    return user

def create_track_and_update_explored(db: Session, user_id: int, linestring):
    track = Track(user_id=user_id, geom=from_shape(linestring, srid=4326))
    db.add(track)
    db.commit()

    stmt = text("""
        INSERT INTO explored_areas (user_id, geom)
        VALUES (:user_id, COALESCE(
            (SELECT ST_Union(e.geom, ST_Buffer(ST_GeomFromEWKT(:wkt)::geography, 15)::geometry)
             FROM explored_areas e WHERE e.user_id = :user_id),
            ST_Buffer(ST_GeomFromEWKT(:wkt)::geography, 15)::geometry
        ))
        ON CONFLICT (user_id) DO UPDATE SET geom = EXCLUDED.geom;
    """)
    db.execute(stmt, {"user_id": user_id, "wkt": f"SRID=4326;{linestring.wkt}"})
    db.commit()

def add_drawn_area(db: Session, user_id: int, geojson_geom):
    geom_shape = shape(geojson_geom)
    # Переводим любую фигуру (и линии, и полигоны) в формат строки EWKT
    wkt = f"SRID=4326;{geom_shape.wkt}"
    
    if geom_shape.geom_type == "LineString":
        # Для линий: превращаем в толстый след радиусом 15 метров
        stmt = text("""
            INSERT INTO explored_areas (user_id, geom, recent_draws)
            VALUES (
                :user_id, 
                COALESCE(
                    (SELECT ST_Union(e.geom, ST_Buffer(ST_GeomFromEWKT(:wkt)::geography, 15)::geometry)
                     FROM explored_areas e WHERE e.user_id = :user_id),
                    ST_Buffer(ST_GeomFromEWKT(:wkt)::geography, 15)::geometry
                ),
                COALESCE((SELECT e.recent_draws FROM explored_areas e WHERE e.user_id = :user_id), '[]'::jsonb) || CAST(:new_draw AS jsonb)
            )
            ON CONFLICT (user_id) DO UPDATE 
            SET geom = EXCLUDED.geom,
                recent_draws = EXCLUDED.recent_draws;
        """)
        db.execute(stmt, {"user_id": user_id, "wkt": wkt, "new_draw": json.dumps(geojson_geom)})
    
    else:
        # Для полигонов (прямоугольников): просто добавляем их площадь к открытой зоне
        stmt = text("""
            INSERT INTO explored_areas (user_id, geom, recent_draws)
            VALUES (
                :user_id, 
                COALESCE(
                    (SELECT ST_Union(e.geom, ST_GeomFromEWKT(:wkt)::geometry)
                     FROM explored_areas e WHERE e.user_id = :user_id),
                    ST_GeomFromEWKT(:wkt)::geometry
                ),
                COALESCE((SELECT e.recent_draws FROM explored_areas e WHERE e.user_id = :user_id), '[]'::jsonb) || CAST(:new_draw AS jsonb)
                )
                ON CONFLICT (user_id) DO UPDATE
                SET geom = EXCLUDED.geom,
                recent_draws = EXCLUDED.recent_draws;
                """)
        db.execute(stmt, {"user_id": user_id, "wkt": wkt, "new_draw": json.dumps(geojson_geom)})
    db.commit()

def undo_last_draw(db: Session, user_id: int):
    # Берем последний элемент из массива (recent_draws->-1)
    # Удаляем последний элемент из массива (recent_draws - -1)
    # И правильно вычитаем либо 15м буфер (для линии), либо сам полигон (для прямоугольника)
    stmt = text("""
        WITH last_draw AS (
            SELECT 
                (recent_draws->-1)::jsonb AS last_geom, 
                recent_draws - -1 AS new_list
            FROM explored_areas 
            WHERE user_id = :user_id AND jsonb_array_length(recent_draws) > 0
        )
        UPDATE explored_areas
        SET geom = ST_Difference(
                geom,
                CASE 
                    WHEN (SELECT last_geom->>'type' FROM last_draw) = 'LineString' THEN
                        ST_Buffer(ST_SetSRID(ST_GeomFromGeoJSON((SELECT last_geom FROM last_draw)::text), 4326)::geography, 15)::geometry
                    ELSE
                        ST_SetSRID(ST_GeomFromGeoJSON((SELECT last_geom FROM last_draw)::text), 4326)
                END
            ),
            recent_draws = (SELECT new_list FROM last_draw)
        WHERE user_id = :user_id AND EXISTS (SELECT 1 FROM last_draw);
    """)
    db.execute(stmt, {"user_id": user_id})
    db.commit()

def get_fog_by_bbox(db: Session, user_id: int, minx: float, miny: float, maxx: float, maxy: float):
    """Исправленная версия — возвращаем настоящий GeoJSON-объект"""
    result = db.execute(text("""
        WITH bbox AS (
            SELECT ST_MakeEnvelope(:minx, :miny, :maxx, :maxy, 4326) AS geom
        )
        SELECT ST_AsGeoJSON(
            CASE 
                WHEN ST_IsEmpty(
                    COALESCE(
                        (SELECT ST_Intersection(e.geom, b.geom) 
                         FROM explored_areas e 
                         WHERE e.user_id = :user_id),
                        ST_GeomFromText('MULTIPOLYGON EMPTY', 4326)
                    )
                ) 
                THEN b.geom
                ELSE ST_Difference(
                    b.geom,
                    COALESCE(
                        (SELECT ST_Intersection(e.geom, b.geom) 
                         FROM explored_areas e 
                         WHERE e.user_id = :user_id),
                        ST_GeomFromText('MULTIPOLYGON EMPTY', 4326)
                    )
                )
            END
        ) AS fog
        FROM bbox b
    """), {
        "minx": minx, "miny": miny, "maxx": maxx, "maxy": maxy,
        "user_id": user_id
    }).fetchone()

    # ←←← ГЛАВНОЕ ИСПРАВЛЕНИЕ
    try:
        fog_geo = json.loads(result.fog) if result and result.fog else {"type": "Polygon", "coordinates": []}
    except:
        fog_geo = {"type": "Polygon", "coordinates": []}

    return {"type": "Feature", "geometry": fog_geo, "properties": {}}

def save_last_viewport(db: Session, user_id: int, viewport: dict):
    stmt = text("""
        UPDATE explored_areas 
        SET last_viewport = :viewport 
        WHERE user_id = :user_id
    """)
    db.execute(stmt, {"user_id": user_id, "viewport": json.dumps(viewport)})
    db.commit()

def get_last_viewport(db: Session, user_id: int):
    result = db.execute(text("""
        SELECT last_viewport FROM explored_areas WHERE user_id = :user_id
    """), {"user_id": user_id}).fetchone()
    return result.last_viewport if result and result.last_viewport else None