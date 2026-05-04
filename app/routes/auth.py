from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.auth import authenticate_user, create_access_token, get_current_user, public_user
from app.database import get_database
from app.schemas import LoginRequest, LoginResponse, UserRead


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> LoginResponse:
    user = await authenticate_user(db, payload.email, payload.password)
    return {
        "access_token": create_access_token(user),
        "token_type": "bearer",
        "user": public_user(user),
    }


@router.get("/me", response_model=UserRead)
async def me(current_user: dict = Depends(get_current_user)) -> UserRead:
    return public_user(current_user)
