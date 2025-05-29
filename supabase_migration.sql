-- =====================================================================================
-- Que Bella - AI Couples Love Journal Database Schema
-- Supabase PostgreSQL Migration
-- =====================================================================================

-- Enable necessary extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =====================================================================================
-- 1. PROFILES TABLE (User information with partner linking)
-- =====================================================================================
CREATE TABLE IF NOT EXISTS profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT UNIQUE NOT NULL,
    full_name TEXT,
    invite_code TEXT UNIQUE,
    partner_id UUID REFERENCES profiles(id),
    allow_read_receipts BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for fast partner lookups
CREATE INDEX IF NOT EXISTS idx_profiles_partner_id ON profiles(partner_id);
CREATE INDEX IF NOT EXISTS idx_profiles_invite_code ON profiles(invite_code);

-- =====================================================================================
-- 2. JOURNAL ENTRIES TABLE (Core journaling functionality)
-- =====================================================================================
CREATE TABLE IF NOT EXISTS journal_entries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    date DATE NOT NULL,
    mood TEXT,
    audio_url TEXT,
    shared_with UUID[] DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, date) -- One entry per user per day
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_journal_entries_user_id ON journal_entries(user_id);
CREATE INDEX IF NOT EXISTS idx_journal_entries_date ON journal_entries(date);
CREATE INDEX IF NOT EXISTS idx_journal_entries_shared_with ON journal_entries USING GIN(shared_with);

-- =====================================================================================
-- 3. MOOD ENTRIES TABLE (Separate mood tracking)
-- =====================================================================================
CREATE TABLE IF NOT EXISTS mood_entries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    mood TEXT NOT NULL,
    date DATE NOT NULL,
    shared_with UUID[] DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, date) -- One mood per user per day
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_mood_entries_user_id ON mood_entries(user_id);
CREATE INDEX IF NOT EXISTS idx_mood_entries_date ON mood_entries(date);

