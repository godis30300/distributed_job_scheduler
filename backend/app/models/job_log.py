import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class JobLog(Base):
    __tablename__ = "job_logs"
    __table_args__ = (
        CheckConstraint("log_level IN ('debug', 'info', 'warning', 'error')", name="ck_job_logs_level"),
        CheckConstraint("stream IN ('stdout', 'stderr', 'system')", name="ck_job_logs_stream"),
        Index("idx_job_logs_level_created_at", "log_level", "created_at"),
        Index("idx_job_logs_run_created_at", "job_run_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_run_id: Mapped[str] = mapped_column(String(36), ForeignKey("job_runs.id"), index=True, nullable=False)
    log_level: Mapped[str] = mapped_column(String(20), default="info", nullable=False)
    stream: Mapped[str] = mapped_column(String(20), default="system", nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True, nullable=False
    )

    run = relationship("JobRun", back_populates="logs")
