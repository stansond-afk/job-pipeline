-- job-pipeline community registry — D1 schema
--
-- Deploy once with:
--   wrangler d1 execute job-pipeline-registry --file=schema.sql
--
-- Two tables:
--   community_submissions  — append-only audit trail of every submission.
--                            One row per (slug, contributor). Re-submissions
--                            from the same contributor are silently deduped.
--   community_consensus    — materialized view of aggregated submissions.
--                            One row per (ats, slug). Updated on each
--                            new submission. This is what /api/community/slugs
--                            reads from.


CREATE TABLE IF NOT EXISTS community_submissions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    ats                 TEXT NOT NULL,
    slug                TEXT NOT NULL,
    company_hint        TEXT,                   -- name the submitter associated with the slug
    job_count           INTEGER DEFAULT 0,      -- jobs observed when verified
    contributor_hash    TEXT NOT NULL,          -- sha256(email), opaque
    submitted_at        TEXT NOT NULL,          -- ISO-8601 UTC

    UNIQUE (ats, slug, contributor_hash)
);

CREATE INDEX IF NOT EXISTS idx_submissions_contributor    ON community_submissions(contributor_hash);
CREATE INDEX IF NOT EXISTS idx_submissions_ats_slug       ON community_submissions(ats, slug);
CREATE INDEX IF NOT EXISTS idx_submissions_submitted_at   ON community_submissions(submitted_at);


CREATE TABLE IF NOT EXISTS community_consensus (
    ats                 TEXT NOT NULL,
    slug                TEXT NOT NULL,
    company_canonical   TEXT,                   -- best-known company name (longest hint wins)
    submission_count    INTEGER NOT NULL DEFAULT 1,
    first_seen          TEXT NOT NULL,
    last_seen           TEXT NOT NULL,

    PRIMARY KEY (ats, slug)
);

CREATE INDEX IF NOT EXISTS idx_consensus_count       ON community_consensus(submission_count DESC);
CREATE INDEX IF NOT EXISTS idx_consensus_ats         ON community_consensus(ats);
