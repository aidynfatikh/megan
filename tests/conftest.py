import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from backend.schemas import Job, Provenance


@pytest.fixture
def new_job():
    now = datetime.now(UTC)
    return Job(
        id=uuid4(),
        filename="meeting.wav",
        created_at=now,
        updated_at=now,
        provenance=Provenance(asr_backend="test", asr_model="test", llm="test"),
    )


@pytest.fixture
async def repository():
    from backend.db import Repository

    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to a dedicated PostgreSQL test database")
    # Tests must not clear development or production data.
    if not url.rstrip("/").endswith("_test"):
        pytest.fail("TEST_DATABASE_URL must name a dedicated database ending in _test")
    repo = Repository(url)
    await repo.open()
    await repo.migrate()
    async with repo.pool.connection() as conn:
        await conn.execute("TRUNCATE jobs CASCADE")
    yield repo
    await repo.close()
