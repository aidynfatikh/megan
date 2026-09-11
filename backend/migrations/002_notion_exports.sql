CREATE TABLE notion_exports (
    job_id uuid NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    revision integer NOT NULL CHECK (revision >= 1),
    data_source_id text NOT NULL,
    state text NOT NULL CHECK (state IN ('pending', 'done')),
    page_id text,
    url text,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (job_id, revision, data_source_id),
    CHECK (state <> 'done' OR (page_id IS NOT NULL AND url IS NOT NULL))
);
