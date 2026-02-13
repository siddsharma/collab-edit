from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, List
from datetime import datetime


class NoteCreate(BaseModel):
    """Schema for creating a note"""
    title: str = Field(..., min_length=1, max_length=500, description="Note title")
    
    @validator('title')
    def title_not_empty(cls, v):
        if not v.strip():
            raise ValueError('Title cannot be empty or whitespace only')
        return v.strip()


class NoteUpdate(BaseModel):
    """Schema for updating a note"""
    title: Optional[str] = Field(None, min_length=1, max_length=500, description="Note title")
    content: Optional[Dict[str, Any]] = Field(None, description="Note content as JSON")


class NoteResponse(BaseModel):
    """Schema for note response"""
    id: str
    title: str
    content: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NoteListResponse(BaseModel):
    """Schema for note list response"""
    id: str
    title: str
    updated_at: datetime

    class Config:
        from_attributes = True


class NoteVersionResponse(BaseModel):
    """Schema for note version response"""
    id: str
    note_id: str
    user_id: str
    delta: Dict[str, Any]
    timestamp: datetime

    class Config:
        from_attributes = True


class NoteVersionListItem(BaseModel):
    """Schema for note version list item"""
    id: str
    note_id: str
    user_id: str
    kind: str
    timestamp: datetime


class NoteVersionSnapshotResponse(BaseModel):
    """Schema for version snapshot response"""
    note_id: str
    version_id: str
    version_timestamp: datetime
    yjs_updates: List[str]


class NoteRestoreResponse(BaseModel):
    """Schema for restore response"""
    note_id: str
    restored_from_version_id: str
    restored_at: datetime


class ErrorResponse(BaseModel):
    """Schema for error responses"""
    detail: str
    status_code: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class HealthResponse(BaseModel):
    """Schema for health check response"""
    status: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
