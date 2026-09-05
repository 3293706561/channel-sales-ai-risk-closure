from __future__ import annotations

import hashlib
import json
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from .database import SessionLocal
from .models import AIRun, IdempotencyRecord, Risk, Task, TaskUpdate, TimelineEvent, User
from .security import issue_token, password_hash, sessions
from .seed import DEMO_NOW, seed_database


@asynccontextmanager
async def lifespan(_app: FastAPI):
    seed_database()
    yield


app = FastAPI(title="特渠销售 AI 经营风险闭环系统", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:8000"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "请先登录。")
    user_id = sessions.get(authorization.removeprefix("Bearer "))
    user = db.get(User, user_id) if user_id else None
    if not user or not user.is_active:
        raise HTTPException(401, "登录已失效，请重新登录。")
    return user


def now() -> datetime:
    return datetime.now(timezone.utc)


def user_data(user: User | None):
    return None if not user else {"id": user.id, "name": user.display_name, "role": user.role, "region": user.region}


def risk_data(risk: Risk, detail: bool = False):
    payload = {
        "id": risk.id, "ruleCode": risk.rule_code, "level": risk.level, "status": risk.status,
        "version": risk.version, "title": risk.title, "summary": risk.summary, "region": risk.region,
        "owner": user_data(risk.owner), "dueAt": risk.due_at, "isDemoData": risk.is_demo,
    }
    if detail:
        payload["signals"] = [{"id": item.id, "type": item.type, "text": item.text, "source": item.source, "evidenceRef": item.evidence_ref, "observedAt": item.observed_at} for item in risk.signals]
        active_task = next((task for task in risk.tasks if task.status in {"open", "pending_review"}), None)
        payload["task"] = task_data(active_task) if active_task else None
        payload["timeline"] = []
        payload["falsePositiveReason"] = risk.false_positive_reason
    return payload


def task_data(task: Task | None):
    if not task:
        return None
    return {
        "id": task.id, "riskId": task.risk_id, "status": task.status, "version": task.version,
        "assignee": user_data(task.assignee), "dueAt": task.due_at, "submittedAt": task.submitted_at,
        "reviewedAt": task.reviewed_at,
        "updates": [{"content": update.content, "author": user_data(update.author), "at": update.created_at} for update in task.updates],
    }


def can_view(user: User, risk: Risk) -> bool:
    return user.role == "sales_director" or risk.owner_id == user.id or any(task.assignee_id == user.id for task in risk.tasks)


def require_manager_for_risk(user: User, risk: Risk):
    if user.role != "regional_manager" or risk.owner_id != user.id:
        raise HTTPException(403, "只有该风险所属的区域经理可以执行此操作。")


def require_version(value: int, current: int):
    if value != current:
        raise HTTPException(409, "状态已变更，请刷新后重试。")


def add_event(db: Session, risk_id: str, event_type: str, actor: User | None, **payload):
    db.add(TimelineEvent(risk_id=risk_id, event_type=event_type, actor_id=actor.id if actor else None, payload=payload, created_at=now()))


def idempotent_response(db: Session, key: str | None, user: User, endpoint: str):
    if not key:
        raise HTTPException(400, "关键状态变更必须提供 Idempotency-Key。")
    record = db.get(IdempotencyRecord, {"key": key, "user_id": user.id, "endpoint": endpoint})
    return record.response if record else None


def remember_response(db: Session, key: str, user: User, endpoint: str, response: dict):
    db.add(IdempotencyRecord(key=key, user_id=user.id, endpoint=endpoint, response=jsonable_encoder(response), created_at=now()))


class LoginBody(BaseModel):
    username: str
    password: str


class ConfirmBody(BaseModel):
    assigneeId: str
    note: str = Field(min_length=2, max_length=500)
    version: int


class DismissBody(BaseModel):
    reason: str = Field(min_length=2, max_length=500)
    version: int


class UpdateBody(BaseModel):
    content: str = Field(min_length=2, max_length=1000)
    version: int


class ReviewBody(BaseModel):
    note: str = Field(min_length=2, max_length=500)
    version: int


class DailyReportBody(BaseModel):
    text: str = Field(min_length=2, max_length=3000)


@app.get("/api/health")
def health():
    return {"ok": True, "provider": "mock", "demoNow": DEMO_NOW}


@app.post("/api/auth/login")
def login(body: LoginBody, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == body.username))
    if not user or not password_hash.verify(body.password, user.password_hash):
        raise HTTPException(401, "用户名或密码错误。")
    return {"accessToken": issue_token(user.id), "user": user_data(user), "isDemoAccount": True}


