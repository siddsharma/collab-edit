import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Set, Any
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
from models import (
    NoteCreate,
    NoteUpdate,
    NoteResponse,
    NoteListResponse,
    NoteVersionListItem,
    NoteVersionSnapshotResponse,
    NoteRestoreResponse,
    NoteRestoreRequest,
    ErrorResponse,
    HealthResponse,
)

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


def _parse_version_delta(delta_raw: str) -> Dict[str, Any]:
    try:
        payload = json.loads(delta_raw)
        if isinstance(payload, dict):
            return payload
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    return {}


def _get_note_or_404(db: Session, note_id: str) -> Note:
    note = db.query(Note).filter(Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    return note


def _get_note_version_or_404(db: Session, note_id: str, version_id: str) -> NoteVersion:
    version = (
        db.query(NoteVersion)
        .filter(NoteVersion.note_id == note_id, NoteVersion.id == version_id)
        .first()
    )
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")
    return version


def _extract_yjs_updates(versions: List[NoteVersion]) -> List[str]:
    updates: List[str] = []
    for version in versions:
        payload = _parse_version_delta(version.delta)
        if payload.get("kind") == "yjs_update" and payload.get("update"):
            updates.append(str(payload["update"]))
    return updates


@app.get(
    "/notes/{note_id}/versions",
    response_model=List[NoteVersionListItem],
    tags=["Notes"],
    summary="List note versions",
)
@limiter.limit("30/minute")
async def list_note_versions(request: Request, note_id: str, limit: int = 100, db: Session = Depends(get_db)):
    """List recent versions for a note."""
    try:
        _get_note_or_404(db, note_id)

        safe_limit = max(1, min(limit, 500))
        versions = (
            db.query(NoteVersion)
            .filter(NoteVersion.note_id == note_id)
            .order_by(NoteVersion.timestamp.desc())
            .limit(safe_limit)
            .all()
        )

        response_items = []
        for version in versions:
            payload = _parse_version_delta(version.delta)
            response_items.append(
                NoteVersionListItem(
                    id=version.id,
                    note_id=version.note_id,
                    user_id=version.user_id,
                    user_name=str(payload.get("user_name") or version.user_id),
                    kind=str(payload.get("kind") or "unknown"),
                    timestamp=version.timestamp,
                )
            )
        return response_items
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(f"Database error listing versions for note {note_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list note versions",
        )


@app.get(
    "/notes/{note_id}/versions/{version_id}",
    response_model=NoteVersionSnapshotResponse,
    tags=["Notes"],
    summary="Get note snapshot at a specific version",
)
@limiter.limit("30/minute")
async def get_note_version_snapshot(
    request: Request,
    note_id: str,
    version_id: str,
    db: Session = Depends(get_db),
):
    """Return all Yjs updates required to reconstruct a note at version timestamp."""
    try:
        _get_note_or_404(db, note_id)
        target_version = _get_note_version_or_404(db, note_id, version_id)

        prior_versions = (
            db.query(NoteVersion)
            .filter(
                NoteVersion.note_id == note_id,
                NoteVersion.timestamp <= target_version.timestamp,
            )
            .order_by(NoteVersion.timestamp.asc())
            .all()
        )

        yjs_updates = _extract_yjs_updates(prior_versions)

        return NoteVersionSnapshotResponse(
            note_id=note_id,
            version_id=target_version.id,
            version_timestamp=target_version.timestamp,
            yjs_updates=yjs_updates,
        )
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(f"Database error loading version snapshot {version_id} for note {note_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load version snapshot",
        )


@app.post(
    "/notes/{note_id}/versions/{version_id}/restore",
    response_model=NoteRestoreResponse,
    tags=["Notes"],
    summary="Mark a note as restored from a specific version",
)
@limiter.limit("20/minute")
async def restore_note_version(
    request: Request,
    note_id: str,
    version_id: str,
    restore_data: NoteRestoreRequest,
    db: Session = Depends(get_db),
):
    """Record a restore action for note history/audit."""
    try:
        note = _get_note_or_404(db, note_id)
        _get_note_version_or_404(db, note_id, version_id)

        restored_at = datetime.utcnow()
        restore_user_id = restore_data.user_id or "system"
        restore_user_name = restore_data.user_name or restore_user_id
        restore_event = NoteVersion(
            note_id=note_id,
            user_id=restore_user_id,
            delta=json.dumps(
                {
                    "kind": "restore",
                    "target_version_id": version_id,
                    "user_name": restore_user_name,
                }
            ),
            timestamp=restored_at,
        )
        note.updated_at = restored_at
        db.add(restore_event)
        db.commit()

        return NoteRestoreResponse(
            note_id=note_id,
            restored_from_version_id=version_id,
            restored_at=restored_at,
        )
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error restoring version {version_id} for note {note_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to restore note version",
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

                # Replay all persisted incremental Yjs updates for this note.
                # We currently do not materialize Yjs state into notes.content snapshots.
                # Filtering by note.updated_at can drop updates and cause data loss on reload.
                updates_query = db.query(NoteVersion).filter(NoteVersion.note_id == note_id)
                yjs_updates = _extract_yjs_updates(
                    updates_query.order_by(NoteVersion.timestamp.asc()).all()
                )

                # Build user_names mapping
                user_names = {uid: user_emails.get(uid, uid) for uid in active_users[note_id]}
                await sio.emit(
                    "load_note",
                    {
                        "content": content,
                        "yjs_updates": yjs_updates,
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
async def yjs_update(sid, data):
    """Relay incremental Yjs updates to other clients in the same note room."""
    try:
        if not data or "update" not in data:
            logger.warning(f"Invalid yjs_update request from {sid}")
            return

        note_id = data.get("note_id") or sid_to_note.get(sid)
        update_payload = data.get("update")

        if not note_id:
            logger.warning(f"Missing note_id for yjs_update from {sid}")
            await sio.emit("error", {"message": "Missing note_id"}, to=sid)
            return

        if not isinstance(update_payload, str) or not update_payload:
            logger.warning(f"Invalid yjs update payload from {sid}")
            await sio.emit("error", {"message": "Invalid yjs update payload"}, to=sid)
            return

        # Persist incremental update for replay until next snapshot autosave.
        db = SessionLocal()
        try:
            note = db.query(Note).filter(Note.id == note_id).first()
            if not note:
                logger.warning(f"Note not found for yjs_update: {note_id}")
                await sio.emit("error", {"message": "Note not found"}, to=sid)
                return

            user_id = sid_to_user.get(sid, "unknown")
            user_name = user_emails.get(user_id, user_id)
            delta_payload = json.dumps(
                {"kind": "yjs_update", "update": update_payload, "user_name": user_name}
            )
            last_version = (
                db.query(NoteVersion)
                .filter(NoteVersion.note_id == note_id)
                .order_by(NoteVersion.timestamp.desc())
                .first()
            )

            # Skip duplicate consecutive updates to limit replay-log bloat.
            if last_version and last_version.delta == delta_payload:
                await sio.emit(
                    "yjs_update",
                    {"note_id": note_id, "update": update_payload},
                    room=f"note_{note_id}",
                    skip_sid=sid,
                )
                logger.debug(f"Relayed duplicate Yjs update without persisting for note {note_id}")
                return

            version = NoteVersion(
                note_id=note_id,
                user_id=user_id,
                delta=delta_payload,
                timestamp=datetime.utcnow(),
            )
            db.add(version)
            db.commit()
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error persisting yjs_update for {note_id}: {e}")
            await sio.emit("error", {"message": "Failed to persist yjs update"}, to=sid)
            return
        finally:
            db.close()

        await sio.emit(
            "yjs_update",
            {"note_id": note_id, "update": update_payload},
            room=f"note_{note_id}",
            skip_sid=sid,
        )
        logger.debug(f"Relayed Yjs update for note {note_id} from {sid}")
    except Exception as e:
        logger.error(f"Error in yjs_update: {e}")

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
fastapi_app = app
app = ASGIApp(sio, fastapi_app)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )
