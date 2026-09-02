from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    username: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(60))
    role: Mapped[str] = mapped_column(String(30))
    region: Mapped[str | None] = mapped_column(String(40), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Risk(Base):
    __tablename__ = "risks"
    id: Mapped[str] = mapped_column(String(60), primary_key=True)
    rule_code: Mapped[str] = mapped_column(String(20), index=True)
    level: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(30), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    title: Mapped[str] = mapped_column(String(160))
    summary: Mapped[str] = mapped_column(Text)
    region: Mapped[str] = mapped_column(String(40), index=True)
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=True)
    false_positive_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner: Mapped[User | None] = relationship()
    signals: Mapped[list["RiskSignal"]] = relationship(back_populates="risk", cascade="all, delete-orphan")
    tasks: Mapped[list["Task"]] = relationship(back_populates="risk", cascade="all, delete-orphan")


class RiskSignal(Base):
    __tablename__ = "risk_signals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    risk_id: Mapped[str] = mapped_column(ForeignKey("risks.id"), index=True)
    type: Mapped[str] = mapped_column(String(40))
    text: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(80))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    evidence_ref: Mapped[str] = mapped_column(String(80))
    risk: Mapped[Risk] = relationship(back_populates="signals")


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[str] = mapped_column(String(60), primary_key=True)
    risk_id: Mapped[str] = mapped_column(ForeignKey("risks.id"), index=True)
    assignee_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(30), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    risk: Mapped[Risk] = relationship(back_populates="tasks")
    assignee: Mapped[User] = relationship()
    updates: Mapped[list["TaskUpdate"]] = relationship(back_populates="task", cascade="all, delete-orphan")


Index("uq_active_task_per_risk", Task.risk_id, unique=True, sqlite_where=Task.status.in_(("open", "pending_review")))


class TaskUpdate(Base):
    __tablename__ = "task_updates"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    task: Mapped[Task] = relationship(back_populates="updates")
    author: Mapped[User] = relationship()


class TimelineEvent(Base):
    __tablename__ = "timeline_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    risk_id: Mapped[str] = mapped_column(ForeignKey("risks.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(60))
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    actor: Mapped[User | None] = relationship()


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    endpoint: Mapped[str] = mapped_column(String(160), primary_key=True)
    response: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AIRun(Base):
    __tablename__ = "ai_runs"
    id: Mapped[str] = mapped_column(String(60), primary_key=True)
    use_case: Mapped[str] = mapped_column(String(40))
    provider: Mapped[str] = mapped_column(String(30))
    input_hash: Mapped[str] = mapped_column(String(64))
    output_json: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30))
    latency_ms: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