@app.get("/api/auth/me")
def me(user: User = Depends(get_current_user)):
    return {"user": user_data(user)}


@app.get("/api/dashboard")
def dashboard(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    risks = db.scalars(select(Risk).options(joinedload(Risk.owner), joinedload(Risk.tasks))).unique().all()
    visible = [risk for risk in risks if can_view(user, risk)]
    visible_risks = {risk.id: risk for risk in visible}
    events = db.scalars(select(TimelineEvent).options(joinedload(TimelineEvent.actor)).order_by(TimelineEvent.created_at.desc())).all()
    recent_events = [
        {"event": event.event_type, "riskId": event.risk_id, "riskTitle": visible_risks[event.risk_id].title,
         "actor": user_data(event.actor), "at": event.created_at, "payload": event.payload}
        for event in events if event.risk_id in visible_risks
    ][:4]
    return {"isDemoData": True, "dataUpdatedAt": DEMO_NOW, "metrics": {"pendingConfirmation": sum(r.status == "pending_confirmation" for r in visible), "inProgress": sum(r.status == "in_progress" for r in visible), "pendingReview": sum(r.status == "pending_review" for r in visible), "closed": sum(r.status == "closed" for r in visible)}, "priorityRisks": [risk_data(risk) for risk in visible if risk.status != "closed"], "recentEvents": recent_events}


@app.get("/api/risks")
def list_risks(level: str | None = None, status: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    risks = db.scalars(select(Risk).options(joinedload(Risk.owner), joinedload(Risk.tasks)).order_by(Risk.due_at)).unique().all()
    items = [risk for risk in risks if can_view(user, risk) and (not level or risk.level == level) and (not status or risk.status == status)]
    return {"isDemoData": True, "dataUpdatedAt": DEMO_NOW, "items": [risk_data(risk) for risk in items]}


@app.get("/api/risks/{risk_id}")
def get_risk(risk_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    risk = db.scalar(select(Risk).options(joinedload(Risk.owner), joinedload(Risk.signals), joinedload(Risk.tasks).joinedload(Task.assignee), joinedload(Risk.tasks).joinedload(Task.updates).joinedload(TaskUpdate.author)).where(Risk.id == risk_id))
    if not risk or not can_view(user, risk):
        raise HTTPException(404, "未找到该风险。")
    events = db.scalars(select(TimelineEvent).options(joinedload(TimelineEvent.actor)).where(TimelineEvent.risk_id == risk.id).order_by(TimelineEvent.created_at)).all()
    payload = risk_data(risk, detail=True)
    payload["timeline"] = [{"event": event.event_type, "actor": user_data(event.actor), "at": event.created_at, "payload": event.payload} for event in events]
    return payload


@app.post("/api/risks/{risk_id}/confirm")
def confirm_risk(risk_id: str, body: ConfirmBody, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    endpoint = f"risk:{risk_id}:confirm"
    replay = idempotent_response(db, idempotency_key, user, endpoint)
    if replay:
        return replay
    db.rollback()
    with db.begin():
        risk = db.get(Risk, risk_id)
        if not risk:
            raise HTTPException(404, "未找到该风险。")
        require_manager_for_risk(user, risk)
        if risk.status != "pending_confirmation":
            raise HTTPException(409, "当前风险不能再次确认并指派。")
        require_version(body.version, risk.version)
        assignee = db.get(User, body.assigneeId)
        if not assignee or assignee.role not in {"sales", "regional_manager"}:
            raise HTTPException(422, "请选择有效的整改责任人。")
        task = Task(id=f"task-{uuid.uuid4().hex[:10]}", risk_id=risk.id, assignee_id=assignee.id, status="open", due_at=risk.due_at)
        risk.status, risk.version = "in_progress", risk.version + 1
        db.add(task)
        add_event(db, risk.id, "risk_confirmed_and_assigned", user, task_id=task.id, note=body.note, assignee_id=assignee.id)
        response = {"risk": {"id": risk.id, "status": risk.status, "version": risk.version}, "task": {"id": task.id, "status": task.status, "version": task.version}, "message": "整改任务已创建。"}
        remember_response(db, idempotency_key, user, endpoint, response)
    return response


@app.post("/api/risks/{risk_id}/dismiss")
def dismiss_risk(risk_id: str, body: DismissBody, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    endpoint = f"risk:{risk_id}:dismiss"
    replay = idempotent_response(db, idempotency_key, user, endpoint)
    if replay:
        return replay
    db.rollback()
    with db.begin():
        risk = db.get(Risk, risk_id)
        if not risk:
            raise HTTPException(404, "未找到该风险。")
        require_manager_for_risk(user, risk)
        if risk.status != "pending_confirmation":
            raise HTTPException(409, "当前风险不能标记为误报。")
        require_version(body.version, risk.version)
        risk.status, risk.false_positive_reason, risk.version = "closed", body.reason, risk.version + 1
        add_event(db, risk.id, "marked_false_positive", user, reason=body.reason)
        response = {"risk": {"id": risk.id, "status": risk.status, "version": risk.version}, "message": "已标记为误报并保留记录。"}
        remember_response(db, idempotency_key, user, endpoint, response)
    return response


def get_task_or_404(db: Session, task_id: str) -> Task:
    task = db.scalar(select(Task).options(joinedload(Task.risk), joinedload(Task.assignee)).where(Task.id == task_id))
    if not task:
        raise HTTPException(404, "未找到整改任务。")
    return task


@app.get("/api/tasks")
def list_tasks(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    tasks = db.scalars(select(Task).options(joinedload(Task.risk), joinedload(Task.assignee)).order_by(Task.due_at)).all()
    visible = [task for task in tasks if user.role == "sales_director" or task.assignee_id == user.id or task.risk.owner_id == user.id]
    return {"items": [{**task_data(task), "risk": risk_data(task.risk)} for task in visible]}


@app.post("/api/tasks/{task_id}/updates")
def update_task(task_id: str, body: UpdateBody, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.rollback()
    with db.begin():
        task = get_task_or_404(db, task_id)
        if task.assignee_id != user.id:
            raise HTTPException(403, "只有任务责任人可以补充进度。")
        if task.status != "open":
            raise HTTPException(409, "当前任务不能补充进度。")
        require_version(body.version, task.version)
        task.version += 1
        db.add(TaskUpdate(task_id=task.id, author_id=user.id, content=body.content, created_at=now()))
        add_event(db, task.risk_id, "task_progress_updated", user, task_id=task.id)
        return {"task": task_data(task), "message": "整改进度已保存。"}


@app.post("/api/tasks/{task_id}/submit-review")
def submit_review(task_id: str, body: ReviewBody, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    endpoint = f"task:{task_id}:submit-review"
    replay = idempotent_response(db, idempotency_key, user, endpoint)
    if replay:
        return replay
    db.rollback()
    with db.begin():
        task = get_task_or_404(db, task_id)
        if task.assignee_id != user.id:
            raise HTTPException(403, "只有任务责任人可以提交复核。")
        if task.status != "open" or task.risk.status != "in_progress":
            raise HTTPException(409, "当前任务不能提交复核。")
        require_version(body.version, task.version)
        task.status, task.version, task.submitted_at = "pending_review", task.version + 1, now()
        task.risk.status, task.risk.version = "pending_review", task.risk.version + 1
        add_event(db, task.risk_id, "submitted_for_review", user, task_id=task.id, note=body.note)
        response = {"task": task_data(task), "risk": {"id": task.risk.id, "status": task.risk.status, "version": task.risk.version}, "message": "已提交人工复核。"}
        remember_response(db, idempotency_key, user, endpoint, response)
    return response


def review_task(task_id: str, body: ReviewBody, approved: bool, idempotency_key: str | None, user: User, db: Session):
    endpoint = f"task:{task_id}:{'approve' if approved else 'return'}"
    replay = idempotent_response(db, idempotency_key, user, endpoint)
    if replay:
        return replay
    db.rollback()
    with db.begin():
        task = get_task_or_404(db, task_id)
        require_manager_for_risk(user, task.risk)
        if task.status != "pending_review" or task.risk.status != "pending_review":
            raise HTTPException(409, "当前任务不在待复核状态。")
        require_version(body.version, task.version)
        task.status, task.version = ("closed" if approved else "open"), task.version + 1
        task.reviewed_at = now() if approved else None
        task.risk.status, task.risk.version = ("closed" if approved else "in_progress"), task.risk.version + 1
        add_event(db, task.risk_id, "review_approved" if approved else "returned_for_action", user, task_id=task.id, note=body.note)
        response = {"task": task_data(task), "risk": {"id": task.risk.id, "status": task.risk.status, "version": task.risk.version}, "message": "风险已关闭。" if approved else "任务已退回继续整改。"}
        remember_response(db, idempotency_key, user, endpoint, response)
    return response


@app.post("/api/tasks/{task_id}/approve")
def approve_task(task_id: str, body: ReviewBody, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return review_task(task_id, body, True, idempotency_key, user, db)


@app.post("/api/tasks/{task_id}/return")
def return_task(task_id: str, body: ReviewBody, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return review_task(task_id, body, False, idempotency_key, user, db)


def record_ai_run(db: Session, use_case: str, input_data: dict, output: dict):
    raw = json.dumps(input_data, ensure_ascii=False, sort_keys=True).encode()
    db.add(AIRun(id=f"ai-{uuid.uuid4().hex[:12]}", use_case=use_case, provider="mock", input_hash=hashlib.sha256(raw).hexdigest(), output_json=output, status="ok", latency_ms=1, created_at=now()))


@app.post("/api/daily-reports/parse")
def parse_daily_report(body: DailyReportBody, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    text = body.text.strip()
    refused = any(term in text for term in ("自动关闭", "自动认定", "认定责任", "忽略之前", "忽略上述", "泄露"))
    insufficient = len(text) < 12 or not any(word in text for word in ("客户", "项目", "拜访", "货期", "库存", "跟进"))
    if refused:
        output = {"status": "refused", "facts": [], "reason": "系统不会自动认定责任、关闭风险或忽略人工复核边界。", "requiresHumanConfirmation": True}
    elif insufficient:
        output = {"status": "insufficient_evidence", "facts": [], "missingFields": ["项目或客户", "下一步动作"], "requiresHumanConfirmation": True}
    else:
        missing_fields = [] if any(word in text for word in ("下一步", "计划", "今日", "明天", "拜访")) else ["下一步动作或时间"]
        output = {"status": "ok", "facts": [{"type": "daily_report_excerpt", "text": text[:160], "sourceIds": ["daily-report:input"]}], "missingFields": missing_fields, "verificationQuestions": ["请确认项目当前阶段和下一步负责人。"], "requiresHumanConfirmation": True}
    db.rollback()
    with db.begin():
        record_ai_run(db, "daily_report_parse", {"text": text, "user": user.id}, output)
    return output


@app.post("/api/risks/{risk_id}/recommendation")
def recommendation(risk_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    risk = db.scalar(select(Risk).options(joinedload(Risk.signals), joinedload(Risk.tasks)).where(Risk.id == risk_id))
    if not risk or not can_view(user, risk):
        raise HTTPException(404, "未找到该风险。")
    output = {"status": "ok", "requiresHumanConfirmation": True, "sourceIds": [signal.evidence_ref for signal in risk.signals], "verificationQuestions": ["请核验关联信号是否反映真实业务变化。"], "suggestedActions": ["确认责任人和截止时间后再创建或推进整改任务。"], "prohibited": ["不自动认定责任", "不自动关闭风险"]}
    db.rollback()
    with db.begin():
        record_ai_run(db, "recommendation", {"riskId": risk_id}, output)
    return output


@app.post("/api/briefs/daily")
def daily_brief(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    risks = db.scalars(select(Risk).options(joinedload(Risk.tasks)).where(Risk.status != "closed")).unique().all()
    risks = [risk for risk in risks if can_view(user, risk)]
    output = {"status": "ok", "requiresHumanConfirmation": True, "facts": [{"riskId": risk.id, "text": risk.title, "status": risk.status} for risk in risks], "summary": f"当前共有 {len(risks)} 条未关闭风险，建议优先处理待确认和待复核事项。"}
    db.rollback()
    with db.begin():
        record_ai_run(db, "daily_brief", {"user": user.id, "riskIds": [risk.id for risk in risks]}, output)
    return output


FRONTEND_DIR = Path(__file__).resolve().parents[2] / "app_frontend"
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
