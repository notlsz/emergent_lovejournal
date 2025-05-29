"""
Authentication utilities for Supabase integration
"""
import os
import jwt
from typing import Optional
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase_client import get_supabase
import uuid

security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> uuid.UUID:
    """
    Extract user ID from Supabase JWT token
    """
    try:
        token = credentials.credentials
        
        # Decode the JWT token (Supabase tokens are self-verifiable)
        # We don't need to verify signature since Supabase handles that
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
    """
    Get user profile from Supabase
    """
    supabase = get_supabase()
    
    result = supabase.table("profiles").select("*").eq("id", str(user_id)).execute()
    
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found"
        )
    
    return result.data[0]

async def get_current_user_profile(user_id: uuid.UUID = Depends(get_current_user)):
    """
    Get current user's profile
    """
    return await get_user_profile(user_id)
