import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.database import Base


class JobDependency(Base):
    __tablename__ = "job_dependencies"
    __table_args__ = (
        UniqueConstraint("job_id", "depends_on_job_id", name="uq_job_dependencies_pair"),
        CheckConstraint("job_id <> depends_on_job_id", name="ck_job_dependencies_not_self"),
        CheckConstraint(
            "required_status IN ('success', 'failed', 'timeout', 'canceled')",
            name="ck_job_dependencies_required_status",
        ),
        Index("idx_job_dependencies_job_id", "job_id"),
        Index("idx_job_dependencies_depends_on_job_id", "depends_on_job_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id"), index=True, nullable=False)
    depends_on_job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id"), index=True, nullable=False)
    required_status: Mapped[str] = mapped_column(String(32), default="success", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
