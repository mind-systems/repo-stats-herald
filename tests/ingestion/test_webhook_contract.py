"""Security/contract tests for POST /webhooks/github.

The route is a logic-free 501 stub at this stage — every test here is
expected to fail (red) against it, and must fail because the stub lacks the
verify/parse logic these assertions require, never because of an import or
fixture error. The follow-up task implements the route to turn these green.
"""

from tests.conftest import TEST_ORG_ID, TEST_ORG_LOGIN


def test_valid_signature_and_push_event_returns_populated_push_event(client, sign, push_payload):
    body = push_payload()

    response = client.post(
        "/webhooks/github",
        content=body,
        headers={
            "X-Hub-Signature-256": sign(body),
            "X-GitHub-Event": "push",
            "Content-Type": "application/json",
        },
    )

    assert response.status_code == 200
    event = response.json()
    assert event["branch"] == "main"
    assert event["org_id"] == TEST_ORG_ID
    assert isinstance(event["org_id"], int)
    assert event["org_login"] == TEST_ORG_LOGIN
    assert event["org_id"] != event["org_login"]

    [commit] = event["commits"]
    assert commit["sha"] == "abc123def456"
    assert commit["message"] == "Add feature"
    assert commit["added"] == ["src/new_file.py"]
    assert commit["modified"] == ["src/main.py"]
    assert commit["removed"] == []
    assert commit["author"] == "Jane Dev"


def test_feature_branch_ref_is_stripped_to_branch_name(client, sign, push_payload):
    body = push_payload(ref="refs/heads/feature/x")

    response = client.post(
        "/webhooks/github",
        content=body,
        headers={
            "X-Hub-Signature-256": sign(body),
            "X-GitHub-Event": "push",
            "Content-Type": "application/json",
        },
    )

    assert response.status_code == 200
    assert response.json()["branch"] == "feature/x"


def test_tampered_signature_is_rejected(client, sign, push_payload):
    body = push_payload()
    tampered_signature = sign(b"a different body entirely")

    response = client.post(
        "/webhooks/github",
        content=body,
        headers={
            "X-Hub-Signature-256": tampered_signature,
            "X-GitHub-Event": "push",
            "Content-Type": "application/json",
        },
    )

    assert response.status_code == 401
    assert "branch" not in response.text


def test_absent_signature_is_rejected(client, push_payload):
    body = push_payload()

    response = client.post(
        "/webhooks/github",
        content=body,
        headers={
            "X-GitHub-Event": "push",
            "Content-Type": "application/json",
        },
    )

    assert response.status_code == 401


def test_non_push_event_is_ignored(client, sign, push_payload):
    body = push_payload()

    response = client.post(
        "/webhooks/github",
        content=body,
        headers={
            "X-Hub-Signature-256": sign(body),
            "X-GitHub-Event": "ping",
            "Content-Type": "application/json",
        },
    )

    assert response.status_code == 204
