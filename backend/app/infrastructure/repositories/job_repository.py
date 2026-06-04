from typing import Optional
from sqlalchemy.orm import Session
from app.domain.entities.job import Job
from app.infrastructure.repositories.base_repository import BaseRepository

class JobRepository(BaseRepository[Job]):
    def __init__(self, db: Session):
        super().__init__(Job, db)

    def find_by_task_name(self, task_name: str) -> Optional[Job]:
        """Specific lookup for jobs by their unique task_name."""
        return self.find_one(task_name=task_name)

    def count_enabled(self) -> int:
        return self.count(enabled=True)
