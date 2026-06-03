import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym

from app.infrastructure.database.database import Base
from app.services.schedule_utils import compute_next_run


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint(
            "action_type IN ('api_call', 'shell', 'python', 'report', 'email', 'backup', 'fail-test', 'long-task', 'api_poll')",
            name="ck_jobs_action_type",
        ),
        CheckConstraint(
            "task_type IS NULL OR task_type IN ('api_call', 'shell', 'python', 'report', 'email', 'backup', 'fail-test', 'long-task', 'api_poll')",
            name="ck_jobs_task_type",
        ),
        CheckConstraint("status IN ('enabled', 'active', 'paused', 'disabled', 'deleted')", name="ck_jobs_status"),
        CheckConstraint("timeout_seconds > 0", name="ck_jobs_timeout_positive"),
        CheckConstraint("max_retry >= 0", name="ck_jobs_max_retry_nonnegative"),
        Index("idx_jobs_status", "status"),
        Index("idx_jobs_enabled_status_next_run_at", "enabled", "status", "next_run_at"),
        Index("idx_jobs_user_id", "user_id"),
        Index("idx_jobs_next_run_at", "next_run_at"),
        Index("idx_jobs_name", "name"),
        Index("idx_jobs_task_type", "task_type"),
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
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    task_name: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    task_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    script: Mapped[str | None] = mapped_column(Text, nullable=True)
    working_dir: Mapped[str | None] = mapped_column(Text, nullable=True)
    action_type: Mapped[str] = mapped_column(String(40), nullable=False)
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

    def are_dependencies_satisfied(self, db_session) -> bool:
        """
        DDD Domain Logic: Check if all upstream dependencies are satisfied.
        """
        from app.domain.entities.job_dependency import JobDependency
        from app.domain.entities.job_run import JobRun

        deps = db_session.query(JobDependency).filter(JobDependency.job_id == self.id).all()
        if not deps:
            return True

        for dep in deps:
            latest_run = (
                db_session.query(JobRun)
                .filter(JobRun.job_id == dep.depends_on_job_id)
                .order_by(JobRun.created_at.desc())
                .first()
            )
            if not latest_run:
                return False
            if latest_run.status != dep.required_status:
                return False
        return True

    def sync_domain_logic(self):
        """
        DDD: Consolidate normalization and domain logic inside the model.
        """
        # 1. Normalize status
        if not self.status:
            self.status = "enabled"
            
        # 2. Sync enabled based on status
        if self.status in ("enabled", "active"):
            self.enabled = True
        else:
            self.enabled = False
        
        # 3. Update next_run_at
        if self.enabled and self.schedule_rule and self.schedule_rule != "manual":
            try:
                self.next_run_at = compute_next_run(self.schedule_rule)
            except ValueError:
                self.next_run_at = None
        else:
            # If disabled or manual, clear next_run_at to prevent scheduling
            self.next_run_at = None

        # 4. Normalize action_payload
        if self.action_payload is None:
            self.action_payload = {}
        if self.script is not None:
            self.action_payload["script"] = self.script
        if self.working_dir is not None:
            self.action_payload["working_dir"] = self.working_dir

    @property
    def action(self) -> str:
        return self.action_type

    @property
    def effective_name(self) -> str:
        return self.name or self.task_name

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

    @property
    def user(self) -> str:
        return self.creator.username if self.creator else "system"

    @property
    def created_by(self) -> str:
        return self.user
