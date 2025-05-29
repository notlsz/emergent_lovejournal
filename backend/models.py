"""
Pydantic models for Que Bella AI Couples Love Journal
"""
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import date, datetime
import uuid

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Profile(BaseModel):
    id: uuid.UUID
    email: str
    full_name: Optional[str] = None
    invite_code: Optional[str] = None
    partner_id: Optional[uuid.UUID] = None
    allow_read_receipts: bool = True
    created_at: datetime
    updated_at: datetime

class JournalEntryCreate(BaseModel):
    content: str
    date: date
    mood: Optional[str] = None
    audio_url: Optional[str] = None

class JournalEntryUpdate(BaseModel):
    content: Optional[str] = None
    mood: Optional[str] = None
    audio_url: Optional[str] = None

class JournalEntry(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    content: str
    date: date
    mood: Optional[str] = None
    audio_url: Optional[str] = None
    shared_with: List[uuid.UUID] = []
    created_at: datetime
    updated_at: datetime

class MoodEntryCreate(BaseModel):
    mood: str
    date: date

class MoodEntry(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    mood: str
    date: date
    shared_with: List[uuid.UUID] = []
    created_at: datetime

class SharedReflection(BaseModel):
    id: uuid.UUID
    date: date
    user_ids: List[uuid.UUID]
    reflection: str
    created_at: datetime

class EntryAccessLog(BaseModel):
    id: uuid.UUID
    entry_id: uuid.UUID
    entry_type: str  # 'journal' or 'mood'
    accessed_by: uuid.UUID
    entry_owner: uuid.UUID
    accessed_at: datetime

class PrivateNoteCreate(BaseModel):
    entry_id: uuid.UUID
    entry_type: str  # 'journal' or 'mood'
    note_content: str

class PrivateNote(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    entry_id: uuid.UUID
    entry_type: str
    note_content: str
    created_at: datetime
    updated_at: datetime

class CalendarDay(BaseModel):
    date: date
    user_entry: Optional[JournalEntry] = None
    partner_entry: Optional[JournalEntry] = None
    shared_reflection: Optional[SharedReflection] = None
    user_mood: Optional[MoodEntry] = None
    partner_mood: Optional[MoodEntry] = None

class Statistics(BaseModel):
    total_entries: int
    partner_entries: int
    shared_days: int
    total_reflections: int
    current_streak: int
    longest_streak: int

class InvitePartnerRequest(BaseModel):
    invite_code: str

class BackfillReflectionRequest(BaseModel):
    date: date
    user_id: uuid.UUID
    partner_id: uuid.UUID

class AuthResponse(BaseModel):
    access_token: str
    user: Profile
    message: str
