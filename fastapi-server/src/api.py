from fastapi import APIRouter
from typing import List
from src.users.model import User
from .users.services import UserService

router = APIRouter()

@router.get("/users", response_model=List[User])
async def get_users():
    return UserService.get_all_users()