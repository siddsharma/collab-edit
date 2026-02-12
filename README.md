# Collaborative Notes - Production Grade Application

A full-stack collaborative notes application built with React, FastAPI, PostgreSQL, and real-time WebSocket sync.

## Features

✨ **Core Features**
- Real-time collaborative editing with WebSocket
- User authentication via Firebase
- Note management (create, read, update, delete)
- Active user tracking per note
- Rich text editing with TipTap
- Responsive UI with Vite + React

🔒 **Security & Production-Ready**
- Environment-based configuration
- Input validation with Pydantic
- Rate limiting on API endpoints
- Comprehensive error handling
- Structured logging with rotation
- CORS protection
- Firebase authentication integration

## Tech Stack

**Backend**
- FastAPI 0.104+ (async Python framework)
- PostgreSQL 15 (relational database)
- SQLAlchemy 2.0+ (ORM)
- Socket.IO (real-time communication)
- Pydantic (data validation)

**Frontend**
- React 18+ (UI framework)
- Vite (build tool)
- TipTap (rich text editor)
- Axios (HTTP client)
- Firebase Auth (authentication)

## Quick Start (Development)

### Prerequisites
- Docker & Docker Compose
- Node.js 18+ (for local frontend development)
- Python 3.9+ (for local backend development)
- Firebase project with service account credentials

### Setup

1. **Clone the repository**
```bash
git clone https://github.com/siddsharma/collab-edit.git
cd collab-edit
```

2. **Configure environment variables**
```bash
# Backend
cp backend/.env.example backend/.env
# Edit backend/.env with your Firebase credentials

# Frontend
cp frontend/.env.example frontend/.env
# Edit frontend/.env with your Firebase config
```

3. **Start the application**
```bash
docker compose up --build
```

The app will be available at:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

## Environment Variables

### Backend (.env)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | - | PostgreSQL connection string |
| `FIREBASE_PROJECT_ID` | Yes | - | Firebase project ID |
| `FIREBASE_PRIVATE_KEY` | Yes | - | Firebase service account private key |
| `FIREBASE_CLIENT_EMAIL` | Yes | - | Firebase service account email |
| `FIREBASE_CLIENT_ID` | Yes | - | Firebase client ID |
| `ENVIRONMENT` | No | development | Environment: development, staging, production |
| `DEBUG` | No | false | Enable debug mode |
| `LOG_LEVEL` | No | INFO | Logging level: DEBUG, INFO, WARNING, ERROR |
| `ALLOWED_ORIGINS` | No | http://localhost:3000,http://localhost | Comma-separated CORS origins |

### Frontend (.env)

```
VITE_API_URL=http://localhost:8000
VITE_SOCKET_URL=http://localhost:8000
VITE_FIREBASE_API_KEY=...
VITE_FIREBASE_AUTH_DOMAIN=...
VITE_FIREBASE_PROJECT_ID=...
VITE_FIREBASE_STORAGE_BUCKET=...
VITE_FIREBASE_MESSAGING_SENDER_ID=...
VITE_FIREBASE_APP_ID=...
```

## API Endpoints

### Health Checks
- `GET /health` - Basic health check
- `GET /ready` - Readiness check with database verification

### Notes CRUD
- `POST /notes` - Create a new note (rate limited: 10/min)
- `GET /notes` - List all notes (rate limited: 30/min)
- `GET /notes/{note_id}` - Get specific note (rate limited: 30/min)
- `PUT /notes/{note_id}` - Update note (rate limited: 20/min)
- `DELETE /notes/{note_id}` - Delete note (rate limited: 10/min)

**API Documentation**: Visit `/docs` for interactive Swagger UI

## Database Schema

### notes table
```sql
id          VARCHAR PRIMARY KEY
title       VARCHAR (indexed)
content     TEXT (JSON format)
created_at  TIMESTAMP
updated_at  TIMESTAMP
```

### note_versions table
```sql
id          VARCHAR PRIMARY KEY
note_id     VARCHAR (indexed)
user_id     VARCHAR
delta       TEXT (JSON format)
timestamp   TIMESTAMP
```

## Production Deployment

### Docker Build

```bash
# Build production images
docker compose build

# Start in production mode
docker compose -p collab-prod up -d
```

### Environment-Specific Settings

**Development**
```bash
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=DEBUG
```

**Production**
```bash
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=WARNING
ALLOWED_ORIGINS=https://yourdomain.com
```

## Logging

Logs are configured with rotation and stored in the `logs/` directory:

- `logs/app_YYYYMMDD.log` - Application logs
- `logs/errors_YYYYMMDD.log` - Error logs only

Log rotation happens automatically at 10MB per file.

## Rate Limiting

API endpoints are protected with rate limiting:

- Note creation: 10 requests/minute
- Note listing/retrieval: 30 requests/minute
- Note updates: 20 requests/minute
- Note deletion: 10 requests/minute

Rate limit exceeded returns **HTTP 429** with message.

## Error Handling

All errors are standardized with status codes:

```json
{
  "detail": "Error message",
  "status_code": 404
}
```

Common status codes:
- `400` - Bad Request (validation error)
- `401` - Unauthorized (authentication failed)
- `404` - Not Found
- `429` - Too Many Requests (rate limited)
- `500` - Internal Server Error
- `503` - Service Unavailable

## Security Best Practices

✅ **Implemented**
- Environment-based secrets management
- Input validation with Pydantic
- Rate limiting on all public endpoints
- CORS protection with configurable origins
- Firebase authentication
- SQL injection prevention via ORM
- Structured logging for audit trails
- Error handling without exposing internals

🔐 **Recommended for Production**
- Use HTTPS/TLS with valid certificates
- Use managed PostgreSQL with SSL
- Implement API authentication tokens
- Set up monitoring and alerting
- Enable database backups and replication
- Use secrets management (AWS Secrets Manager, HashiCorp Vault)
- Enable audit logging
- Set up WAF (Web Application Firewall)

## Monitoring

### Health Checks
```bash
# Basic health
curl http://localhost:8000/health

# Detailed readiness
curl http://localhost:8000/ready
```

### Logging
Monitor application and error logs:
```bash
tail -f logs/app_*.log
tail -f logs/errors_*.log
```

## Troubleshooting

### Database Connection Issues
```bash
# Check database connectivity
docker exec collab-edit-db-1 psql -U collab-svc-user -d collaborative_notes -c "SELECT 1"
```

### Firebase Authentication Issues
- Verify Firebase service account credentials are correct
- Check Firebase project ID matches configuration
- Ensure FIREBASE_PRIVATE_KEY has proper formatting with newlines

## Contributing

1. Create a feature branch (`git checkout -b feature/amazing-feature`)
2. Commit your changes (`git commit -m 'Add amazing feature'`)
3. Push to the branch (`git push origin feature/amazing-feature`)
4. Open a Pull Request

## License

This project is licensed under the MIT License.
