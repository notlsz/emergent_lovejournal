"""
Que Bella - AI Couples Love Journal Backend
Supabase + FastAPI Implementation with Advanced Features
"""
from fastapi import FastAPI, HTTPException, Depends, status, UploadFile, File, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
import os
import uuid
from datetime import date, datetime, timedelta
from typing import List, Optional
import openai
from supabase_client import get_supabase
from auth import get_current_user, get_current_user_profile
from models import *
import calendar
import asyncio

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
# PROFILE MANAGEMENT
# =====================================================================================

@app.get("/api/profile", response_model=Profile)
async def get_profile(current_user: uuid.UUID = Depends(get_current_user)):
    """Get current user profile"""
    profile = await get_current_user_profile(current_user)
    return Profile(**profile)

@app.post("/api/invite-partner")
async def invite_partner(
    request: InvitePartnerRequest,
    current_user: uuid.UUID = Depends(get_current_user)
):
    """Link with partner using invite code"""
    try:
        supabase = get_supabase()
        
        # Find partner by invite code
        partner_result = supabase.table("profiles").select("*").eq("invite_code", request.invite_code).execute()
        
        if not partner_result.data:
            raise HTTPException(status_code=404, detail="Invalid invite code")
        
        partner = partner_result.data[0]
        partner_id = uuid.UUID(partner["id"])
        
        if partner_id == current_user:
            raise HTTPException(status_code=400, detail="Cannot invite yourself")
        
        # Update both users to link as partners
        supabase.table("profiles").update({"partner_id": str(partner_id)}).eq("id", str(current_user)).execute()
        supabase.table("profiles").update({"partner_id": str(current_user)}).eq("id", str(partner_id)).execute()
        
        # Update shared_with fields for existing entries
        await update_shared_entries(current_user, partner_id)
        
        return {"message": "Partner linked successfully", "partner_name": partner.get("full_name", partner["email"])}
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error linking partner: {str(e)}")

async def update_shared_entries(user_id: uuid.UUID, partner_id: uuid.UUID):
    """Update existing entries to be shared with new partner"""
    supabase = get_supabase()
    
    # Update journal entries
    supabase.table("journal_entries").update({
        "shared_with": [str(partner_id)]
    }).eq("user_id", str(user_id)).execute()
    
    # Update mood entries  
    supabase.table("mood_entries").update({
        "shared_with": [str(partner_id)]
    }).eq("user_id", str(user_id)).execute()

# =====================================================================================
# JOURNAL ENTRIES
# =====================================================================================

@app.post("/api/journal-entries", response_model=JournalEntry)
async def create_journal_entry(
    entry_data: JournalEntryCreate,
    current_user: uuid.UUID = Depends(get_current_user)
):
    """Create new journal entry"""
    try:
        supabase = get_supabase()
        
        # Get partner ID for sharing
        profile = await get_current_user_profile(current_user)
        shared_with = [profile["partner_id"]] if profile.get("partner_id") else []
        
        # Create entry
        entry_dict = {
            "user_id": str(current_user),
            "content": entry_data.content,
            "date": entry_data.date.isoformat(),
            "mood": entry_data.mood,
            "audio_url": entry_data.audio_url,
            "shared_with": shared_with
        }
        
        result = supabase.table("journal_entries").insert(entry_dict).execute()
        
        if result.data:
            return JournalEntry(**result.data[0])
        else:
            raise HTTPException(status_code=400, detail="Failed to create entry")
            
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error creating entry: {str(e)}")

@app.get("/api/journal-entries", response_model=List[JournalEntry])
async def get_journal_entries(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    current_user: uuid.UUID = Depends(get_current_user)
):
    """Get journal entries for current user and partner"""
    try:
        supabase = get_supabase()
        
        query = supabase.table("journal_entries").select("*")
        
        # Filter by date range if provided
        if date_from:
            query = query.gte("date", date_from.isoformat())
        if date_to:
            query = query.lte("date", date_to.isoformat())
        
        # RLS will automatically filter for accessible entries
        result = query.order("date", desc=True).execute()
        
        # Log access for partner's entries
        await log_entry_access(result.data, current_user, "journal")
        
        return [JournalEntry(**entry) for entry in result.data]
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error fetching entries: {str(e)}")

