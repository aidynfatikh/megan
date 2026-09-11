from unittest.mock import AsyncMock

import httpx
import pytest

from backend.config import Settings
from backend.example import example_job
from backend.notion import NotionError, NotionExporter, report_markdown

BASE = "https://api.notion.com/v1"
SOURCE = "11111111-2222-4333-8444-555555555555"


def exporter(repo):
    return NotionExporter(
        Settings(_env_file=None, notion_api_token="test-secret", notion_data_source_id=SOURCE), repo
    )


def meeting():
    job = example_job()
    job.provenance.sample = False
    return job


async def test_real_export_payload_preserves_report_and_is_cached(respx_mock):
    repo = AsyncMock()
    repo.notion_export.return_value = None
    respx_mock.post(f"{BASE}/data_sources/{SOURCE}/query").respond(200, json={"results": []})
    route = respx_mock.post(f"{BASE}/pages").respond(
        200, json={"id": "page-1", "url": "https://www.notion.so/page-1"}
    )
    job = meeting()
    result = await exporter(repo).export(job)
    assert result.url == "https://www.notion.so/page-1"
    import json

    payload = json.loads(route.calls[0].request.content)
    assert payload["parent"]["data_source_id"] == SOURCE
    assert payload["properties"]["Megan ID"]["rich_text"][0]["text"]["content"] == str(job.id)
    assert payload["markdown"] == report_markdown(job)
    assert "Decisions" in payload["markdown"] and "Risks" in payload["markdown"]
    assert "source" in payload["markdown"].lower()
    repo.begin_notion_export.assert_awaited_once()
    repo.finish_notion_export.assert_awaited_once()


async def test_cached_revision_never_posts_again(respx_mock):
    repo = AsyncMock()
    repo.notion_export.return_value = {
        "state": "done",
        "page_id": "page-1",
        "url": "https://www.notion.so/page-1",
    }
    result = await exporter(repo).export(meeting())
    assert result.reused
    assert not respx_mock.calls


async def test_ambiguous_timeout_is_reconciled_without_creating_duplicates(respx_mock):
    repo = AsyncMock()
    repo.notion_export.return_value = {"state": "pending"}
    query = respx_mock.post(f"{BASE}/data_sources/{SOURCE}/query").respond(
        200, json={"results": []}
    )
    with pytest.raises(NotionError, match="uncertain"):
        await exporter(repo).export(meeting())
    assert query.call_count == 1
    assert len(respx_mock.calls) == 1
    query.respond(200, json={"results": [{"id": "page-1", "url": "https://www.notion.so/page-1"}]})
    assert (await exporter(repo).export(meeting())).reused


@pytest.mark.parametrize("code", [401, 403, 429, 529])
async def test_rejected_export_can_retry_but_never_leaks_token(respx_mock, code):
    repo = AsyncMock()
    repo.notion_export.return_value = None
    respx_mock.post(f"{BASE}/data_sources/{SOURCE}/query").respond(200, json={"results": []})
    route = respx_mock.post(f"{BASE}/pages").respond(code, json={"message": "test-secret"})
    with pytest.raises(NotionError) as error:
        await exporter(repo).export(meeting())
    assert "test-secret" not in str(error.value)
    assert route.call_count == 1
    repo.cancel_notion_export.assert_awaited_once()


async def test_network_timeout_keeps_pending_receipt(respx_mock):
    repo = AsyncMock()
    repo.notion_export.return_value = None
    respx_mock.post(f"{BASE}/data_sources/{SOURCE}/query").respond(200, json={"results": []})
    respx_mock.post(f"{BASE}/pages").mock(side_effect=httpx.ReadTimeout("timeout"))
    with pytest.raises(NotionError):
        await exporter(repo).export(meeting())
    repo.cancel_notion_export.assert_not_called()


def test_markdown_keeps_edits_conditions_unknown_dates_and_review_state():
    job = meeting()
    item = job.report.action_items[0]
    item.conditions = ["Only if the microphone arrives"]
    item.due.date = None
    item.review.state = "needs_review"
    item.task = "Check <script> and [a link](https://example.com)"
    md = report_markdown(job)
    assert "Only if the microphone arrives" in md
    assert "needs_review" in md
    assert "[a link](https://example.com)" not in md


async def test_export_receipt_survives_repository_reopen(repository, new_job):
    await repository.create(new_job)
    await repository.begin_notion_export(new_job.id, 1, SOURCE)
    assert (await repository.notion_export(new_job.id, 1, SOURCE))["state"] == "pending"
    await repository.finish_notion_export(
        new_job.id, 1, SOURCE, "page-1", "https://www.notion.so/page-1"
    )
    from backend.db import Repository

    reopened = Repository(repository.url)
    await reopened.open()
    try:
        assert (await reopened.notion_export(new_job.id, 1, SOURCE))["state"] == "done"
        assert await reopened.notion_export(new_job.id, 2, SOURCE) is None
    finally:
        await reopened.close()


async def test_concurrent_clicks_create_one_page(respx_mock):
    import asyncio

    repo = AsyncMock()
    receipt = None

    async def finish(*args):
        nonlocal receipt
        receipt = {"state": "done", "page_id": args[-2], "url": args[-1]}

    repo.notion_export.side_effect = lambda *args: receipt
    repo.finish_notion_export.side_effect = finish
    respx_mock.post(f"{BASE}/data_sources/{SOURCE}/query").respond(200, json={"results": []})
    route = respx_mock.post(f"{BASE}/pages").respond(
        200, json={"id": "page-1", "url": "https://www.notion.so/page-1"}
    )
    client = exporter(repo)
    job = meeting()
    first, second = await asyncio.gather(client.export(job), client.export(job))
    assert first.url == second.url
    assert not first.reused and second.reused
    assert route.call_count == 1


async def test_connection_is_saved_privately_and_reloaded_without_returning_token(
    respx_mock, tmp_path
):
    from backend.notion import NotionConnect

    respx_mock.get(f"{BASE}/users/me").respond(200, json={"type": "bot"})
    route = respx_mock.get(f"{BASE}/data_sources/{SOURCE}").respond(
        200,
        json={
            "properties": {
                k: {"type": v}
                for k, v in {
                    "Name": "title",
                    "Megan ID": "rich_text",
                    "Revision": "number",
                    "Meeting date": "date",
                    "Language": "select",
                    "Tasks": "number",
                }.items()
            }
        },
    )
    settings = Settings(
        _env_file=None,
        data_dir=tmp_path,
        notion_api_token="old-secret",
        notion_data_source_id=SOURCE,
    )
    client = NotionExporter(settings, AsyncMock())
    status = await client.connect(NotionConnect(token="replacement-secret", data_source_id=SOURCE))
    assert status["configured"]
    assert "replacement-secret" not in str(status)
    assert route.calls[0].request.headers["authorization"] == "Bearer replacement-secret"
    assert (tmp_path / "notion-connection.json").stat().st_mode & 0o777 == 0o600
    restored = NotionExporter(settings, AsyncMock())
    assert restored.settings.notion_api_token.get_secret_value() == "replacement-secret"


async def test_connection_validation_never_reflects_secret(tmp_path):
    from backend.main import create_app

    app = create_app(Settings(_env_file=None, data_dir=tmp_path), repository=AsyncMock())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/integrations/notion",
            json={"token": "private-token", "data_source_id": "not-a-uuid"},
        )
    assert response.status_code == 422
    assert "private-token" not in response.text
