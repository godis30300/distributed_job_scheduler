from typing import Generic, TypeVar, Type, Any, Optional, Sequence
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.infrastructure.database.database import Base

T = TypeVar("T", bound=Base)

class BaseRepository(Generic[T]):
    def __init__(self, model: Type[T], db: Session):
        self.model = model
        self.db = db

    def get(self, id: Any) -> Optional[T]:
        """Fetch a single record by its primary key ID."""
        return self.db.query(self.model).filter(self.model.id == id).first()

    def find_one(self, **filters) -> Optional[T]:
        """Find the first record matching the given filters."""
        query = self.db.query(self.model)
        for field, value in filters.items():
            if hasattr(self.model, field):
                query = query.filter(getattr(self.model, field) == value)
        return query.first()

    def list(
        self, 
        skip: int = 0, 
        limit: int = 100, 
        order_by: Any = None,
        **filters
    ) -> Sequence[T]:
        """
        List records with support for filtering, pagination, and ordering.
        Default order is by created_at descending if the field exists.
        """
        query = self.db.query(self.model)
        
        # Apply filters
        for field, value in filters.items():
            if value is not None and hasattr(self.model, field):
                query = query.filter(getattr(self.model, field) == value)
        
        # Apply ordering
        if order_by is not None:
            query = query.order_by(order_by)
        elif hasattr(self.model, "created_at"):
            query = query.order_by(getattr(self.model, "created_at").desc())
            
        return query.offset(skip).limit(limit).all()

    def count(self, **filters) -> int:
        """Count records matching the given filters."""
        query = self.db.query(func.count(self.model.id))
        for field, value in filters.items():
            if value is not None and hasattr(self.model, field):
                query = query.filter(getattr(self.model, field) == value)
        return query.scalar() or 0

    def add(self, entity: T) -> T:
        """Add a new entity to the database session."""
        self.db.add(entity)
        return entity

    def remove(self, entity: T) -> None:
        """Delete an entity from the database session."""
        self.db.delete(entity)

    def commit(self):
        """Commit the current transaction."""
        self.db.commit()

    def flush(self):
        """Flush changes to the database without committing."""
        self.db.flush()

    def refresh(self, entity: T):
        """Refresh the state of an entity from the database."""
        self.db.refresh(entity)
