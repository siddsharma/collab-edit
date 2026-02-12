# Collaborative Note Editing Web App

A real-time collaborative note editing application with Firebase authentication, WebSocket support for live updates, and rich text editing.

## Tech Stack

### Frontend
- **React 18** - UI framework
- **Vite** - Build tool
- **TipTap** - Rich text editor
- **Socket.io-client** - WebSocket client
- **Firebase** - Authentication
- **Yjs** - CRDT for collaborative editing (ready to integrate)

### Backend
- **FastAPI** - Python web framework
- **python-socketio** - WebSocket support
- **SQLAlchemy** - ORM
- **PostgreSQL** - Database
- **Firebase Admin SDK** - Token verification

### Deployment
- **Docker** - Containerization
- **Docker Compose** - Multi-container orchestration

## Features

✅ User authentication with Firebase  
✅ Create and list notes  
✅ Real-time collaborative editing  
✅ Show active users editing a note  
✅ Rich text editing with TipTap  
✅ Persistent PostgreSQL database  
✅ WebSocket support for live updates  
✅ Fully Dockerized

## Setup Instructions

### Prerequisites
- Docker and Docker Compose installed
- Firebase project created with authentication enabled
- Node.js 18+ (for local development without Docker)
- Python 3.11+ (for local development without Docker)

### 1. Configure Firebase

1. Create a Firebase project at [firebase.google.com](https://firebase.google.com)
2. Enable Google Sign-in authentication
3. Get your Firebase credentials:
   - Go to Project Settings → Service Accounts
   - Generate a new private key (JSON)
   - Save as `backend/firebase-key.json`
4. Get your web app credentials:
   - Go to Project Settings → Your apps
   - Copy the config object

### 2. Environment Setup

**Backend (.env):**
```bash
cd backend
cp .env.example .env
# Edit .env with your Firebase credentials
```

**Frontend (.env):**
```bash
cd frontend
cp .env.example .env
# Edit .env with your Firebase web config
```

### 3. Run with Docker Compose

```bash
# From project root
docker-compose up -d
```

Access the app at `http://localhost:3000`

### 4. Local Development (without Docker)

**Backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:async_app --reload
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

## Project Structure

```
.
├── backend/                 # FastAPI application
│   ├── main.py             # FastAPI app + Socket.io handlers
│   ├── auth.py             # Firebase verification
│   ├── db.py               # Database models
│   ├── requirements.txt     # Python dependencies
│   ├── Dockerfile          # Backend Docker image
│   └── .env.example        # Environment template
│
├── frontend/               # React application
│   ├── src/
│   │   ├── App.jsx         # Main app component
│   │   ├── main.jsx        # Entry point
│   │   ├── firebaseConfig.js  # Firebase setup
│   │   ├── components/
│   │   │   ├── Login.jsx   # Firebase login
│   │   │   ├── NoteList.jsx # Notes list
│   │   │   ├── Editor.jsx  # Rich text editor with WebSocket
│   │   │   └── ActiveUsers.jsx  # Show active editors
│   │   └── styles/         # CSS files
│   ├── public/
│   ├── index.html          # HTML entry point
│   ├── package.json        # Node dependencies
│   ├── vite.config.js      # Vite config
│   ├── Dockerfile          # Frontend Docker image
│   └── .env.example        # Environment template
│
├── docker-compose.yml      # Container orchestration
└── README.md              # This file
```

## API Endpoints

### REST API
- `GET /health` - Health check
- `POST /notes?title=<title>` - Create new note
- `GET /notes` - List all notes
- `GET /notes/{note_id}` - Get note content

### WebSocket Events

**Client → Server:**
- `join_note` - Join a note editing session
  ```json
  {
    "token": "firebase-id-token",
    "note_id": "note-uuid"
  }
  ```
- `update_note` - Send content updates
  ```json
  {
    "delta": { /* editor state */ }
  }
  ```
- `cursor_move` - Send cursor position
  ```json
  {
    "position": { "line": 5, "ch": 10 }
  }
  ```

**Server → Client:**
- `user_joined` - User joined the editing session
- `user_left` - User left the session
- `note_updated` - Received content update from another user
- `cursor_updated` - Cursor position from another user

## Next Steps to Production

1. **Conflict Resolution**: Integrate Yjs for CRDT-based conflict-free collaborative editing
2. **Real-time Sync**: Implement Yjs WebSocket provider for better sync
3. **User Presence**: Add cursor tracking and selection awareness
4. **Permissions**: Add note sharing and access control
5. **Offline Support**: Implement offline editing with sync on reconnect
6. **Version History**: Add undo/redo and version history
7. **Search**: Add full-text search for notes
8. **Export**: Add export to PDF/Word formats
9. **Security**: Add HTTPS, sanitize inputs, add rate limiting
10. **Monitoring**: Add logging, error tracking, and analytics

## Troubleshooting

**Database connection error:**
- Ensure PostgreSQL container is running: `docker-compose ps`
- Check database credentials in `.env`

**Firebase auth errors:**
- Verify Firebase key file is in `backend/firebase-key.json`
- Ensure Firebase project has Google Sign-in enabled

**WebSocket connection timeout:**
- Check backend is running on port 8000
- Verify CORS settings allow frontend origin

## License

MIT
