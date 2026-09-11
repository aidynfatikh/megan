"""Explicit report publishing. Local inference never calls this module."""

import asyncio
import json
import os
import re
from uuid import UUID

import httpx
from pydantic import Field, SecretStr

from backend.config import Settings
from backend.schemas import Job, Model

API = "https://api.notion.com/v1"
VERSION = "2026-03-11"


class NotionError(RuntimeError):
    pass


class NotionResult(Model):
    url: str
    page_id: str
    revision: int
    reused: bool


class NotionConnect(Model):
    token: SecretStr = Field(min_length=10, max_length=500)
    data_source_id: UUID | None = None
    parent_page_id: UUID | None = None


class NotionExportRequest(Model):
    revision: int = Field(ge=1)


def escape(text: str) -> str:
    # Transcript text must not create links, embeds or markup in the exported page.
    return re.sub(r"([\\`*_\[\]<>#|~])", r"\\\1", text).replace("\n", " ")


def timestamp(seconds):
    return "unknown" if seconds is None else f"{int(seconds) // 60}:{int(seconds) % 60:02d}"


def report_markdown(job: Job) -> str:
    report = job.report
    if report is None:
        raise NotionError("Wait until a report is ready.")
    lines = [
        f"# {escape(report.title)}",
        "",
        f"Meeting date: {job.meeting_date or 'Not provided'} · Language: {job.report_language} · Revision: {job.report_revision}",
        "",
        "Generated locally by Megan. Review the interpretation against its sources. Audio stays on the local machine.",
    ]
    if job.provenance.demo:
        lines += ["", f"Demo recording: {escape(job.provenance.demo)}"]

    def sources(evidence):
        seen = set()
        for src in evidence:
            key = (src.segment_id, src.quote)
            if key not in seen:
                lines.append(
                    f"> Source {src.segment_id} · {timestamp(src.start)}–{timestamp(src.end)}: {escape(src.quote)}"
                )
                seen.add(key)

    def claims(title, items):
        lines.extend(["", f"## {title}", ""])
        if not items:
            lines.append("None found in this recording.")
        for item in items:
            lines.extend([f"- {escape(item.text)}", f"Review: {item.review.state}"])
            sources(item.evidence)

    claims("Summary", report.summary)
    for topic in report.topics:
        claims(f"Topic: {escape(topic.title)}", topic.theses)
    claims("Decisions", report.decisions)
    lines.extend(["", "## Action items", ""])
    if not report.action_items:
        lines.append("No outstanding assignments found.")
    for action in report.action_items:
        lines.extend(
            [
                f"- [ ] {escape(action.task)}",
                f"Owner: {escape(action.assignee or 'Not stated')} · Due: {action.due.date or 'Unresolved / not stated'} · Priority: {action.priority}",
                f"Review: {action.review.state} · Date resolution: {action.due.resolution}",
            ]
        )
        if action.due.raw:
            lines.append(f"Spoken deadline: {escape(action.due.raw)}")
        for condition in action.conditions:
            lines.append(f"Condition: {escape(condition)}")
        if action.review.reasons:
            lines.append("Review reasons: " + ", ".join(map(escape, action.review.reasons)))
        sources([src for group in action.evidence.values() for src in group])
    claims("Open questions", report.open_questions)
    claims("Risks and blockers", report.risks)
    if job.warnings:
        lines.extend(["", "## Processing notes", ""])
        lines.extend(f"- {escape(w)}" for w in job.warnings)
    lines.extend(["", f"Megan meeting ID: {job.id}"])
    return "\n\n".join(lines)


def rich_text(value):
    return [{"type": "text", "text": {"content": str(value)}}]


