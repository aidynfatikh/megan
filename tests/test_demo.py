from backend.demo import seed_demo


async def test_demo_seed_has_audio_and_never_overwrites_edits(repository, new_job, tmp_path):
    from backend.schemas import Report

    source = tmp_path / "demo" / "russian"
    source.mkdir(parents=True)
    new_job.status = "done"
    new_job.report = Report(title="Recorded demo")
    new_job.report_revision = 1
    new_job.provenance.demo = "Prerecorded synthetic speech, processed locally."
    (source / "job.json").write_text(new_job.model_dump_json())
    (source / "recording.wav").write_bytes(b"curated demo audio")
    data = tmp_path / "data"
    await seed_demo(repository, tmp_path / "demo", data)
    job = await repository.get(new_job.id)
    assert job.report_revision == 1
    assert (data / "jobs" / str(job.id) / "normalized.wav").read_bytes() == b"curated demo audio"
    job.report.title = "My reviewed title"
    await repository.save(job, new_revision=True)
    await seed_demo(repository, tmp_path / "demo", data)
    restored = await repository.get(new_job.id)
    assert restored.report.title == "My reviewed title"
    assert restored.report_revision == 2
    async with repository.pool.connection() as conn:
        row = await (
            await conn.execute(
                "SELECT payload FROM report_revisions WHERE job_id=%s AND revision=1", (job.id,)
            )
        ).fetchone()
    assert row["payload"]["title"] == "Recorded demo"