@app.put("/api/journal-entries/{entry_id}", response_model=JournalEntry)
async def update_journal_entry(
    entry_id: uuid.UUID,
    entry_data: JournalEntryUpdate,
    current_user: uuid.UUID = Depends(get_current_user)
):
    """Update journal entry"""
    try:
        supabase = get_supabase()
        
        # Prepare update data (only include non-None fields)
        update_data = {k: v for k, v in entry_data.dict().items() if v is not None}
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No data to update")
        
        result = supabase.table("journal_entries").update(update_data).eq("id", str(entry_id)).execute()
        
        if result.data:
            return JournalEntry(**result.data[0])
        else:
            raise HTTPException(status_code=404, detail="Entry not found or permission denied")
            
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error updating entry: {str(e)}")

@app.delete("/api/journal-entries/{entry_id}")
async def delete_journal_entry(
    entry_id: uuid.UUID,
    current_user: uuid.UUID = Depends(get_current_user)
):
    """Delete journal entry"""
    try:
        supabase = get_supabase()
        
        result = supabase.table("journal_entries").delete().eq("id", str(entry_id)).execute()
        
        if result.data:
            return {"message": "Entry deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="Entry not found or permission denied")
            
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error deleting entry: {str(e)}")

# =====================================================================================
# MOOD ENTRIES  
# =====================================================================================

@app.post("/api/mood-entries", response_model=MoodEntry)
async def create_mood_entry(
    mood_data: MoodEntryCreate,
    current_user: uuid.UUID = Depends(get_current_user)
):
    """Create new mood entry"""
    try:
        supabase = get_supabase()
        
        # Get partner ID for sharing
        profile = await get_current_user_profile(current_user)
        shared_with = [profile["partner_id"]] if profile.get("partner_id") else []
        
        entry_dict = {
            "user_id": str(current_user),
            "mood": mood_data.mood,
            "date": mood_data.date.isoformat(),
            "shared_with": shared_with
        }
        
        result = supabase.table("mood_entries").insert(entry_dict).execute()
        
        if result.data:
            return MoodEntry(**result.data[0])
        else:
            raise HTTPException(status_code=400, detail="Failed to create mood entry")
            
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error creating mood entry: {str(e)}")

@app.get("/api/mood-entries", response_model=List[MoodEntry])
async def get_mood_entries(current_user: uuid.UUID = Depends(get_current_user)):
    """Get mood entries for current user and partner"""
    try:
        supabase = get_supabase()
        
        result = supabase.table("mood_entries").select("*").order("date", desc=True).execute()
        
        # Log access for partner's entries
        await log_entry_access(result.data, current_user, "mood")
        
        return [MoodEntry(**entry) for entry in result.data]
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error fetching mood entries: {str(e)}")

# =====================================================================================
# SHARED REFLECTIONS & AI
# =====================================================================================

@app.post("/api/generate-reflection")
async def generate_reflection(
    reflection_date: date,
    current_user: uuid.UUID = Depends(get_current_user)
):
    """Generate AI reflection for a specific date"""
    try:
        supabase = get_supabase()
        
        # Get partner ID
        profile = await get_current_user_profile(current_user)
        partner_id = profile.get("partner_id")
        
        if not partner_id:
            raise HTTPException(status_code=400, detail="No partner linked")
        
        # Get journal entries for both users on the specified date
        entries_result = supabase.table("journal_entries").select("*").eq("date", reflection_date.isoformat()).execute()
        
        user_entry = None
        partner_entry = None
        
        for entry in entries_result.data:
            if entry["user_id"] == str(current_user):
                user_entry = entry
            elif entry["user_id"] == partner_id:
                partner_entry = entry
        
        if not user_entry or not partner_entry:
            raise HTTPException(status_code=400, detail="Both partners need journal entries for this date")
        
        # Generate AI reflection
        reflection_text = await generate_ai_reflection(user_entry["content"], partner_entry["content"])
        
        # Save reflection
        user_ids = sorted([str(current_user), partner_id])  # Sort for consistent uniqueness
        reflection_dict = {
            "date": reflection_date.isoformat(),
            "user_ids": user_ids,
            "reflection": reflection_text
        }
        
        result = supabase.table("shared_reflections").upsert(reflection_dict).execute()
        
        if result.data:
            return {"reflection": reflection_text, "date": reflection_date}
        else:
            raise HTTPException(status_code=400, detail="Failed to save reflection")
            
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error generating reflection: {str(e)}")

async def generate_ai_reflection(user_content: str, partner_content: str) -> str:
    """Generate AI reflection using OpenAI"""
    try:
        prompt = f"""
        You are creating a poetic, loving reflection for a couple based on their journal entries from the same day. 
        
        First person wrote: "{user_content}"
        Second person wrote: "{partner_content}"
        
        Create a beautiful, 1-2 sentence reflection that captures the essence of their shared day and emotional connection. 
        Make it poetic, warm, and insightful about their relationship. Focus on the love and connection between them.
        """
        
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a relationship counselor and poet who creates beautiful reflections for couples."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=100,
            temperature=0.7
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        return f"In the tapestry of your shared day, love weaves beautiful patterns of connection and understanding."

# =====================================================================================
# CALENDAR VIEW
# =====================================================================================

@app.get("/api/calendar/{year}/{month}", response_model=List[CalendarDay])
async def get_calendar_data(
    year: int,
    month: int,
    current_user: uuid.UUID = Depends(get_current_user)
):
    """Get calendar data for a specific month"""
    try:
        supabase = get_supabase()
        
        # Get partner ID
        profile = await get_current_user_profile(current_user)
        partner_id = profile.get("partner_id")
        
        # Calculate date range for the month
        first_day = date(year, month, 1)
        last_day = date(year, month, calendar.monthrange(year, month)[1])
        
        # Get all entries for the month
        journal_result = supabase.table("journal_entries").select("*").gte("date", first_day.isoformat()).lte("date", last_day.isoformat()).execute()
        mood_result = supabase.table("mood_entries").select("*").gte("date", first_day.isoformat()).lte("date", last_day.isoformat()).execute()
        reflection_result = supabase.table("shared_reflections").select("*").gte("date", first_day.isoformat()).lte("date", last_day.isoformat()).execute()
        
        # Organize data by date
        calendar_data = []
        current_date = first_day
        
        while current_date <= last_day:
            date_str = current_date.isoformat()
            
            # Find entries for this date
            user_journal = next((JournalEntry(**entry) for entry in journal_result.data if entry["date"] == date_str and entry["user_id"] == str(current_user)), None)
            partner_journal = next((JournalEntry(**entry) for entry in journal_result.data if entry["date"] == date_str and entry["user_id"] == partner_id), None) if partner_id else None
            
            user_mood = next((MoodEntry(**entry) for entry in mood_result.data if entry["date"] == date_str and entry["user_id"] == str(current_user)), None)
            partner_mood = next((MoodEntry(**entry) for entry in mood_result.data if entry["date"] == date_str and entry["user_id"] == partner_id), None) if partner_id else None
            
            shared_reflection = next((SharedReflection(**entry) for entry in reflection_result.data if entry["date"] == date_str), None)
            
            calendar_data.append(CalendarDay(
                date=current_date,
                user_entry=user_journal,
                partner_entry=partner_journal,
                user_mood=user_mood,
                partner_mood=partner_mood,
                shared_reflection=shared_reflection
            ))
            
            current_date += timedelta(days=1)
        
        return calendar_data
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error fetching calendar data: {str(e)}")

# =====================================================================================
# STATISTICS & ANALYTICS
# =====================================================================================

@app.get("/api/statistics", response_model=Statistics)
async def get_statistics(current_user: uuid.UUID = Depends(get_current_user)):
    """Get user statistics and analytics"""
    try:
        supabase = get_supabase()
        
        # Get partner ID
        profile = await get_current_user_profile(current_user)
        partner_id = profile.get("partner_id")
        
        # Count total entries
        user_entries = supabase.table("journal_entries").select("id").eq("user_id", str(current_user)).execute()
        total_entries = len(user_entries.data)
        
        # Count partner entries
        partner_entries = 0
        if partner_id:
            partner_entries_result = supabase.table("journal_entries").select("id").eq("user_id", partner_id).execute()
            partner_entries = len(partner_entries_result.data)
        
        # Count shared days (days where both partners have entries)
        shared_days = 0
        total_reflections = 0
        
        if partner_id:
            # Get reflections count
            reflections_result = supabase.table("shared_reflections").select("id").contains("user_ids", [str(current_user)]).execute()
            total_reflections = len(reflections_result.data)
            shared_days = total_reflections  # Each reflection represents a shared day
        
        # Calculate streaks
        current_streak, longest_streak = await calculate_streaks(current_user)
        
        return Statistics(
            total_entries=total_entries,
            partner_entries=partner_entries,
            shared_days=shared_days,
            total_reflections=total_reflections,
            current_streak=current_streak,
            longest_streak=longest_streak
        )
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error fetching statistics: {str(e)}")

async def calculate_streaks(user_id: uuid.UUID) -> tuple[int, int]:
    """Calculate current and longest journaling streaks"""
    try:
        supabase = get_supabase()
        
        # Get all journal entries for user, sorted by date
        result = supabase.table("journal_entries").select("date").eq("user_id", str(user_id)).order("date", desc=False).execute()
        
        if not result.data:
            return 0, 0
        
        # Convert to date objects and remove duplicates
        dates = sorted(set(date.fromisoformat(entry["date"]) for entry in result.data))
        
        current_streak = 0
        longest_streak = 0
        temp_streak = 1
        
        today = date.today()
        
        # Check if there's an entry for today or yesterday (current streak)
        if dates and (dates[-1] == today or dates[-1] == today - timedelta(days=1)):
            current_streak = 1
            
            # Count backwards from the latest date
            for i in range(len(dates) - 2, -1, -1):
                if dates[i + 1] - dates[i] == timedelta(days=1):
                    current_streak += 1
                else:
                    break
        
        # Calculate longest streak
        for i in range(1, len(dates)):
            if dates[i] - dates[i - 1] == timedelta(days=1):
                temp_streak += 1
                longest_streak = max(longest_streak, temp_streak)
            else:
                temp_streak = 1
        
        longest_streak = max(longest_streak, temp_streak)
        
        return current_streak, longest_streak
        
    except Exception as e:
        return 0, 0

# =====================================================================================
# ACCESS LOGGING (for Read Receipts)
# =====================================================================================

async def log_entry_access(entries: List[dict], current_user: uuid.UUID, entry_type: str):
    """Log when user accesses partner's entries"""
    try:
        supabase = get_supabase()
        
        access_logs = []
        for entry in entries:
            entry_owner = uuid.UUID(entry["user_id"])
            
            # Only log if this is partner's entry (not own entry)
            if entry_owner != current_user:
                access_logs.append({
                    "entry_id": entry["id"],
                    "entry_type": entry_type,
                    "accessed_by": str(current_user),
                    "entry_owner": str(entry_owner)
                })
        
        if access_logs:
            supabase.table("entry_access_logs").insert(access_logs).execute()
            
    except Exception as e:
        # Don't fail the main request if logging fails
        pass

@app.get("/api/access-logs/{entry_id}")
async def get_entry_access_logs(
    entry_id: uuid.UUID,
    current_user: uuid.UUID = Depends(get_current_user)
):
    """Get access logs for a specific entry"""
    try:
        supabase = get_supabase()
        
        result = supabase.table("entry_access_logs").select("*").eq("entry_id", str(entry_id)).execute()
        
        return [EntryAccessLog(**log) for log in result.data]
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error fetching access logs: {str(e)}")

# =====================================================================================
# AUDIO JOURNALING (File Upload)
# =====================================================================================

@app.post("/api/upload-audio")
async def upload_audio(
    file: UploadFile = File(...),
    current_user: uuid.UUID = Depends(get_current_user)
):
    """Upload audio file to Supabase Storage"""
    try:
        # Validate file type
        if not file.content_type.startswith('audio/'):
            raise HTTPException(status_code=400, detail="File must be an audio file")
        
        # Read file content
        file_content = await file.read()
        
        # Create unique filename
        file_extension = file.filename.split('.')[-1] if '.' in file.filename else 'mp3'
        unique_filename = f"{current_user}/{uuid.uuid4()}.{file_extension}"
        
        supabase = get_supabase()
        
        # Upload to Supabase Storage
        result = supabase.storage.from_("audio-journal").upload(unique_filename, file_content)
        
        if result:
            # Get public URL
            public_url = supabase.storage.from_("audio-journal").get_public_url(unique_filename)
            
            return {"audio_url": public_url, "filename": unique_filename}
        else:
            raise HTTPException(status_code=400, detail="Failed to upload audio file")
            
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error uploading audio: {str(e)}")

# =====================================================================================
# PRIVATE NOTES ON PARTNER'S ENTRIES
# =====================================================================================

@app.post("/api/private-notes", response_model=PrivateNote)
async def create_private_note(
    note_data: PrivateNoteCreate,
    current_user: uuid.UUID = Depends(get_current_user)
):
    """Create private note on partner's entry"""
    try:
        supabase = get_supabase()
        
        note_dict = {
            "user_id": str(current_user),
            "entry_id": str(note_data.entry_id),
            "entry_type": note_data.entry_type,
            "note_content": note_data.note_content
        }
        
        result = supabase.table("private_notes").upsert(note_dict).execute()
        
        if result.data:
            return PrivateNote(**result.data[0])
        else:
            raise HTTPException(status_code=400, detail="Failed to create private note")
            
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error creating private note: {str(e)}")

@app.get("/api/private-notes/{entry_id}", response_model=Optional[PrivateNote])
async def get_private_note(
    entry_id: uuid.UUID,
    entry_type: str,
    current_user: uuid.UUID = Depends(get_current_user)
):
    """Get private note for specific entry"""
    try:
        supabase = get_supabase()
        
        result = supabase.table("private_notes").select("*").eq("entry_id", str(entry_id)).eq("entry_type", entry_type).eq("user_id", str(current_user)).execute()
        
        if result.data:
            return PrivateNote(**result.data[0])
        else:
            return None
            
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error fetching private note: {str(e)}")

# =====================================================================================
# CRON JOB & ADMIN ENDPOINTS
# =====================================================================================

@app.post("/api/cron/generate-reflections")
async def cron_generate_reflections(cron_secret: str = Header(None)):
    """Cron job to automatically generate daily reflections at 5 AM UTC"""
    
    # Verify cron secret
    expected_secret = os.getenv("CRON_SECRET")
    if not cron_secret or cron_secret != expected_secret:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    try:
        supabase = get_supabase()
        yesterday = date.today() - timedelta(days=1)
        
        # Get all journal entries from yesterday
        entries_result = supabase.table("journal_entries").select("*").eq("date", yesterday.isoformat()).execute()
        
        # Group entries by couples (using shared_with)
        couples = {}
        for entry in entries_result.data:
            user_id = entry["user_id"]
            shared_with = entry.get("shared_with", [])
            
            if shared_with:
                partner_id = shared_with[0]
                couple_key = tuple(sorted([user_id, partner_id]))
                
                if couple_key not in couples:
                    couples[couple_key] = {}
                
                couples[couple_key][user_id] = entry
        
        # Generate reflections for couples with both entries
        reflections_created = 0
        for (user1_id, user2_id), entries in couples.items():
            if len(entries) == 2:  # Both partners have entries
                try:
                    # Check if reflection already exists
                    existing = supabase.table("shared_reflections").select("id").eq("date", yesterday.isoformat()).contains("user_ids", [user1_id, user2_id]).execute()
                    
                    if not existing.data:  # No existing reflection
                        entry1 = entries[user1_id]
                        entry2 = entries[user2_id]
                        
                        # Generate AI reflection
                        reflection_text = await generate_ai_reflection(entry1["content"], entry2["content"])
                        
                        # Save reflection
                        reflection_dict = {
                            "date": yesterday.isoformat(),
                            "user_ids": [user1_id, user2_id],
                            "reflection": reflection_text
                        }
                        
                        supabase.table("shared_reflections").insert(reflection_dict).execute()
                        reflections_created += 1
                        
                except Exception as e:
                    # Continue with other couples if one fails
                    continue
        
        return {"message": f"Generated {reflections_created} reflections for {yesterday}"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cron job error: {str(e)}")

@app.post("/api/backfill-reflection")
async def backfill_reflection(
    request: BackfillReflectionRequest,
    current_user: uuid.UUID = Depends(get_current_user)
):
    """Manually generate reflection for a specific date and couple"""
    try:
        supabase = get_supabase()
        
        # Get journal entries for both users on the specified date
        entries_result = supabase.table("journal_entries").select("*").eq("date", request.date.isoformat()).execute()
        
        user_entry = None
        partner_entry = None
        
        for entry in entries_result.data:
            if entry["user_id"] == str(request.user_id):
                user_entry = entry
            elif entry["user_id"] == str(request.partner_id):
                partner_entry = entry
        
        if not user_entry or not partner_entry:
            raise HTTPException(status_code=400, detail="Both users need journal entries for this date")
        
        # Generate AI reflection
        reflection_text = await generate_ai_reflection(user_entry["content"], partner_entry["content"])
        
        # Save reflection
        user_ids = sorted([str(request.user_id), str(request.partner_id)])
        reflection_dict = {
            "date": request.date.isoformat(),
            "user_ids": user_ids,
            "reflection": reflection_text
        }
        
        result = supabase.table("shared_reflections").upsert(reflection_dict).execute()
        
        if result.data:
            return {"reflection": reflection_text, "date": request.date}
        else:
            raise HTTPException(status_code=400, detail="Failed to save reflection")
            
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error generating reflection: {str(e)}")

# =====================================================================================
# HEALTH CHECK
# =====================================================================================

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "message": "Que Bella AI Couples Love Journal is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)