class NotionExporter:
    def __init__(self, settings: Settings, repo):
        self.settings = settings.model_copy()
        self.repo = repo
        self.lock = asyncio.Lock()
        path = settings.data_dir / "notion-connection.json"
        if path.is_file():
            try:
                saved = NotionConnect.model_validate_json(path.read_text())
                self.settings.notion_api_token = saved.token
                self.settings.notion_data_source_id = str(saved.data_source_id or "")
            except (ValueError, OSError):
                pass

    async def connect(self, request: NotionConnect):
        try:
            async with self.lock, self.client(request.token.get_secret_value()) as client:
                self.check(await client.get("users/me"))
                source_id = str(request.data_source_id) if request.data_source_id else None
                if source_id:
                    source = self.check(await client.get(f"data_sources/{source_id}"))
                    required = {
                        "Name": "title",
                        "Megan ID": "rich_text",
                        "Revision": "number",
                        "Meeting date": "date",
                        "Language": "select",
                        "Tasks": "number",
                    }
                    if any(
                        source.get("properties", {}).get(k, {}).get("type") != v
                        for k, v in required.items()
                    ):
                        raise NotionError(
                            "This data source does not have the Megan report properties. Leave its ID blank to create a dedicated database."
                        )
                else:
                    database = self.check(
                        await client.post(
                            "databases",
                            json={
                                "parent": {
                                    "type": "page_id",
                                    "page_id": str(request.parent_page_id),
                                }
                                if request.parent_page_id
                                else {"type": "workspace", "workspace": True},
                                "title": rich_text("Megan Meetings"),
                                "initial_data_source": {
                                    "properties": {
                                        "Name": {"title": {}},
                                        "Megan ID": {"rich_text": {}},
                                        "Revision": {"number": {}},
                                        "Meeting date": {"date": {}},
                                        "Language": {"select": {}},
                                        "Tasks": {"number": {}},
                                    }
                                },
                            },
                        )
                    )
                    source_id = database["data_sources"][0]["id"]
                path = self.settings.data_dir / "notion-connection.json"
                path.parent.mkdir(parents=True, exist_ok=True)
                temporary = path.with_suffix(".tmp")
                with os.fdopen(
                    os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w"
                ) as stream:
                    os.fchmod(stream.fileno(), 0o600)
                    json.dump(
                        {"token": request.token.get_secret_value(), "data_source_id": source_id},
                        stream,
                    )
                temporary.replace(path)
                self.settings.notion_api_token = request.token
                self.settings.notion_data_source_id = source_id
                return self.status()
        except httpx.HTTPError:
            raise NotionError(
                "Could not reach Notion. Check your connection. If database creation timed out, check Notion for Megan Meetings before creating another."
            ) from None

    def status(self):
        return {
            "configured": bool(
                self.settings.notion_api_token.get_secret_value()
                and self.settings.notion_data_source_id
            ),
            "destination": "Megan Meetings" if self.settings.notion_data_source_id else None,
        }

    def client(self, token: str | None = None):
        return httpx.AsyncClient(
            base_url=API + "/",
            follow_redirects=False,
            timeout=60,
            headers={
                "Authorization": "Bearer "
                + (token or self.settings.notion_api_token.get_secret_value()),
                "Notion-Version": VERSION,
            },
        )

    @staticmethod
    def check(response):
        if response.is_success:
            return response.json()
        messages = {
            401: "Notion token was not accepted. Reconnect in settings.",
            403: "Notion connection needs permission to read and insert pages in the destination.",
            404: "Notion destination is unavailable. Share the database with the connection.",
            429: "Notion is rate limiting requests. Try again later.",
            529: "Notion is busy. Try again later.",
        }
        raise NotionError(
            messages.get(
                response.status_code,
                f"Notion could not complete this request (HTTP {response.status_code}).",
            )
        )

    async def export(self, job: Job) -> NotionResult:
        if not self.status()["configured"]:
            raise NotionError("Connect Notion before exporting.")
        if (
            job.status != "done"
            or not job.report
            or job.report_revision < 1
            or job.provenance.sample
        ):
            raise NotionError("Export a completed recording with a saved report.")
        async with self.lock:
            # Connection settings can change while an export waits for the lock.
            try:
                source_id = str(UUID(self.settings.notion_data_source_id))
            except ValueError:
                raise NotionError(
                    "Notion data source ID is invalid. Reconnect in settings."
                ) from None
            key = (job.id, job.report_revision, source_id)
            receipt = await self.repo.notion_export(*key)
            if receipt and receipt["state"] == "done":
                return NotionResult(
                    url=receipt["url"],
                    page_id=receipt["page_id"],
                    revision=job.report_revision,
                    reused=True,
                )
            try:
                async with self.client() as client:
                    query = self.check(
                        await client.post(
                            f"data_sources/{source_id}/query",
                            json={
                                "filter": {
                                    "and": [
                                        {
                                            "property": "Megan ID",
                                            "rich_text": {"equals": str(job.id)},
                                        },
                                        {
                                            "property": "Revision",
                                            "number": {"equals": job.report_revision},
                                        },
                                    ]
                                },
                                "page_size": 2,
                            },
                        )
                    )
                    matches = query.get("results", [])
                    if matches:
                        page = matches[0]
                        reused = True
                    else:
                        if receipt:
                            raise NotionError(
                                "The previous export result is uncertain. Check Notion and retry later; Megan will not create a duplicate while that request may still finish."
                            )
                        payload = {
                            "parent": {"type": "data_source_id", "data_source_id": source_id},
                            "properties": {
                                "Name": {"title": rich_text(job.report.title)},
                                "Megan ID": {"rich_text": rich_text(job.id)},
                                "Revision": {"number": job.report_revision},
                                "Meeting date": {
                                    "date": {"start": str(job.meeting_date)}
                                    if job.meeting_date
                                    else None
                                },
                                "Language": {"select": {"name": job.report_language}},
                                "Tasks": {"number": len(job.report.action_items)},
                            },
                            "markdown": report_markdown(job),
                        }
                        if len(json.dumps(payload, ensure_ascii=False).encode()) > 450_000:
                            raise NotionError(
                                "This report exceeds Notion's page request limit. Download its JSON export instead."
                            )
                        # Commit before the external write. A crash/timeout leaves a pending
                        # receipt that can be reconciled by querying Notion, never blind retried.
                        await self.repo.begin_notion_export(*key)
                        response = await client.post("pages", json=payload)
                        if (400 <= response.status_code < 500) or response.status_code == 529:
                            await self.repo.cancel_notion_export(*key)
                        page = self.check(response)
                        reused = False
                    await self.repo.finish_notion_export(*key, page["id"], page["url"])
                    return NotionResult(
                        url=page["url"],
                        page_id=page["id"],
                        revision=job.report_revision,
                        reused=reused,
                    )
            except httpx.HTTPError:
                raise NotionError(
                    "Could not reach Notion. Check the connection and retry; any pending export will be checked before another page is created."
                ) from None
