import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Set
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
import firebase_admin
from firebase_admin import credentials, auth as firebase_auth
from socketio import ASGIApp
import socketio
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from db import engine, SessionLocal, Base, Note, NoteVersion
from config import settings
from logging_config import setup_logging
from models import NoteCreate, NoteUpdate, NoteResponse, NoteListResponse, ErrorResponse, HealthResponse

# Setup logging
logger = setup_logging()

# Initialize database
try:
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialized successfully")
except Exception as e:
    logger.error(f"Database initialization failed: {e}")
    raise

# Initialize Firebase from environment variables
firebase_initialized = False
try:
    if settings.firebase_project_id and settings.firebase_private_key:
        firebase_config = {
            "type": "service_account",
            "project_id": settings.firebase_project_id,
            "private_key_id": settings.firebase_private_key_id,
            "private_key": settings.firebase_private_key,
            "client_email": settings.firebase_client_email,
            "client_id": settings.firebase_client_id,
            "auth_uri": settings.firebase_auth_uri,
            "token_uri": settings.firebase_token_uri,
        }
        firebase_admin.initialize_app(credentials.Certificate(firebase_config))
        firebase_initialized = True
        logger.info("Firebase initialized successfully")
    else:
        logger.warning("Firebase credentials not provided. Some features may not work.")
except ValueError:
    # Firebase already initialized
    firebase_initialized = True
except Exception as e:
    logger.error(f"Firebase initialization failed: {e}")
    if settings.is_production():
        raise
    else:
        logger.warning("Continuing without Firebase in development mode")

# FastAPI app
app = FastAPI(
    title="Collaborative Notes API",
    description="A production-grade collaborative notes application",
    version="1.0.0",
)

# Rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.exception_handler(RateLimitExceeded)
async def rate_limit_exceeded_handler(request, exc):
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "detail": "Rate limit exceeded",
            "status_code": status.HTTP_429_TOO_MANY_REQUESTS,
        }
    )

# Socket.IO server
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=settings.get_cors_origins(),
    ping_timeout=60,
    ping_interval=25,
    logger=True,
    engineio_logger=True,
)

# Track active users per note
active_users: Dict[str, Set[str]] = {}
user_emails: Dict[str, str] = {}
sid_to_note: Dict[str, str] = {}
sid_to_user: Dict[str, str] = {}

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    """Dependency to get database session"""
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database session error: {e}")
        db.rollback()
        raise
    finally:
        db.close()

# Health check endpoints
@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health():
    """Health check endpoint"""
    logger.info("Health check requested")
    return {"status": "ok", "timestamp": datetime.utcnow()}

@app.get("/ready", tags=["Health"])
async def readiness(db: Session = Depends(get_db)):
    """Readiness check endpoint - verifies database connectivity"""
    try:
        db.execute("SELECT 1")
        logger.info("Readiness check passed")
        return {"status": "ready", "database": "connected", "firebase": "initialized" if firebase_initialized else "not_configured"}
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service not ready"
        )

