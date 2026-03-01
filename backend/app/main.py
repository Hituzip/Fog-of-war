from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy import text
from .database import engine, get_db
from .models import Base
from .routers.auth import router as auth_router
from .routers.map import router as map_router
from .routers.viewport import router as viewport_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Автоматическая инициализация базы ПРИ ПЕРВОМ ЗАПУСКЕ КОНТЕЙНЕРА
    db = next(get_db())
    Base.metadata.create_all(bind=engine)
    try:
        # Включаем PostGIS
        db.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
        db.execute(text("""
            ALTER TABLE explored_areas 
            ADD COLUMN IF NOT EXISTS last_viewport JSONB,
            ADD COLUMN IF NOT EXISTS recent_draws JSONB DEFAULT '[]';
        """))
        db.commit()
        print("✅ PostGIS extension enabled")

        # Создаём все таблицы (users, tracks, explored_areas)
        Base.metadata.create_all(bind=engine)
        print("✅ All tables created successfully")
    except Exception as e:
        print(f"⚠️ DB init warning: {e}")
    finally:
        db.close()

    yield  # приложение работает


app = FastAPI(lifespan=lifespan, title="Fog of War Map v2 — весь мир")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api", tags=["auth"])
app.include_router(map_router, prefix="/api", tags=["map"])
app.include_router(viewport_router, prefix="/api", tags=["viewport"])