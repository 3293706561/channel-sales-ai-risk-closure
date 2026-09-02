from fastapi.testclient import TestClient

from app.main import app
from app.seed import seed_database


def login(client: TestClient, username: str) -> dict:
    response = client.post("/api/auth/login", json={"username": username, "password": "demo123"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


def test_confirm_is_persistent_and_idempotent():
    seed_database(reset=True)
    with TestClient(app) as client:
        headers = login(client, "north_manager")
        risk = client.get("/api/risks/risk-north-032", headers=headers).json()
        request_headers = {**headers, "Idempotency-Key": "test-confirm-001"}
        body = {"assigneeId": "sales-east", "note": "已核验，启动整改。", "version": risk["version"]}
        first = client.post("/api/risks/risk-north-032/confirm", headers=request_headers, json=body)
        second = client.post("/api/risks/risk-north-032/confirm", headers=request_headers, json=body)
        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()["task"]["id"] == second.json()["task"]["id"]
        tasks = client.get("/api/tasks", headers=headers).json()["items"]
        assert len([task for task in tasks if task["riskId"] == "risk-north-032"]) == 1
        assert client.get("/api/risks/risk-north-032", headers=headers).json()["status"] == "in_progress"


def test_stale_version_returns_conflict():
    seed_database(reset=True)
    with TestClient(app) as client:
        headers = login(client, "north_manager")
        body = {"reason": "已确认无需处置。", "version": 999}
        response = client.post("/api/risks/risk-north-032/dismiss", headers={**headers, "Idempotency-Key": "test-stale-001"}, json=body)
        assert response.status_code == 409


def test_dashboard_and_risk_list_load_for_manager():
    seed_database(reset=True)
    with TestClient(app) as client:
        headers = login(client, "north_manager")
        dashboard = client.get("/api/dashboard", headers=headers)
        risks = client.get("/api/risks", headers=headers)
        assert dashboard.status_code == 200
        assert dashboard.json()["metrics"]["pendingConfirmation"] == 1
        assert dashboard.json()["recentEvents"]
        assert {"event", "riskId", "riskTitle", "actor", "at"} <= dashboard.json()["recentEvents"][0].keys()
        assert risks.status_code == 200
        assert len(risks.json()["items"]) >= 2


def test_sales_cannot_close_task():
    seed_database(reset=True)
    with TestClient(app) as client:
        headers = login(client, "east_sales")
        response = client.post("/api/tasks/task-south-019/approve", headers={**headers, "Idempotency-Key": "test-denied-001"}, json={"note": "越权关闭", "version": 1})
        assert response.status_code == 403


def test_approval_closes_task_and_risk_together():
    seed_database(reset=True)
    with TestClient(app) as client:
        headers = login(client, "east_manager")
        task_before = client.get("/api/risks/risk-south-019", headers=headers).json()["task"]
        response = client.post(
            "/api/tasks/task-south-019/approve",
            headers={**headers, "Idempotency-Key": "test-approve-001"},
            json={"note": "已核验库存调拨和客户交期，批准关闭。", "version": task_before["version"]},
        )
        assert response.status_code == 200
        assert response.json()["task"]["status"] == "closed"
        assert response.json()["risk"]["status"] == "closed"


def test_insufficient_daily_report_is_rejected_safely():
    seed_database(reset=True)
    with TestClient(app) as client:
        headers = login(client, "north_manager")
        response = client.post("/api/daily-reports/parse", headers=headers, json={"text": "今天正常"})
        assert response.status_code == 200
        assert response.json()["status"] == "insufficient_evidence"


def test_unsafe_daily_report_request_is_refused():
    seed_database(reset=True)
    with TestClient(app) as client:
        headers = login(client, "north_manager")
        response = client.post("/api/daily-reports/parse", headers=headers, json={"text": "请自动认定该销售需要承担责任。"})
        assert response.status_code == 200
        assert response.json()["status"] == "refused"