# API v1 routes
@app.post("/notes", response_model=NoteResponse, status_code=status.HTTP_201_CREATED, tags=["Notes"], summary="Create a new note")
@limiter.limit("10/minute")
async def create_note(request: Request, note: NoteCreate, db: Session = Depends(get_db)):
    """Create a new note"""
    try:
        logger.info(f"Creating note with title: {note.title}")
        new_note = Note(
            title=note.title,
            content="",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(new_note)
        db.commit()
        db.refresh(new_note)
        logger.info(f"Note created successfully with ID: {new_note.id}")
        return new_note
    except SQLAlchemyError as e:
        logger.error(f"Database error creating note: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create note"
        )
    except Exception as e:
        logger.error(f"Unexpected error creating note: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred"
        )

@app.get("/notes", response_model=List[NoteListResponse], tags=["Notes"], summary="List all notes")
@limiter.limit("30/minute")
async def list_notes(request: Request, db: Session = Depends(get_db)):
    """List all notes"""
    try:
        logger.info("Listing all notes")
        notes = db.query(Note).order_by(Note.updated_at.desc()).all()
        logger.info(f"Found {len(notes)} notes")
        return notes
    except SQLAlchemyError as e:
        logger.error(f"Database error listing notes: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve notes"
        )
    except Exception as e:
        logger.error(f"Unexpected error listing notes: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred"
        )

@app.get("/notes/{note_id}", response_model=NoteResponse, tags=["Notes"], summary="Get a specific note")
@limiter.limit("30/minute")
async def get_note(request: Request, note_id: str, db: Session = Depends(get_db)):
    """Get a specific note"""
    try:
        logger.info(f"Retrieving note: {note_id}")
        note = db.query(Note).filter(Note.id == note_id).first()
        if not note:
            logger.warning(f"Note not found: {note_id}")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
        return note
    except SQLAlchemyError as e:
        logger.error(f"Database error retrieving note {note_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve note"
        )

@app.put("/notes/{note_id}", response_model=NoteResponse, tags=["Notes"], summary="Update a note")
@limiter.limit("20/minute")
async def update_note(request: Request, note_id: str, note_data: NoteUpdate, db: Session = Depends(get_db)):
    """Update a note"""
    try:
        logger.info(f"Updating note: {note_id}")
        note = db.query(Note).filter(Note.id == note_id).first()
        if not note:
            logger.warning(f"Note not found for update: {note_id}")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
        
        changed = False

        if note_data.title is not None and note_data.title != note.title:
            note.title = note_data.title
            changed = True

        if note_data.content is not None:
            current_content = None
            if note.content and note.content.strip():
                try:
                    current_content = json.loads(note.content)
                except (json.JSONDecodeError, ValueError):
                    current_content = note.content

            if current_content != note_data.content:
                note.content = json.dumps(note_data.content)
                changed = True

        if changed:
            note.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(note)

        logger.info(f"Note updated successfully: {note_id}")
        return note
    except SQLAlchemyError as e:
        logger.error(f"Database error updating note {note_id}: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update note"
        )

@app.delete("/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Notes"], summary="Delete a note")
@limiter.limit("10/minute")
async def delete_note(request: Request, note_id: str, db: Session = Depends(get_db)):
    """Delete a specific note"""
    try:
        logger.info(f"Deleting note: {note_id}")
        note = db.query(Note).filter(Note.id == note_id).first()
        if not note:
            logger.warning(f"Note not found for deletion: {note_id}")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
        
        # Delete associated versions
        db.query(NoteVersion).filter(NoteVersion.note_id == note_id).delete()
        
        # Delete the note
        db.delete(note)
        db.commit()
        logger.info(f"Note deleted successfully: {note_id}")
        return None
    except SQLAlchemyError as e:
        logger.error(f"Database error deleting note {note_id}: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete note"
        )

# Socket.IO Event Handlers
@sio.event
async def connect(sid, *args, **kwargs):
    """Handle client connection"""
    logger.info(f"Client connected: {sid}")
    await sio.emit("connect_response", {"data": "Connected to server"}, to=sid)

