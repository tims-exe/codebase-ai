from typing import List, Optional
from src.users.model import User

users_data = [
    User(id=1, name="John Doe", email="john@example.com", age=30),
    User(id=2, name="Jane Smith", email="jane@example.com", age=25),
    User(id=3, name="Bob Johnson", email="bob@example.com", age=35),
    User(id=4, name="Alice Brown", email="alice@example.com", age=28)
]

class UserService:
    @staticmethod
    def get_all_users() -> List[User]:
        return users_data
    
    @staticmethod
    def get_user_by_id(user_id: int) -> Optional[User]:
        return next((user for user in users_data if user.id == user_id), None)