-- =====================================================================================
-- 4. SHARED REFLECTIONS TABLE (AI-generated couple reflections)
-- =====================================================================================
CREATE TABLE IF NOT EXISTS shared_reflections (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    date DATE NOT NULL,
    user_ids UUID[] NOT NULL,
    reflection TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(date, user_ids) -- One reflection per couple per day
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_shared_reflections_date ON shared_reflections(date);
CREATE INDEX IF NOT EXISTS idx_shared_reflections_user_ids ON shared_reflections USING GIN(user_ids);

-- =====================================================================================
-- 5. ENTRY ACCESS LOGS TABLE (Track when partners view entries)
-- =====================================================================================
CREATE TABLE IF NOT EXISTS entry_access_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    entry_id UUID NOT NULL,
    entry_type TEXT NOT NULL CHECK (entry_type IN ('journal', 'mood')),
    accessed_by UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    entry_owner UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    accessed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_entry_access_logs_entry_id ON entry_access_logs(entry_id);
CREATE INDEX IF NOT EXISTS idx_entry_access_logs_accessed_by ON entry_access_logs(accessed_by);
CREATE INDEX IF NOT EXISTS idx_entry_access_logs_entry_owner ON entry_access_logs(entry_owner);

-- =====================================================================================
-- 6. PRIVATE NOTES TABLE (Private comments on partner's entries)
-- =====================================================================================
CREATE TABLE IF NOT EXISTS private_notes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    entry_id UUID NOT NULL, -- References journal_entries.id
    entry_type TEXT NOT NULL CHECK (entry_type IN ('journal', 'mood')),
    note_content TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, entry_id, entry_type) -- One private note per user per entry
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_private_notes_user_id ON private_notes(user_id);
CREATE INDEX IF NOT EXISTS idx_private_notes_entry_id ON private_notes(entry_id);

-- =====================================================================================
-- 7. STORAGE BUCKET FOR AUDIO FILES
-- =====================================================================================
INSERT INTO storage.buckets (id, name, public)
VALUES ('audio-journal', 'audio-journal', false)
ON CONFLICT (id) DO NOTHING;

-- =====================================================================================
-- 8. ROW LEVEL SECURITY (RLS) POLICIES
-- =====================================================================================

-- Enable RLS on all tables
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE journal_entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE mood_entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE shared_reflections ENABLE ROW LEVEL SECURITY;
ALTER TABLE entry_access_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE private_notes ENABLE ROW LEVEL SECURITY;

-- =====================================================================================
-- PROFILES TABLE POLICIES
-- =====================================================================================

-- Users can view their own profile and their partner's profile
CREATE POLICY "Users can view own and partner profile" ON profiles
    FOR SELECT USING (
        auth.uid() = id OR 
        auth.uid() = partner_id OR
        id IN (SELECT partner_id FROM profiles WHERE id = auth.uid())
    );

-- Users can update their own profile only
CREATE POLICY "Users can update own profile" ON profiles
    FOR UPDATE USING (auth.uid() = id);

-- Users can insert their own profile only
CREATE POLICY "Users can insert own profile" ON profiles
    FOR INSERT WITH CHECK (auth.uid() = id);

-- =====================================================================================
-- JOURNAL ENTRIES TABLE POLICIES
-- =====================================================================================

-- Users can view their own entries and entries shared with them
CREATE POLICY "Users can view own and shared journal entries" ON journal_entries
    FOR SELECT USING (
        auth.uid() = user_id OR 
        auth.uid() = ANY(shared_with)
    );

-- Users can insert their own entries only
CREATE POLICY "Users can insert own journal entries" ON journal_entries
    FOR INSERT WITH CHECK (auth.uid() = user_id);

-- Users can update their own entries only
CREATE POLICY "Users can update own journal entries" ON journal_entries
    FOR UPDATE USING (auth.uid() = user_id);

-- Users can delete their own entries only
CREATE POLICY "Users can delete own journal entries" ON journal_entries
    FOR DELETE USING (auth.uid() = user_id);

-- =====================================================================================
-- MOOD ENTRIES TABLE POLICIES
-- =====================================================================================

-- Users can view their own mood entries and entries shared with them
CREATE POLICY "Users can view own and shared mood entries" ON mood_entries
    FOR SELECT USING (
        auth.uid() = user_id OR 
        auth.uid() = ANY(shared_with)
    );

-- Users can insert their own mood entries only
CREATE POLICY "Users can insert own mood entries" ON mood_entries
    FOR INSERT WITH CHECK (auth.uid() = user_id);

-- Users can update their own mood entries only
CREATE POLICY "Users can update own mood entries" ON mood_entries
    FOR UPDATE USING (auth.uid() = user_id);

-- Users can delete their own mood entries only
CREATE POLICY "Users can delete own mood entries" ON mood_entries
    FOR DELETE USING (auth.uid() = user_id);

-- =====================================================================================
-- SHARED REFLECTIONS TABLE POLICIES
-- =====================================================================================

-- Users can view reflections that include them
CREATE POLICY "Users can view reflections that include them" ON shared_reflections
    FOR SELECT USING (auth.uid() = ANY(user_ids));

-- Only service role can insert/update/delete reflections (for AI cron jobs)
CREATE POLICY "Service role can manage reflections" ON shared_reflections
    FOR ALL USING (auth.role() = 'service_role');

-- =====================================================================================
-- ENTRY ACCESS LOGS TABLE POLICIES
-- =====================================================================================

-- Users can view access logs for their own entries or entries they accessed
CREATE POLICY "Users can view relevant access logs" ON entry_access_logs
    FOR SELECT USING (
        auth.uid() = entry_owner OR 
        auth.uid() = accessed_by
    );

-- Users can insert access logs when they access entries
CREATE POLICY "Users can insert access logs" ON entry_access_logs
    FOR INSERT WITH CHECK (auth.uid() = accessed_by);

-- =====================================================================================
-- PRIVATE NOTES TABLE POLICIES
-- =====================================================================================

-- Users can only view their own private notes
CREATE POLICY "Users can view own private notes" ON private_notes
    FOR SELECT USING (auth.uid() = user_id);

-- Users can insert their own private notes only
CREATE POLICY "Users can insert own private notes" ON private_notes
    FOR INSERT WITH CHECK (auth.uid() = user_id);

-- Users can update their own private notes only
CREATE POLICY "Users can update own private notes" ON private_notes
    FOR UPDATE USING (auth.uid() = user_id);

-- Users can delete their own private notes only
CREATE POLICY "Users can delete own private notes" ON private_notes
    FOR DELETE USING (auth.uid() = user_id);

-- =====================================================================================
-- STORAGE POLICIES FOR AUDIO FILES
-- =====================================================================================

-- Users can upload audio files to their own folder
CREATE POLICY "Users can upload own audio files" ON storage.objects
    FOR INSERT WITH CHECK (
        bucket_id = 'audio-journal' AND 
        auth.uid()::text = (storage.foldername(name))[1]
    );

-- Users can view their own audio files and their partner's audio files
CREATE POLICY "Users can view own and partner audio files" ON storage.objects
    FOR SELECT USING (
        bucket_id = 'audio-journal' AND (
            auth.uid()::text = (storage.foldername(name))[1] OR
            (storage.foldername(name))[1] IN (
                SELECT partner_id::text FROM profiles WHERE id = auth.uid()
            )
        )
    );

-- Users can update their own audio files
CREATE POLICY "Users can update own audio files" ON storage.objects
    FOR UPDATE USING (
        bucket_id = 'audio-journal' AND 
        auth.uid()::text = (storage.foldername(name))[1]
    );

-- Users can delete their own audio files
CREATE POLICY "Users can delete own audio files" ON storage.objects
    FOR DELETE USING (
        bucket_id = 'audio-journal' AND 
        auth.uid()::text = (storage.foldername(name))[1]
    );

-- =====================================================================================
-- FUNCTIONS AND TRIGGERS
-- =====================================================================================

-- Function to automatically update the updated_at column
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers for updated_at columns
CREATE TRIGGER update_profiles_updated_at
    BEFORE UPDATE ON profiles
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_journal_entries_updated_at
    BEFORE UPDATE ON journal_entries
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_private_notes_updated_at
    BEFORE UPDATE ON private_notes
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =====================================================================================
-- UTILITY FUNCTIONS
-- =====================================================================================

-- Function to generate unique invite codes
CREATE OR REPLACE FUNCTION generate_invite_code()
RETURNS TEXT AS $$
DECLARE
    chars TEXT := 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
    result TEXT := '';
    i INT;
BEGIN
    FOR i IN 1..8 LOOP
        result := result || substr(chars, floor(random() * length(chars) + 1)::INT, 1);
    END LOOP;
    RETURN result;
END;
$$ LANGUAGE plpgsql;

-- Function to automatically set invite code on profile creation
CREATE OR REPLACE FUNCTION set_invite_code()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.invite_code IS NULL THEN
        NEW.invite_code := generate_invite_code();
        -- Ensure uniqueness
        WHILE EXISTS (SELECT 1 FROM profiles WHERE invite_code = NEW.invite_code) LOOP
            NEW.invite_code := generate_invite_code();
        END LOOP;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to set invite code on profile creation
CREATE TRIGGER set_profiles_invite_code
    BEFORE INSERT ON profiles
    FOR EACH ROW
    EXECUTE FUNCTION set_invite_code();

-- =====================================================================================
-- SAMPLE DATA AND SETUP COMPLETION
-- =====================================================================================

-- Function to handle new user registration
CREATE OR REPLACE FUNCTION handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.profiles (id, email, full_name)
    VALUES (NEW.id, NEW.email, NEW.raw_user_meta_data->>'full_name');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger to automatically create profile on user registration
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION handle_new_user();

-- Grant necessary permissions
GRANT USAGE ON SCHEMA public TO anon, authenticated;
GRANT ALL ON ALL TABLES IN SCHEMA public TO anon, authenticated;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO anon, authenticated;

-- =====================================================================================
-- MIGRATION COMPLETE
-- =====================================================================================
-- This migration sets up the complete Que Bella database schema with:
-- ✅ User profiles with partner linking
-- ✅ Journal entries with audio support
-- ✅ Mood tracking
-- ✅ AI-generated shared reflections
-- ✅ Entry access logging for read receipts
-- ✅ Private notes on partner entries
-- ✅ Row-Level Security (RLS) for data privacy
-- ✅ Supabase Storage for audio files
-- ✅ Automatic triggers and utility functions
-- =====================================================================================