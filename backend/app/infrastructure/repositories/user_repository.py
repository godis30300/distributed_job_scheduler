from typing import Optional
from sqlalchemy.orm import Session
from app.domain.entities.user import User
from app.infrastructure.repositories.base_repository import BaseRepository

class UserRepository(BaseRepository[User]):
    def __init__(self, db: Session):
        super().__init__(User, db)

    def find_by_username(self, username: str) -> Optional[User]:
        return self.find_one(username=username)

    def find_by_email(self, email: str) -> Optional[User]:
        return self.find_one(email=email)
