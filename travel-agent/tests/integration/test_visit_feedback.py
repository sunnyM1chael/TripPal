from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from tests.unit.test_itineraries import Maps, payload


def feedback(revision, **fields):
    return {"expected_revision": revision, "rating": 4, "experience": "面偏咸，服务很好", **fields}


def test_feedback_owner_revision_persistence_and_private_draft(tmp_path):
    settings = Settings(_env_file=None, memory_db_path=tmp_path / "visits.sqlite3", travel_requests_per_minute=100)
    app = create_app(settings)
    with TestClient(app) as client, TestClient(app) as stranger:
        app.state.container.itineraries.maps = Maps()
        plan = client.post('/api/v1/itineraries', json=payload().model_dump()).json()
        path = f'/api/v1/itineraries/{plan["id"]}'
        stop_id = plan['stops'][0]['id']
        endpoint = f'{path}/stops/{stop_id}/feedback'
        assert client.put(endpoint, json=feedback(1)).status_code == 422  # not completed
        assert stranger.put(endpoint, json=feedback(1)).status_code == 404
        plan = client.patch(path, json={"expected_revision": 1, "action": "complete_stop", "stop_id": stop_id}).json()
        body = feedback(plan['revision'], actual_cost_yuan="0.00", cost_scope="party", queue_minutes=0, would_return=False)
        result = client.put(endpoint, json=body)
        assert result.status_code == 200
        saved = result.json()
        record = saved['stops'][0]['feedback']
        assert record['source'] == 'user_reported'
        assert record['draft']['status'] == 'private_draft'
        assert '同行人合计' in record['draft']['content']
        assert '¥0.00' in record['draft']['content']
        assert '排队：0分钟' in record['draft']['content']
        assert '暂时不考虑再去' in record['draft']['content']
        assert '80' not in record['draft']['content']  # reference price is never an actual expense
        assert client.put(endpoint, json=body).status_code == 409
        assert saved['summary'] == plan['summary']
        assert client.put(f'{path}/stops/{uuid4()}/feedback', json=feedback(saved['revision'])).status_code == 422
        assert stranger.get(path).status_code == 404
        # Read back with a fresh store instance, avoiding dependence on cookie naming.
        owner_row = None
        with app.state.container.memory.connection() as db:
            owner_row = db.execute('SELECT owner FROM itineraries WHERE id=?', (plan['id'],)).fetchone()
        from app.itineraries.store import ItineraryStore
        from app.memory.store import MemoryStore
        restarted = ItineraryStore(MemoryStore(settings.memory_db_path))
        restarted.initialize()
        assert restarted.get(owner_row['owner'], plan['id'])['stops'][0]['feedback'] == record
        edited = client.put(endpoint, json=feedback(saved['revision'], draft_title="我的真实体验", draft_content="正文由我修改"))
        assert edited.status_code == 200
        assert edited.json()['stops'][0]['feedback']['draft']['content'] == '正文由我修改'
        # Other itinerary edits must preserve the feedback on completed stops.
        changed = client.patch(path, json={"expected_revision": edited.json()['revision'], "action": "update_plan", "title": "修改后的行程"})
        assert changed.status_code == 200
        assert changed.json()['stops'][0]['feedback']['draft']['title'] == '我的真实体验'
        assert client.delete('/api/v1/travel/memory').status_code == 200
        assert client.get(path).status_code == 404


@pytest.mark.parametrize('patch', [
    {"experience": "   "}, {"rating": 6}, {"rating": True}, {"rating": 3.5},
    {"actual_cost_yuan": -1}, {"actual_cost_yuan": "NaN"}, {"actual_cost_yuan": "1.001"},
    {"queue_minutes": -1}, {"queue_minutes": 1.5}, {"owner": "user:other"},
    {"shop_id": "123"}, {"draft_content": "   "}, {"experience": "x" * 1501}
])
def test_feedback_rejects_invalid_or_forged_fields(tmp_path, patch):
    app = create_app(Settings(_env_file=None, memory_db_path=tmp_path / 'visits.sqlite3'))
    with TestClient(app) as client:
        result = client.put(f'/api/v1/itineraries/{uuid4()}/stops/{uuid4()}/feedback', json=feedback(1, **patch))
        assert result.status_code == 422


def test_unknown_expenses_remain_unknown_and_custom_draft_is_private():
    from app.itineraries.feedback import VisitFeedback, make_draft
    spec = VisitFeedback.model_validate(feedback(1))
    draft = make_draft({"place": {"name": "公园", "cost_yuan": 80}}, spec)
    assert '花费' not in draft['content']
    assert '排队' not in draft['content']
    assert '再去' not in draft['content']
