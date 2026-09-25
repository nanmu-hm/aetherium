from fastapi.testclient import TestClient

from engine.api import AetheriumApplication, RunRequest, create_app


def build_client(tmp_path):
    application = AetheriumApplication.create(
        seed=42,
        data_dir=tmp_path / "world",
        canon_path=tmp_path / "narrative-canon.jsonl",
    )
    return TestClient(create_app(application))


def test_root_and_health(tmp_path):
    client = build_client(tmp_path)

    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["name"] == "aetherium"

    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_dashboard_page_and_view_model(tmp_path):
    client = build_client(tmp_path)

    page = client.get("/dashboard/")
    assert page.status_code == 200
    assert "Aetherium World Dashboard" in page.text
    assert "/dashboard/app.js" in page.text

    model = client.get("/api/dashboard")
    assert model.status_code == 200
    payload = model.json()
    assert payload["summary"]["world_id"] == "demo"
    assert len(payload["characters"]) == 2
    assert "threads" in payload["narrative"]
    assert "discoveries" in payload["narrative"]


def test_world_summary_and_characters_are_read_only(tmp_path):
    client = build_client(tmp_path)

    summary = client.get("/api/world/summary").json()
    assert summary["world_id"] == "demo"
    assert summary["tick"] == 0
    assert summary["character_count"] == 2

    characters = client.get("/api/world/characters")
    assert characters.status_code == 200
    assert {item["id"] for item in characters.json()} == {"lin", "mei"}


def test_simulation_step_is_the_world_write_path(tmp_path):
    client = build_client(tmp_path)

    response = client.post("/api/simulation/step", json={"ticks": 2})
    assert response.status_code == 200
    payload = response.json()
    assert payload["ticks_run"] == 2
    assert payload["tick"] == 2
    assert len(payload["events"]) == 4

    summary = client.get("/api/world/summary").json()
    assert summary["tick"] == 2
    assert summary["event_count"] == 4


def test_agents_can_be_inspected_and_chatted_without_mutating_world(tmp_path):
    client = build_client(tmp_path)

    before = client.get("/api/world/summary").json()
    agents = client.get("/api/agents").json()
    ids = {item["agent_id"] for item in agents}
    assert "writer" in ids
    assert "continuity" in ids
    assert "critic" in ids
    assert "character:lin" in ids

    inspected = client.post("/api/agents/character:lin/inspect", json={})
    assert inspected.status_code == 200
    assert inspected.json()["result"]["status"] == "ok"

    chatted = client.post(
        "/api/agents/continuity/chat",
        json={"message": "Check continuity."},
    )
    assert chatted.status_code == 200
    assert chatted.json()["result"]["status"] == "ok"
    after = client.get("/api/world/summary").json()
    assert after == before


def test_narrative_observation_and_scene_generation_are_read_only(tmp_path):
    client = build_client(tmp_path)

    client.post("/api/simulation/step", json={"ticks": 1})
    narrative = client.get("/api/narrative").json()
    scenes = client.get("/api/narrative/scenes").json()

    assert narrative["pressure"] >= 0.0
    assert scenes
    assert scenes[0]["event_ids"]

    events = client.get("/api/world/events").json()
    assert len(events) == 2


def test_writer_draft_can_be_submitted_and_preserves_event_provenance(tmp_path):
    client = build_client(tmp_path)
    client.post("/api/simulation/step", json={"ticks": 1})
    scenes = client.get("/api/narrative/scenes").json()
    scene_id = scenes[0]["id"]

    response = client.post("/api/narrative/drafts", json={"scene_id": scene_id})
    assert response.status_code == 200
    draft = response.json()

    assert draft["status"] == "pending"
    assert draft["scene_id"] == scene_id
    assert draft["source_event_ids"] == scenes[0]["event_ids"]
    assert draft["participant_ids"]
    assert draft["branch_id"] == "main"


def test_draft_revision_and_approval_publish_only_to_narrative_canon(tmp_path):
    client = build_client(tmp_path)
    client.post("/api/simulation/step", json={"ticks": 1})
    scene_id = client.get("/api/narrative/scenes").json()[0]["id"]
    draft = client.post("/api/narrative/drafts", json={"scene_id": scene_id}).json()

    revised = client.post(
        f"/api/narrative/drafts/{draft['id']}/revise",
        json={"prose": "Human-edited prose.", "title": "Edited title", "edited_by": "tester"},
    )
    assert revised.status_code == 200
    latest = revised.json()
    assert latest["version"] == 2
    assert latest["status"] == "pending"
    assert latest["source_event_ids"] == draft["source_event_ids"]

    approved = client.post(
        f"/api/narrative/drafts/{draft['id']}/approve",
        json={"approved_by": "tester"},
    )
    assert approved.status_code == 200
    assert approved.json()["approved"] is True
    assert approved.json()["draft"]["status"] == "approved"

    canon = client.get("/api/narrative/canon").json()
    assert len(canon) == 1
    assert canon[0]["prose"] == "Human-edited prose."
    assert canon[0]["source_event_ids"] == draft["source_event_ids"]

    world = client.get("/api/world/summary").json()
    assert world["tick"] == 1
    assert world["event_count"] == 2


def test_autonomous_run_endpoint_uses_the_safe_controller(tmp_path):
    client = build_client(tmp_path)

    response = client.post(
        "/api/simulation/run",
        json={
            "max_ticks": 3,
            "checkpoint_every": 1,
            "checkpoint_before_run": True,
        },
    )
    assert response.status_code == 200
    report = response.json()
    assert report["status"] == "max_ticks"
    assert report["ticks_run"] == 3
    assert report["end_tick"] == 3
    assert report["checkpoints"] == [
        "main-tick-0",
        "main-tick-1",
        "main-tick-2",
        "main-tick-3",
    ]


def test_invalid_agent_and_invalid_run_are_rejected(tmp_path):
    client = build_client(tmp_path)

    response = client.post("/api/agents/unknown/inspect", json={})
    assert response.status_code == 404

    response = client.post("/api/simulation/run", json={"max_ticks": 0})
    assert response.status_code == 422


def test_api_run_request_matches_controller_limits(tmp_path):
    request = RunRequest(max_ticks=2, checkpoint_every=0)
    assert request.max_ticks == 2
    assert request.checkpoint_every == 0
\ndef test_dashboard_assets_are_served_as_browser_files(tmp_path):\n    client = build_client(tmp_path)\n\n    script = client.get("/dashboard/app.js")\n    style = client.get("/dashboard/style.css")\n\n    assert script.status_code == 200\n    assert 'fetch("/api/dashboard?limit=80")' in script.text\n    assert "renderGraph" in script.text\n\n    assert style.status_code == 200\n    assert ".character-list" in style.text\n