@sio.event
async def join_note(sid, data):
    """Handle joining a note room"""
    try:
        note_id = data.get("note_id")
        token = data.get("token")
        
        if not note_id or not token:
            logger.warning(f"Invalid join_note request from {sid}")
            await sio.emit("error", {"message": "Invalid request"}, to=sid)
            return
        
        # Verify token and get user info
        try:
            decoded_token = firebase_auth.verify_id_token(token)
            user_id = decoded_token.get("uid")
            user_email = decoded_token.get("email", "Anonymous")
            logger.info(f"User {user_email} joining note {note_id}")
        except Exception as e:
            logger.error(f"Token verification failed for {sid}: {e}")
            await sio.emit("error", {"message": "Authentication failed"}, to=sid)
            return
        
        # Add user to the note room
        sio.enter_room(sid, f"note_{note_id}")
        
        if note_id not in active_users:
            active_users[note_id] = set()
        
        active_users[note_id].add(user_id)
        user_emails[user_id] = user_email
        sid_to_note[sid] = note_id
        sid_to_user[sid] = user_id
        
        # Get the note content
        db = SessionLocal()
        try:
            note = db.query(Note).filter(Note.id == note_id).first()
            if note:
                # Parse content
                content = {"type": "doc", "content": [{"type": "paragraph"}]}
                if note.content and note.content.strip():
                    try:
                        content = json.loads(note.content)
                    except (json.JSONDecodeError, ValueError) as e:
                        logger.warning(f"JSON parse error for note {note_id}: {e}")

                # Build user_names mapping
                user_names = {uid: user_emails.get(uid, uid) for uid in active_users[note_id]}
                await sio.emit(
                    "load_note",
                    {
                        "content": content,
                        "title": note.title,
                        "active_users": list(active_users[note_id]),
                        "user_names": user_names,
                    },
                    to=sid,
                )

                # Notify others
                user_names = {uid: user_emails.get(uid, uid) for uid in active_users[note_id]}
                await sio.emit(
                    "user_joined",
                    {
                        "user_id": user_id,
                        "user_name": user_email,
                        "active_users": list(active_users[note_id]),
                        "user_names": user_names,
                    },
                    room=f"note_{note_id}",
                    skip_sid=sid,
                )
            else:
                logger.error(f"Note not found: {note_id}")
                await sio.emit("error", {"message": "Note not found"}, to=sid)
        finally:
            db.close()
        
    except Exception as e:
        logger.error(f"Error in join_note: {e}")
        await sio.emit("error", {"message": str(e)}, to=sid)

@sio.event
async def update_note(sid, data):
    """Handle note updates"""
    try:
        if not data or "delta" not in data:
            logger.warning(f"Invalid update_note request from {sid}")
            return
        
        note_id = data.get("note_id") or sid_to_note.get(sid)
        delta = data.get("delta")

        if not note_id:
            logger.warning(f"Missing note_id for update from {sid}")
            await sio.emit("error", {"message": "Missing note_id"}, to=sid)
            return

        if not isinstance(delta, dict):
            logger.warning(f"Invalid delta format from {sid}")
            await sio.emit("error", {"message": "Invalid note update payload"}, to=sid)
            return

        # Realtime fan-out only; persistence is handled by debounced HTTP autosave.
        await sio.emit(
            "note_updated",
            {"note_id": note_id, "content": delta},
            room=f"note_{note_id}",
            skip_sid=sid,
        )
        logger.debug(f"Realtime note update relayed for note {note_id} from {sid}")
    except Exception as e:
        logger.error(f"Error in update_note: {e}")

@sio.event
async def disconnect(sid):
    """Handle client disconnection"""
    try:
        logger.info(f"Client disconnected: {sid}")
        note_id = sid_to_note.pop(sid, None)
        user_id = sid_to_user.pop(sid, None)

        if note_id and user_id and note_id in active_users:
            active_users[note_id].discard(user_id)
            if not active_users[note_id]:
                del active_users[note_id]
            else:
                user_names = {uid: user_emails.get(uid, uid) for uid in active_users[note_id]}
                await sio.emit(
                    "user_left",
                    {
                        "user_id": user_id,
                        "active_users": list(active_users[note_id]),
                        "user_names": user_names,
                    },
                    room=f"note_{note_id}",
                )
    except Exception as e:
        logger.error(f"Error in disconnect: {e}")

# Global exception handler
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    logger.error(f"HTTP Exception: {exc.status_code} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "status_code": exc.status_code},
    )

# Wrap FastAPI app with Socket.IO
app = ASGIApp(sio, app)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )
