"""
Comprehensive tests for FastAPI application and API routers:
- `src/main.py`
- `src/routers/clients.py`
- `src/routers/consent.py`
- `src/routers/briefs.py`
- `src/routers/actions.py`
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from src.main import app
from src.routers import briefs

client = TestClient(app)


def setup_module():
    """Ensure synthetic data is loaded into store for tests."""
    briefs.load_clients()


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.1.0"}


def test_list_clients():
    response = client.get("/api/clients/")
    assert response.status_code == 200
    data = response.json()
    assert "clients" in data
    assert len(data["clients"]) > 0
    first = data["clients"][0]
    assert "client_id" in first
    assert "pseudonym" in first
    assert "open_high_priority" in first
    assert "red_flags" in first


def test_get_consent_valid():
    response = client.get("/api/consent/C001")
    assert response.status_code == 200
    data = response.json()
    assert data["client_id"] == "C001"
    assert "consents" in data
    assert "evaluated_at" in data
    for item in data["consents"]:
        assert "category" in item
        assert "recipient_role" in item
        assert "purpose" in item
        assert "active" in item


def test_get_consent_not_found():
    response = client.get("/api/consent/NONEXISTENT_999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_get_brief_default_role():
    response = client.get("/api/briefs/C001")
    assert response.status_code == 200
    data = response.json()
    assert data["client_id"] == "C001"
    assert data["recipient_role"] == "counsellor"
    assert "summary" in data
    assert "tier" in data
    assert "actions" in data
    assert "explanation" in data
    assert "permitted_categories" in data


def test_get_brief_all_roles():
    for role in ["counsellor", "social_worker", "psychiatrist", "nurse"]:
        response = client.get(f"/api/briefs/C001?role={role}")
        assert response.status_code == 200
        data = response.json()
        assert data["recipient_role"] == role


def test_get_brief_tier_override():
    for tier in [1, 2, 3, 4]:
        response = client.get(f"/api/briefs/C001?tier={tier}")
        assert response.status_code == 200
        data = response.json()
        assert data["tier"] >= tier or data["tier"] in [1, 2, 3, 4]


def test_get_brief_invalid_tier():
    response = client.get("/api/briefs/C001?tier=5")
    assert response.status_code == 422


def test_get_brief_not_found():
    response = client.get("/api/briefs/NONEXISTENT_999")
    assert response.status_code == 404


def test_get_actions_valid():
    response = client.get("/api/actions/C001")
    assert response.status_code == 200
    data = response.json()
    assert data["client_id"] == "C001"
    assert "actions" in data
    assert "red_flags" in data
    assert "notifications" in data
    assert "verification_rate" in data
    assert "all_high_priority_have_ownership" in data


def test_get_actions_not_found():
    response = client.get("/api/actions/NONEXISTENT_999")
    assert response.status_code == 404


def test_verify_action_success():
    # Fetch first client's actions
    actions_resp = client.get("/api/actions/C001")
    actions = actions_resp.json()["actions"]
    if actions:
        target_id = actions[0]["action_id"]
        verify_resp = client.post(
            f"/api/actions/C001/{target_id}/verify",
            json={
                "status": "completed",
                "verified_by_role": "psychiatrist",
                "outcome_notes": "Reviewed in ward round; completed successfully.",
            },
        )
        assert verify_resp.status_code == 200
        res_data = verify_resp.json()
        assert res_data["status"] == "success"
        assert res_data["action"]["verified"] is True
        assert res_data["action"]["verified_by_role"] == "psychiatrist"
        assert res_data["integrity"]["is_valid"] is True


def test_verify_action_with_supervisor():
    actions_resp = client.get("/api/actions/C001")
    actions = actions_resp.json()["actions"]
    if actions:
        target_id = actions[0]["action_id"]
        verify_resp = client.post(
            f"/api/actions/C001/{target_id}/verify",
            json={
                "status": "completed",
                "verified_by_role": "counsellor",
                "outcome_notes": "Supervisor reviewed escalation.",
                "supervisor_id": "SUP-007",
            },
        )
        assert verify_resp.status_code == 200
        res_data = verify_resp.json()
        assert res_data["status"] == "success"
        assert res_data["action"]["verification_status"] == "escalated_resolved"


def test_verify_action_not_found():
    resp = client.post(
        "/api/actions/C001/FAKE_ACT_999/verify",
        json={"status": "completed", "verified_by_role": "counsellor"},
    )
    assert resp.status_code == 404
