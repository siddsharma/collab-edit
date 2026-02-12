import os
import json
from datetime import datetime
from typing import Dict, List, Set
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.wsgi import WSGIMiddleware
from sqlalchemy.orm import Session
import firebase_admin
from firebase_admin import credentials, auth as firebase_auth
from dotenv import load_dotenv
from socketio import ASGIApp
import socketio

from db import engine, SessionLocal, Base, Note, NoteVersion
from auth import verify_firebase_token
import uvicorn

load_dotenv()

# Initialize database
Base.metadata.create_all(bind=engine)

# Initialize Firebase from environment variables
try:
    firebase_config = {
        "type": "service_account",
        "project_id": os.getenv("FIREBASE_PROJECT_ID"),
        "private_key_id": os.getenv("FIREBASE_PRIVATE_KEY_ID"),
        "private_key": os.getenv("FIREBASE_PRIVATE_KEY"),
        "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
        "client_id": os.getenv("FIREBASE_CLIENT_ID"),
        "auth_uri": os.getenv("FIREBASE_AUTH_URI", "https://accounts.google.com/o/oauth2/auth"),
        "token_uri": os.getenv("FIREBASE_TOKEN_URI", "https://oauth2.googleapis.com/token"),
    }
    firebase_admin.initialize_app(credentials.Certificate(firebase_config))
except ValueError:
    # Firebase already initialized
    pass
except Exception as e:
    print(f"Warning: Firebase initialization failed: {e}")
    print("Some features may not work without Firebase credentials")

# FastAPI app
app = FastAPI(title="Collaborative Notes API")

# Socket.IO server
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=[
        "http://localhost:3000",
        "http://localhost",
        "http://127.0.0.1:3000",
        "http://127.0.0.1",
        "*",
    ],
    ping_timeout=60,
    ping_interval=25,
)

# Track active users per note
active_users: Dict[str, Set[str]] = {}
user_info: Dict[str, Dict] = {}
# Track user_id to email mapping for active users
user_emails: Dict[str, str] = {}

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/notes")
async def create_note(title: str, db: Session = Depends(get_db)):
    """Create a new note"""
    note = Note(
        title=title,
        content="",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return {"id": note.id, "title": note.title, "content": note.content}

@app.get("/notes")
async def list_notes(db: Session = Depends(get_db)):
    """List all notes"""
    notes = db.query(Note).all()
    return [{"id": n.id, "title": n.title, "updated_at": n.updated_at} for n in notes]

@app.get("/notes/{note_id}")
async def get_note(note_id: str, db: Session = Depends(get_db)):
    """Get a specific note"""
    note = db.query(Note).filter(Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return {
        "id": note.id,
        "title": note.title,
        "content": note.content,
        "created_at": note.created_at,
        "updated_at": note.updated_at,
    }

@app.delete("/notes/{note_id}")
async def delete_note(note_id: str, db: Session = Depends(get_db)):
    """Delete a specific note"""
    note = db.query(Note).filter(Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    
    # Delete associated versions
    db.query(NoteVersion).filter(NoteVersion.note_id == note_id).delete()
    
    # Delete the note
    db.delete(note)
    db.commit()
    
    return {"message": "Note deleted successfully"}

# Socket.IO Event Handlers
@sio.event
async def connect(sid, *args, **kwargs):
    """Handle client connection"""
    print(f"Client {sid} connected")
    await sio.emit("connect_response", {"data": "Connected to server"}, to=sid)

@sio.event
async def join_note(sid, data):
    """Handle joining a note room"""
    try:
        note_id = data.get("note_id")
        token = data.get("token")
        
        # Verify token and get user info
        try:
            decoded_token = firebase_auth.verify_id_token(token)
            user_id = decoded_token.get("uid")
            user_email = decoded_token.get("email", "Anonymous")
        except Exception as e:
            print(f"Token verification failed: {e}")
            await sio.emit("error", {"message": "Authentication failed"}, to=sid)
            return
        
        # Add user to the note room
        sio.enter_room(sid, f"note_{note_id}")
        
        if note_id not in active_users:
            active_users[note_id] = set()
        
        active_users[note_id].add(user_id)
        user_emails[user_id] = user_email
        user_info[sid] = {
            "user_id": user_id,
            "user_email": user_email,
            "note_id": note_id,
        }
        
        # Get the note content
        db = SessionLocal()
        try:
            note = db.query(Note).filter(Note.id == note_id).first()
            if note:
                # Parse content - if empty or can't parse, use default
                content = {"type": "doc", "content": [{"type": "paragraph"}]}
                if note.content and note.content.strip():
                    try:
                        content = json.loads(note.content)
                    except (json.JSONDecodeError, ValueError) as e:
                        print(f"JSON parse error: {e}")
                        content = {"type": "doc", "content": [{"type": "paragraph"}]}

                # Emit note content and active users to the joining user
                # Build user_names mapping for all active users
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

                # Notify others that a user joined
                # Build user_names mapping for all active users
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
        finally:
            db.close()
        
        print(f"User {user_email} joined note {note_id}")
        
    except Exception as e:
        print(f"Error in join_note: {e}")
        await sio.emit("error", {"message": str(e)}, to=sid)

@sio.event
async def update_note(sid, data):
    """Handle note updates"""
    try:
        if sid not in user_info:
            await sio.emit("error", {"message": "Not in a note room"}, to=sid)
            return
        
        user_info_data = user_info[sid]
        note_id = user_info_data["note_id"]
        user_id = user_info_data["user_id"]
        
        # Update the note in database
        db = SessionLocal()
        try:
            note = db.query(Note).filter(Note.id == note_id).first()
            if note:
                # Get the delta from the update
                if "delta" in data:
                    delta = data["delta"]
                    # Store as JSON string in database
                    note.content = json.dumps(delta)
                    note.updated_at = datetime.utcnow()
                    db.commit()

                    # Broadcast the delta object to other users
                    await sio.emit(
                        "note_updated",
                        {
                            "user_id": user_id,
                            "content": delta,  # Send as object, not string
                            "updated_at": note.updated_at.isoformat(),
                        },
                        room=f"note_{note_id}",
                        skip_sid=sid,
                    )
        finally:
            db.close()
            
    except Exception as e:
        print(f"Error in update_note: {e}")
        await sio.emit("error", {"message": str(e)}, to=sid)

@sio.event
async def disconnect(sid):
    """Handle client disconnection"""
    try:
        if sid in user_info:
            user_data = user_info.pop(sid)
            note_id = user_data["note_id"]
            user_id = user_data["user_id"]
            
            if note_id in active_users:
                active_users[note_id].discard(user_id)

                # Clean up user email if no longer active in any note
                if not any(user_id in users for users in active_users.values()):
                    user_emails.pop(user_id, None)

                # Notify other users that someone left
                if active_users[note_id]:
                    # Build user_names mapping for remaining active users
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
                else:
                    # Clean up empty rooms
                    active_users.pop(note_id, None)
            
            print(f"User {user_id} disconnected from note {note_id}")
    except Exception as e:
        print(f"Error in disconnect: {e}")

# Wrap FastAPI app with Socket.IO
app = ASGIApp(sio, app)
