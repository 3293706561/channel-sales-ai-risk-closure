from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .database import Base, SessionLocal, engine
from .models import Risk, RiskSignal, Task, TaskUpdate, TimelineEvent, User
from .security import password_hash

DEMO_NOW = datetime(2026, 9, 2, 9, 30, tzinfo=timezone(timedelta(hours=8)))


def event(risk_id: str, event_type: str, actor_id: str | None, minutes: int, **payload):
    return TimelineEvent(risk_id=risk_id, event_type=event_type, actor_id=actor_id, payload=payload, created_at=DEMO_NOW + timedelta(minutes=minutes))


def signal(risk_id: str, type_: str, text: str, source: str, ref: str, minutes: int):
    return RiskSignal(risk_id=risk_id, type=type_, text=text, source=source, evidence_ref=ref, observed_at=DEMO_NOW + timedelta(minutes=minutes))


def seed_database(reset: bool = False) -> None:
    if reset:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal.begin() as db:
        if db.query(User).first():
            return
        users = [
            User(id="director-001", username="director", display_name="陈总", role="sales_director", region=None, password_hash=password_hash.hash("demo123")),
            User(id="manager-north", username="north_manager", display_name="李楠", role="regional_manager", region="华北", password_hash=password_hash.hash("demo123")),
            User(id="manager-east", username="east_manager", display_name="王玥", role="regional_manager", region="华东", password_hash=password_hash.hash("demo123")),
            User(id="sales-east", username="east_sales", display_name="周航", role="sales", region="华东", password_hash=password_hash.hash("demo123")),
        ]
        db.add_all(users)
        risks = [
            Risk(id="risk-north-032", rule_code="R-032", level="critical", status="pending_confirmation", title="华北大区月度目标达成风险", summary="近 7 日出货额持续低于计划，重点项目推进停滞。", region="华北", owner_id="manager-north", due_at=DEMO_NOW + timedelta(hours=8)),
            Risk(id="risk-east-027", rule_code="R-027", level="warning", status="in_progress", title="华东重点客户拜访履职风险", summary="重点客户有效拜访量下降，商机跟进记录滞后。", region="华东", owner_id="manager-east", due_at=DEMO_NOW + timedelta(days=1)),
            Risk(id="risk-south-019", rule_code="R-019", level="warning", status="pending_review", title="华南项目供货协同风险", summary="需求预估高于可售库存，整改材料等待区域复核。", region="华南", owner_id="manager-east", due_at=DEMO_NOW + timedelta(days=2)),
            Risk(id="risk-west-018", rule_code="R-018", level="warning", status="closed", title="西区渠道库存周转风险", summary="已完成库存调拨，复核通过后关闭。", region="西区", owner_id="manager-east", due_at=DEMO_NOW - timedelta(days=1)),
            Risk(id="risk-central-011", rule_code="R-011", level="warning", status="closed", title="中区项目跟进异常", summary="经人工核验为系统同步延迟造成的误报。", region="中区", owner_id="manager-north", due_at=DEMO_NOW - timedelta(days=2), false_positive_reason="项目跟进已在来源系统完成，同步延迟导致规则误报。"),
        ]
        db.add_all(risks)
        db.add_all([
            signal("risk-north-032", "sales_trend", "近 3 日日均出货额较前一周下降 24%", "模拟出货数据", "shipment:hb:2026-09-02", -30),
            signal("risk-north-032", "project_stagnation", "重点项目已 12 天无有效跟进记录", "模拟项目跟进", "project:hb-gift", -28),
            signal("risk-north-032", "daily_report_tag", "“货期不确定”标签在日报中出现 7 次", "模拟日报解析", "report-tag:leadtime", -26),
            signal("risk-east-027", "visit_trend", "有效拜访量较近 4 周均值下降 42%", "模拟拜访记录", "visit:east:weekly", -60),
            signal("risk-east-027", "opportunity_stale", "两条重点商机超过 8 天未更新", "模拟商机记录", "opportunity:east:stale", -58),
            signal("risk-south-019", "inventory_gap", "合同确认阶段需求高于可售库存 18%", "模拟库存数据", "inventory:south:gap", -90),
        ])
        tasks = [
            Task(id="task-east-027", risk_id="risk-east-027", assignee_id="sales-east", status="open", due_at=DEMO_NOW + timedelta(days=1)),
            Task(id="task-south-019", risk_id="risk-south-019", assignee_id="manager-east", status="pending_review", due_at=DEMO_NOW + timedelta(days=2), submitted_at=DEMO_NOW - timedelta(minutes=20)),
            Task(id="task-west-018", risk_id="risk-west-018", assignee_id="manager-east", status="closed", due_at=DEMO_NOW - timedelta(days=1), submitted_at=DEMO_NOW - timedelta(days=2), reviewed_at=DEMO_NOW - timedelta(days=1)),
        ]
        db.add_all(tasks)
        db.add_all([
            TaskUpdate(task_id="task-east-027", author_id="sales-east", content="已确认客户决策节点，周三安排联合拜访。", created_at=DEMO_NOW - timedelta(hours=1)),
            TaskUpdate(task_id="task-south-019", author_id="manager-east", content="已提交库存调拨记录和客户交期确认材料。", created_at=DEMO_NOW - timedelta(minutes=30)),
        ])
        db.add_all([
            event("risk-north-032", "rule_matched", None, -30),
            event("risk-east-027", "risk_confirmed_and_assigned", "manager-east", -120, task_id="task-east-027"),
            event("risk-south-019", "submitted_for_review", "manager-east", -20, task_id="task-south-019"),
            event("risk-west-018", "review_approved", "manager-east", -1440, task_id="task-west-018"),
            event("risk-central-011", "marked_false_positive", "manager-north", -2880, reason="系统同步延迟"),
        ])


if __name__ == "__main__":
    seed_database(reset=True)
