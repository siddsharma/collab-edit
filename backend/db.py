from sqlalchemy import create_engine, Column, String, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os
from dotenv import load_dotenv
import uuid

load_dotenv()

# Database URL
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://noteuser:notepass@db:5432/collaborative_notes"
)

# Create engine
engine = create_engine(DATABASE_URL, echo=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class Note(Base):
    __tablename__ = "notes"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String, index=True)
    content = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class NoteVersion(Base):
    """Store version history for collaborative editing"""
    __tablename__ = "note_versions"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    note_id = Column(String, index=True)
    user_id = Column(String)
    delta = Column(Text)  # JSON delta
    timestamp = Column(DateTime, default=datetime.utcnow)
