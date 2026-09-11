-- Speaker lists written before this migration could name a voice that holds no transcript text:
-- a sub-second diarizer false alarm inside a silent gap intersects no ASR segment, so a
-- single-speaker recording listed two participants. Such a name can be neither filtered nor
-- checked against the audio. Drop those voices and close the gap in the anonymous numbering.
-- Names the user edited are kept verbatim; segments, text and IDs are never touched.
WITH stored AS (
    SELECT id, document FROM jobs
    WHERE jsonb_typeof(document->'speakers') = 'array'
      AND jsonb_array_length(document->'speakers') > 0
),
heard AS (
    SELECT stored.id, segment.value->>'speaker_id' AS speaker_id, min(segment.ordinality) AS first_seen
    FROM stored
    CROSS JOIN LATERAL jsonb_array_elements(stored.document->'segments')
        WITH ORDINALITY AS segment(value, ordinality)
    WHERE segment.value->>'speaker_id' IS NOT NULL
    GROUP BY stored.id, segment.value->>'speaker_id'
),
kept AS (
    SELECT stored.id, speaker.value AS speaker,
           row_number() OVER (PARTITION BY stored.id ORDER BY heard.first_seen) AS position
    FROM stored
    CROSS JOIN LATERAL jsonb_array_elements(stored.document->'speakers') AS speaker(value)
    JOIN heard ON heard.id = stored.id AND heard.speaker_id = speaker.value->>'id'
),
rebuilt AS (
    SELECT id, jsonb_agg(
        CASE WHEN speaker->>'name_source' = 'anonymous'
             THEN jsonb_set(speaker, '{name}', to_jsonb('Speaker ' || position))
             ELSE speaker END
        ORDER BY position
    ) AS speakers
    FROM kept GROUP BY id
)
UPDATE jobs
SET document = jsonb_set(jobs.document, '{speakers}', coalesce(rebuilt.speakers, '[]'::jsonb))
FROM stored LEFT JOIN rebuilt ON rebuilt.id = stored.id
WHERE jobs.id = stored.id
  AND stored.document->'speakers' IS DISTINCT FROM coalesce(rebuilt.speakers, '[]'::jsonb);
