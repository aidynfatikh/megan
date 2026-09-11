CREATE TABLE IF NOT EXISTS jobs (
    id uuid PRIMARY KEY,
    status text NOT NULL CHECK (status IN ('queued', 'running', 'done', 'failed', 'interrupted')),
    revision integer NOT NULL DEFAULT 0,
    document jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- Admission is also enforced in PostgreSQL, not just an in-memory semaphore.
CREATE UNIQUE INDEX IF NOT EXISTS jobs_one_active
    ON jobs ((true)) WHERE status IN ('queued', 'running');
CREATE INDEX IF NOT EXISTS jobs_recent ON jobs (created_at DESC);

CREATE TABLE IF NOT EXISTS report_revisions (
    job_id uuid NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    revision integer NOT NULL,
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (job_id, revision)
);
