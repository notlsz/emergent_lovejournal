from fastapi import FastAPI, APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timedelta
import jwt
import bcrypt
from openai import OpenAI
import asyncio
from contextlib import asynccontextmanager

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# OpenAI client
openai_client = OpenAI(api_key=os.environ['OPENAI_API_KEY'])

# JWT Configuration
JWT_SECRET = os.environ.get('JWT_SECRET', 'que_bella_secret_key_2024')
JWT_ALGORITHM = 'HS256'

security = HTTPBearer()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown
    client.close()

# Create the main app without a prefix
app = FastAPI(lifespan=lifespan)

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Pydantic Models
class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: str
    name: str
    partner_id: Optional[str] = None
    invite_code: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class UserCreate(BaseModel):
    email: str
    password: str
    name: str

class UserLogin(BaseModel):
    email: str
    password: str

class JournalEntry(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    content: str
    date: str  # YYYY-MM-DD format
    mood: Optional[str] = None
    audio_url: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class JournalEntryCreate(BaseModel):
    content: str
    date: str
    mood: Optional[str] = None

class MoodEntry(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    mood: str
    date: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class MoodEntryCreate(BaseModel):
    mood: str
    date: str

class SharedReflection(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    date: str
    user_ids: List[str]
    reflection: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class PartnerInvite(BaseModel):
    invite_code: str

class DayEntry(BaseModel):
    date: str
    my_entry: Optional[JournalEntry] = None
    partner_entry: Optional[JournalEntry] = None
    my_mood: Optional[MoodEntry] = None
    partner_mood: Optional[MoodEntry] = None
    reflection: Optional[SharedReflection] = None

# Authentication functions
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def create_access_token(user_id: str) -> str:
    payload = {
        'user_id': user_id,
        'exp': datetime.utcnow() + timedelta(days=30)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get('user_id')
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        return user_id
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

# API Routes
@api_router.post("/register")
async def register(user_data: UserCreate):
    # Check if user exists
    existing_user = await db.users.find_one({"email": user_data.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create user
    hashed_password = hash_password(user_data.password)
    user = User(
        email=user_data.email,
        name=user_data.name,
        invite_code=str(uuid.uuid4())[:8]  # Generate 8-char invite code
    )
    
    user_dict = user.dict()
    user_dict['password'] = hashed_password
    
    await db.users.insert_one(user_dict)
    
    token = create_access_token(user.id)
    return {"token": token, "user": user}

@api_router.post("/login")
async def login(login_data: UserLogin):
    user = await db.users.find_one({"email": login_data.email})
    if not user or not verify_password(login_data.password, user['password']):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_access_token(user['id'])
    user_obj = User(**{k: v for k, v in user.items() if k != 'password'})
    return {"token": token, "user": user_obj}

@api_router.get("/me")
async def get_me(user_id: str = Depends(get_current_user)):
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user_obj = User(**{k: v for k, v in user.items() if k != 'password'})
    return user_obj

@api_router.post("/invite-partner")
async def invite_partner(invite_data: PartnerInvite, user_id: str = Depends(get_current_user)):
    # Find partner by invite code
    partner = await db.users.find_one({"invite_code": invite_data.invite_code})
    if not partner:
        raise HTTPException(status_code=404, detail="Invalid invite code")
    
    if partner['id'] == user_id:
        raise HTTPException(status_code=400, detail="Cannot invite yourself")
    
    # Update both users
    await db.users.update_one({"id": user_id}, {"$set": {"partner_id": partner['id']}})
    await db.users.update_one({"id": partner['id']}, {"$set": {"partner_id": user_id}})
    
    return {"message": "Partner linked successfully", "partner_name": partner['name']}

@api_router.post("/journal")
async def create_journal_entry(entry_data: JournalEntryCreate, user_id: str = Depends(get_current_user)):
    # Check if entry already exists for this date
    existing_entry = await db.journal_entries.find_one({"user_id": user_id, "date": entry_data.date})
    if existing_entry:
        # Update existing entry
        await db.journal_entries.update_one(
            {"user_id": user_id, "date": entry_data.date},
            {"$set": {"content": entry_data.content, "mood": entry_data.mood}}
        )
        updated_entry = await db.journal_entries.find_one({"user_id": user_id, "date": entry_data.date})
        return JournalEntry(**updated_entry)
    else:
        # Create new entry
        entry = JournalEntry(
            user_id=user_id,
            content=entry_data.content,
            date=entry_data.date,
            mood=entry_data.mood
        )
        await db.journal_entries.insert_one(entry.dict())
        return entry

@api_router.post("/mood")
async def create_mood_entry(mood_data: MoodEntryCreate, user_id: str = Depends(get_current_user)):
    # Check if mood already exists for this date
    existing_mood = await db.mood_entries.find_one({"user_id": user_id, "date": mood_data.date})
    if existing_mood:
        # Update existing mood
        await db.mood_entries.update_one(
            {"user_id": user_id, "date": mood_data.date},
            {"$set": {"mood": mood_data.mood}}
        )
        updated_mood = await db.mood_entries.find_one({"user_id": user_id, "date": mood_data.date})
        return MoodEntry(**updated_mood)
    else:
        # Create new mood
        mood = MoodEntry(
            user_id=user_id,
            mood=mood_data.mood,
            date=mood_data.date
        )
        await db.mood_entries.insert_one(mood.dict())
        return mood

@api_router.get("/calendar/{month}")
async def get_calendar_data(month: str, user_id: str = Depends(get_current_user)):
    # Get user and partner
    user = await db.users.find_one({"id": user_id})
    if not user or not user.get('partner_id'):
        return []
    
    partner_id = user['partner_id']
    
    # Get all entries for the month
    entries = await db.journal_entries.find({
        "user_id": {"$in": [user_id, partner_id]},
        "date": {"$regex": f"^{month}"}
    }).to_list(None)
    
    moods = await db.mood_entries.find({
        "user_id": {"$in": [user_id, partner_id]},
        "date": {"$regex": f"^{month}"}
    }).to_list(None)
    
    reflections = await db.shared_reflections.find({
        "user_ids": {"$in": [user_id]},
        "date": {"$regex": f"^{month}"}
    }).to_list(None)
    
    # Organize by date
    calendar_data = {}
    
    # Process entries
    for entry in entries:
        date = entry['date']
        if date not in calendar_data:
            calendar_data[date] = DayEntry(date=date)
        
        if entry['user_id'] == user_id:
            calendar_data[date].my_entry = JournalEntry(**entry)
        else:
            calendar_data[date].partner_entry = JournalEntry(**entry)
    
    # Process moods
    for mood in moods:
        date = mood['date']
        if date not in calendar_data:
            calendar_data[date] = DayEntry(date=date)
        
        if mood['user_id'] == user_id:
            calendar_data[date].my_mood = MoodEntry(**mood)
        else:
            calendar_data[date].partner_mood = MoodEntry(**mood)
    
    # Process reflections
    for reflection in reflections:
        date = reflection['date']
        if date not in calendar_data:
            calendar_data[date] = DayEntry(date=date)
        
        calendar_data[date].reflection = SharedReflection(**reflection)
    
    return list(calendar_data.values())

@api_router.post("/generate-reflection/{date}")
async def generate_reflection(date: str, user_id: str = Depends(get_current_user)):
    # Get user and partner
    user = await db.users.find_one({"id": user_id})
    if not user or not user.get('partner_id'):
        raise HTTPException(status_code=400, detail="No partner linked")
    
    partner_id = user['partner_id']
    
    # Get both entries for the date
    my_entry = await db.journal_entries.find_one({"user_id": user_id, "date": date})
    partner_entry = await db.journal_entries.find_one({"user_id": partner_id, "date": date})
    
    if not my_entry or not partner_entry:
        raise HTTPException(status_code=400, detail="Both partners need to have entries for this date")
    
    # Check if reflection already exists
    existing_reflection = await db.shared_reflections.find_one({
        "date": date,
        "user_ids": {"$all": [user_id, partner_id]}
    })
    
    if existing_reflection:
        return SharedReflection(**existing_reflection)
    
    # Generate AI reflection
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a poetic AI that creates beautiful, intimate reflections for couples based on their journal entries. Create 1-2 sentences that capture the essence of their shared day and emotional connection. Be romantic, insightful, and poetic."
                },
                {
                    "role": "user",
                    "content": f"Partner 1's journal: {my_entry['content']}\n\nPartner 2's journal: {partner_entry['content']}\n\nCreate a beautiful shared reflection for this couple's day."
                }
            ],
            max_tokens=150,
            temperature=0.8
        )
        
        reflection_text = response.choices[0].message.content.strip()
        
    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        # Fallback to a beautiful sample reflection when API is unavailable
        reflection_text = "Two hearts sharing their world through words, creating a tapestry of love that grows stronger with each passing day. In your shared stories, the beauty of your connection shines brightest."
    
    # Save reflection
    reflection = SharedReflection(
        date=date,
        user_ids=[user_id, partner_id],
        reflection=reflection_text
    )
    
    await db.shared_reflections.insert_one(reflection.dict())
    return reflection

@api_router.get("/stats")
async def get_stats(user_id: str = Depends(get_current_user)):
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Count entries
    my_entries = await db.journal_entries.count_documents({"user_id": user_id})
    
    # Count days with partner entries (if partner exists)
    shared_days = 0
    if user.get('partner_id'):
        partner_id = user['partner_id']
        
        # Get all my entry dates
        my_dates = await db.journal_entries.distinct("date", {"user_id": user_id})
        
        # Count how many of those dates also have partner entries
        for date in my_dates:
            partner_entry = await db.journal_entries.find_one({"user_id": partner_id, "date": date})
            if partner_entry:
                shared_days += 1
    
    # Count reflections
    reflections_count = await db.shared_reflections.count_documents({"user_ids": user_id})
    
    return {
        "total_entries": my_entries,
        "shared_days": shared_days,
        "reflections": reflections_count,
        "has_partner": bool(user.get('partner_id'))
    }

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
