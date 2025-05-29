"""
Que Bella - AI Couples Love Journal Backend
Supabase + FastAPI Implementation with Advanced Features
ALL-IN-ONE VERSION
"""
from fastapi import FastAPI, HTTPException, Depends, status, UploadFile, File, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
import os
import uuid
from datetime import date, datetime, timedelta
from typing import List, Optional
import openai
from supabase import create_client, Client
import calendar
import asyncio
import jwt
from pydantic import BaseModel, EmailStr

# Load environment variables
load_dotenv()

app = FastAPI(title="Que Bella - AI Couples Love Journal", version="2.0.0")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")

# =====================================================================================
# SUPABASE CLIENT SETUP
# =====================================================================================

class SupabaseClient:
    _instance: Optional[Client] = None
    
    @classmethod
    def get_client(cls) -> Client:
        """Get Supabase client instance (singleton pattern)"""
        if cls._instance is None:
            supabase_url = os.getenv("SUPABASE_URL")
            supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            
            if not supabase_url or not supabase_key:
                raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
            
            cls._instance = create_client(supabase_url, supabase_key)
        
        return cls._instance

def get_supabase() -> Client:
    """Get Supabase client instance"""
    return SupabaseClient.get_client()

# =====================================================================================
# PYDANTIC MODELS
# =====================================================================================

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

# =====================================================================================
# AUTHENTICATION UTILITIES
# =====================================================================================

security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> uuid.UUID:
    """Extract user ID from Supabase JWT token"""
    try:
        token = credentials.credentials
        
        # Decode the JWT token (Supabase tokens are self-verifiable)
        payload = jwt.decode(token, options={"verify_signature": False})
        
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: no user ID found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return uuid.UUID(user_id)
        
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID format",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_user_profile(user_id: uuid.UUID):
    """Get user profile from Supabase"""
    supabase = get_supabase()
    
    result = supabase.table("profiles").select("*").eq("id", str(user_id)).execute()
    
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found"
        )
    
    return result.data[0]

async def get_current_user_profile(user_id: uuid.UUID = Depends(get_current_user)):
    """Get current user's profile"""
    return await get_user_profile(user_id)

# =====================================================================================
# AUTHENTICATION ENDPOINTS (Supabase Auth Integration)
# =====================================================================================

@app.post("/api/register", response_model=AuthResponse)
async def register(user_data: UserCreate):
    """Register new user with Supabase Auth"""
    try:
        supabase = get_supabase()
        
        # Create user with Supabase Auth
        auth_response = supabase.auth.sign_up({
            "email": user_data.email,
            "password": user_data.password,
            "options": {
                "data": {
                    "full_name": user_data.full_name
                }
            }
        })
        
        if auth_response.user:
            # Profile will be auto-created by the database trigger
            return AuthResponse(
                access_token=auth_response.session.access_token,
                user=Profile(
                    id=uuid.UUID(auth_response.user.id),
                    email=auth_response.user.email,
                    full_name=user_data.full_name,
                    invite_code=None,  # Will be set by trigger
                    partner_id=None,
                    allow_read_receipts=True,
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                ),
                message="Registration successful"
            )
        else:
            raise HTTPException(status_code=400, detail="Registration failed")
            
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Registration error: {str(e)}")

@app.post("/api/login", response_model=AuthResponse)
async def login(user_data: UserLogin):
    """Login user with Supabase Auth"""
    try:
        supabase = get_supabase()
        
        # Authenticate with Supabase
        auth_response = supabase.auth.sign_in_with_password({
            "email": user_data.email,
            "password": user_data.password
        })
        
        if auth_response.user:
            # Get user profile
            profile_result = supabase.table("profiles").select("*").eq("id", auth_response.user.id).execute()
            
            if profile_result.data:
                profile_data = profile_result.data[0]
                return AuthResponse(
                    access_token=auth_response.session.access_token,
                    user=Profile(**profile_data),
                    message="Login successful"
                )
            else:
                raise HTTPException(status_code=404, detail="User profile not found")
        else:
            raise HTTPException(status_code=401, detail="Invalid credentials")
            
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Login error: {str(e)}")

# =====================================================================================
# HEALTH CHECK
# =====================================================================================

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "message": "Que Bella AI Couples Love Journal is running"}

# =====================================================================================
# TEST ENDPOINT FOR SIMPLE TESTING
# =====================================================================================

@app.get("/api/test")
async def test_endpoint():
    """Simple test endpoint"""
    try:
        supabase = get_supabase()
        return {"status": "success", "message": "Supabase connection working"}
    except Exception as e:
        return {"status": "error", "message": f"Supabase connection failed: {str(e)}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)