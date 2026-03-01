from sqlalchemy import Column, Integer, String, ForeignKey, Index
from geoalchemy2 import Geometry
from sqlalchemy.dialects.postgresql import JSONB   # ← ЭТО ОБЯЗАТЕЛЬНО
from .database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)

class Track(Base):
    __tablename__ = "tracks"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    geom = Column(Geometry("LINESTRING", srid=4326), nullable=False)
    __table_args__ = (Index("ix_track_geom", "geom", postgresql_using="gist"),)

class ExploredArea(Base):
    __tablename__ = "explored_areas"
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    geom = Column(Geometry("MULTIPOLYGON", srid=4326), nullable=False)
    
    # Новые поля
    last_viewport = Column(JSONB, nullable=True)           # последнее место + зум
    recent_draws = Column(JSONB, nullable=True, server_default="[]")  # для отмены

    __table_args__ = (Index("ix_explored_geom", "geom", postgresql_using="gist"),)