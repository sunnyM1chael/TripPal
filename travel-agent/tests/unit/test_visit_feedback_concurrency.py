import asyncio
from uuid import UUID

import pytest

from app.core.exceptions import NotFoundError
from app.itineraries.feedback import VisitFeedback, save_feedback
from app.itineraries.models import EditItinerary, RevisionConflict
from app.tools.travel import TravelTools
from tests.unit.test_itineraries import service, payload


async def test_concurrent_feedback_cannot_silently_overwrite_and_tool_is_owner_scoped(service):
    plan = await service.create('guest:owner', payload())
    stop_id = plan['stops'][0]['id']
    plan = await service.edit('guest:owner', plan['id'], EditItinerary(
        expected_revision=plan['revision'], action='complete_stop', stop_id=stop_id))
    async def write(text):
        return await save_feedback(service.store, 'guest:owner', plan['id'], UUID(stop_id),
            VisitFeedback(expected_revision=plan['revision'], rating=4, experience=text))
    results = await asyncio.gather(write('面很好吃'), write('服务不错'), return_exceptions=True)
    assert sum(isinstance(result, RevisionConflict) for result in results) == 1
    assert sum(isinstance(result, dict) for result in results) == 1
    tools = TravelTools(None, owner='guest:owner', itineraries=service, itinerary_id=plan['id'])
    visits = await tools.execute('get_visit_feedback', {})
    assert len(visits['visits']) == 1
    assert visits['visits'][0]['feedback']['experience'] in {'面很好吃', '服务不错'}
    other = TravelTools(None, owner='guest:other', itineraries=service, itinerary_id=plan['id'])
    with pytest.raises(NotFoundError):
        await other.execute('get_visit_feedback', {})
    # The model can read privately; it cannot invoke a feedback or publishing write.
    names = {item['function']['name'] for item in tools.schemas()}
    assert 'get_visit_feedback' in names
    assert 'save_visit_feedback' not in names
    assert 'publish_blog' not in names
