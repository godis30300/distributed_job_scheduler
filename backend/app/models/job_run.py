import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class JobRun(Base):
    __tablename__ = "job_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'success', 'failed', 'timeout', 'canceled')",
            name="ck_job_runs_status",
        ),
        CheckConstraint(
            "trigger_type IN ('schedule', 'manual', 'api', 'retry', 'dependency')",
            name="ck_job_runs_trigger_type",
        ),
        CheckConstraint("retry_count >= 0", name="ck_job_runs_retry_count_nonnegative"),
        CheckConstraint(
            "action_type IN ('api_call', 'shell', 'python', 'report', 'email', 'backup', 'fail-test', 'long-task')",
            name="ck_job_runs_action_type",
        ),
        CheckConstraint(
            "task_type IS NULL OR task_type IN ('api_call', 'shell', 'python', 'report', 'email', 'backup', 'fail-test', 'long-task')",
            name="ck_job_runs_task_type",
        ),
        CheckConstraint("timeout_seconds > 0", name="ck_job_runs_timeout_positive"),
        Index("idx_job_runs_status_created_at", "status", "created_at"),
        Index("idx_job_runs_pending_queue", "created_at", postgresql_where=text("status = 'pending'")),
        Index("idx_job_runs_user_id", "user_id"),
        Index("idx_job_runs_user_start_time", "user_id", "start_time"),
        Index("idx_job_runs_start_time", "start_time"),
        Index("idx_job_runs_job_status_created_at", "job_id", "status", "created_at"),
        Index("idx_job_runs_locked_until", "locked_until"),
        Index("idx_job_runs_task_type_created_at", "task_type", "created_at"),
        Index("idx_job_runs_pending_queue", "created_at", postgresql_where=text("status = 'pending'")),
        Index(
            "idx_job_runs_running_locks",
            "locked_until",
            postgresql_where=text("status = 'running' AND locked_until IS NOT NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id"), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), index=True, default="pending", nullable=False)
    # pending, running, success, failed, timeout, canceled

    user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    trigger_type: Mapped[str] = mapped_column(String(32), default="schedule", nullable=False)
    triggered_by: Mapped[str | None] = mapped_column(String(80), nullable=True)
    worker_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    locked_by: Mapped[str | None] = mapped_column(String(80), nullable=True)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_seconds_decimal: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    task_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    script: Mapped[str | None] = mapped_column(Text, nullable=True)
    working_dir: Mapped[str | None] = mapped_column(Text, nullable=True)
    action_type: Mapped[str] = mapped_column(String(40), nullable=False)
    action_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=300, nullable=False)
    stdout: Mapped[str | None] = mapped_column(Text, nullable=True)
    stderr: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    job = relationship("Job", back_populates="runs")
    logs = relationship("JobLog", back_populates="run", cascade="all, delete-orphan")

    @property
    def task_name(self) -> str:
        return self.job.task_name if self.job else "Unknown"

    @property
    def action(self) -> str:
        return self.action_type

    @property
    def duration(self) -> float | int | None:
        if self.duration_seconds_decimal is not None:
            return self.duration_seconds_decimal
        if self.duration_ms is not None:
            return round(self.duration_ms / 1000, 3)
        return self.duration_seconds

    @property
    def user(self) -> str:
        # If triggered_by is 'scheduler', it might not have a specific user context in the run record
        # but we can fallback to the job's creator.
        if self.triggered_by == "scheduler" and self.job:
            return self.job.user
        return self.triggered_by if self.triggered_by else "system"
