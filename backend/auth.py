import firebase_admin
from firebase_admin import auth as firebase_auth
from fastapi import HTTPException, Header
from typing import Optional

async def verify_firebase_token(authorization: Optional[str] = Header(None)):
    """Verify Firebase ID token from Authorization header"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization token")
    
    # Extract token from "Bearer <token>"
    try:
        token = authorization.split(" ")[1] if " " in authorization else authorization
    except IndexError:
        raise HTTPException(status_code=401, detail="Invalid authorization header format")
    
    try:
        decoded = firebase_auth.verify_id_token(token)
        return decoded
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")

