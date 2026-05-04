import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym

from app.core.database import Base


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint(
            "action_type IN ('api_call', 'shell', 'report', 'email', 'backup', 'fail-test', 'long-task')",
            name="ck_jobs_action_type",
        ),
        CheckConstraint("status IN ('enabled', 'active', 'paused', 'disabled', 'deleted')", name="ck_jobs_status"),
        CheckConstraint("timeout_seconds > 0", name="ck_jobs_timeout_positive"),
        CheckConstraint("max_retry >= 0", name="ck_jobs_max_retry_nonnegative"),
        Index("idx_jobs_status", "status"),
        Index("idx_jobs_user_id", "user_id"),
        Index("idx_jobs_next_run_at", "next_run_at"),
        Index(
            "idx_jobs_due_schedule",
            "next_run_at",
            postgresql_where=text(
                "enabled = TRUE AND status IN ('enabled', 'active') AND next_run_at IS NOT NULL"
            ),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    task_name: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    action_type: Mapped[str] = mapped_column(String(40), nullable=False)  # api_call, shell
    action_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    schedule_rule: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="enabled", nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=300, nullable=False)
    max_retry: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Compatibility alias for existing API schemas/controllers.
    created_by = synonym("user_id")

    @property
    def action(self) -> str:
        return self.action_type

    @property
    def retry_limit(self) -> int:
        return self.max_retry

    @property
    def schedule_type(self) -> str:
        if self.schedule_rule == "manual":
            return "manual"
        if self.schedule_rule.startswith("every:"):
            return "interval"
        return "cron"

    @property
    def cron_expression(self) -> str | None:
        return self.schedule_rule if self.schedule_type == "cron" else None

    @property
    def interval_seconds(self) -> int | None:
        if self.schedule_type != "interval":
            return None
        value = self.schedule_rule.split(":", 1)[1].strip()
        if value.endswith("s"):
            return int(value[:-1])
        if value.endswith("m"):
            return int(value[:-1]) * 60
        if value.endswith("h"):
            return int(value[:-1]) * 3600
        return None

    creator = relationship("User", back_populates="jobs")
    runs = relationship("JobRun", back_populates="job", cascade="all, delete-orphan")
