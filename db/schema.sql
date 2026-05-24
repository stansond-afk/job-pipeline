-- job pipeline — SQLite schema.
--
-- Design notes:
--   - "postings" is the raw firehose: every job we've ever pulled from a source.
--   - "applications" tracks the user's pipeline state for postings she decides to pursue.
--   - "source_log" is an audit trail of scraper runs — useful for debugging when a
--     source goes silent or starts throwing errors.
--   - "url_telemetry" (D32) captures domain/ATS/slug for every URL we see, regardless
--     of source. Read by analyze_telemetry.py to surface scraper-coverage gaps.
--
-- Conventions:
--   - Timestamps stored as ISO-8601 UTC strings (TEXT). SQLite has no native
--     datetime; strings sort correctly and are easy to read.
--   - Dedup key is (source, source_job_id). Same job seen twice = UPDATE last_seen,
--     don't INSERT a duplicate.
--   - fit_score left NULL for now; scoring module will populate later.

CREATE TABLE IF NOT EXISTS postings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Origin
    source          TEXT NOT NULL,          -- 'greenhouse', 'lever', 'usajobs', 'neogov', ...
    source_job_id   TEXT NOT NULL,          -- the ATS's own ID for this posting
    company         TEXT NOT NULL,          -- canonical company name (matches targets.csv)

    -- Posting content
    role            TEXT NOT NULL,          -- role title
    location        TEXT,                   -- as posted — e.g. "Washington, DC" or "Remote - US"
    department      TEXT,                   -- ATS-provided dept/team if any
    url             TEXT NOT NULL,          -- link to the posting
    jd_text         TEXT,                   -- full job description (may be long)

    -- Metadata
    posted_at       TEXT,                   -- ISO-8601 UTC, if the ATS provides it
    first_seen      TEXT NOT NULL,          -- ISO-8601 UTC, when WE first saw this posting
    last_seen       TEXT NOT NULL,          -- ISO-8601 UTC, most recent scrape that still saw it
    is_active       INTEGER NOT NULL DEFAULT 1,  -- 0 = no longer appearing in source feed

    -- Scoring (populated by scoring module later)
    fit_score       REAL,                   -- 0.0 - 1.0, NULL until scored
    score_notes     TEXT,                   -- why it scored that way

    -- Interest level (D27 — per-posting triage signal, separate from fit_score)
    interest_level  TEXT NOT NULL DEFAULT 'not_reviewed',
        -- valid values: 'not_reviewed' (default), 'not_interested',
        --               'interested', 'very_interested'
    interest_updated_at TEXT,           -- ISO-8601 UTC, set on every interest change.
                                        -- Feeds daily-streak computation (D33). NULL = never changed.

    UNIQUE (source, source_job_id)
);

CREATE INDEX IF NOT EXISTS idx_postings_company        ON postings(company);
CREATE INDEX IF NOT EXISTS idx_postings_first_seen     ON postings(first_seen);
CREATE INDEX IF NOT EXISTS idx_postings_is_active      ON postings(is_active);
CREATE INDEX IF NOT EXISTS idx_postings_fit_score      ON postings(fit_score);
CREATE INDEX IF NOT EXISTS idx_postings_interest_level ON postings(interest_level);


CREATE TABLE IF NOT EXISTS applications (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    posting_id      INTEGER NOT NULL,

    -- Pipeline status
    status          TEXT NOT NULL DEFAULT 'new',
        -- valid values: 'new', 'reviewing', 'tailored', 'submitted',
        --               'interviewing', 'offered', 'rejected', 'withdrawn', 'closed'

    -- Tracking
    submitted_at    TEXT,                   -- ISO-8601 UTC, when she actually applied
    resume_path     TEXT,                   -- path to tailored resume .docx, if any
    cover_letter_path TEXT,                 -- path to cover letter .docx, if any
    notes           TEXT,                   -- freeform notes from her

    -- JD capture (D18 — snapshot at Apply time, edited via modal)
    jd_snapshot     TEXT,                   -- full JD text as the user edited/confirmed it
    tailored_notes  TEXT,                   -- paste-back from the Claude tailoring chat

    -- Housekeeping
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,

    FOREIGN KEY (posting_id) REFERENCES postings(id)
);

CREATE INDEX IF NOT EXISTS idx_applications_posting_id ON applications(posting_id);
CREATE INDEX IF NOT EXISTS idx_applications_status     ON applications(status);


CREATE TABLE IF NOT EXISTS source_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source          TEXT NOT NULL,          -- 'greenhouse', 'lever', etc.
    company         TEXT,                   -- NULL when the run hits many companies
    run_at          TEXT NOT NULL,          -- ISO-8601 UTC, when scraper started
    status          TEXT NOT NULL,          -- 'success', 'error', 'skipped'
    postings_found  INTEGER NOT NULL DEFAULT 0,
    postings_new    INTEGER NOT NULL DEFAULT 0,
    postings_updated INTEGER NOT NULL DEFAULT 0,
    error_message   TEXT,
    duration_ms     INTEGER
);

CREATE INDEX IF NOT EXISTS idx_source_log_run_at ON source_log(run_at);
CREATE INDEX IF NOT EXISTS idx_source_log_source ON source_log(source);


-- ---------------------------------------------------------------------------
-- url_telemetry (D32) — passive coverage-gap signal
-- ---------------------------------------------------------------------------
--
-- One row per (url, source) pair we've ever observed. Written by upsert_posting
-- (which routes through record_url_telemetry()) so every scraper contributes
-- without per-scraper changes. Also written by manual entries via the Worker.
--
-- ats_guess values:
--   'greenhouse', 'lever', 'workday', 'icims', 'bamboohr', 'avature', 'paycom',
--   'smartrecruiters', 'dayforce', 'ashby', 'workable', 'jobvite', 'ultipro',
--   'adp', 'usajobs', 'neogov', 'amazon', 'unknown'
--
-- ats_slug is the platform-tenant identifier when extractable:
--   - greenhouse: company slug from path (e.g. 'wri', 'thebrattlegroup')
--   - lever:      company slug from path (e.g. 'palantir')
--   - workday:    tenant subdomain (e.g. 'aaaie' for CSAA, 'aes' for AES Corp)
--   - icims:      tenant subdomain stripped of 'careers-' prefix (e.g. 'wwfus')
--   - avature:    tenant subdomain (e.g. 'deloitteus')
--   - bamboohr:   tenant subdomain (e.g. 'interagency')
--   - others:     see jobpipeline/url_telemetry.py for full extraction logic
--
-- Idempotency: UNIQUE(url, source) + INSERT OR IGNORE. Required because JobSpy
-- returns the same posting under multiple keyword search queries, and a posting
-- seen in two scraper runs should not create two telemetry rows.

CREATE TABLE IF NOT EXISTS url_telemetry (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    url             TEXT NOT NULL,
    domain          TEXT NOT NULL,          -- normalized hostname, e.g. 'boards.greenhouse.io'
    ats_guess       TEXT NOT NULL,          -- canonical ATS id; 'unknown' for unrecognized
    ats_slug        TEXT,                   -- tenant/company slug when extractable
    company_name    TEXT,                   -- as known to the posting (may be NULL)
    source          TEXT NOT NULL,          -- 'greenhouse', 'jobspy:indeed', 'manual', ...
    added_at        TEXT NOT NULL,          -- ISO-8601 UTC, first time we saw this URL from this source
    posting_id      INTEGER,                -- FK to postings.id; NULL if telemetry written before posting committed

    FOREIGN KEY (posting_id) REFERENCES postings(id),
    UNIQUE (url, source)
);

CREATE INDEX IF NOT EXISTS idx_url_telemetry_domain    ON url_telemetry(domain);
CREATE INDEX IF NOT EXISTS idx_url_telemetry_ats_guess ON url_telemetry(ats_guess);
CREATE INDEX IF NOT EXISTS idx_url_telemetry_ats_slug  ON url_telemetry(ats_slug);
CREATE INDEX IF NOT EXISTS idx_url_telemetry_source    ON url_telemetry(source);
CREATE INDEX IF NOT EXISTS idx_url_telemetry_added_at  ON url_telemetry(added_at);


-- ---------------------------------------------------------------------------
-- achievements (D33 — dopamine mechanics)
-- ---------------------------------------------------------------------------
--
-- 8 hand-defined achievements unlocked as the user hits milestones. Rows are
-- pre-seeded by migrate_004_achievements_streak.py; the dashboard reads
-- this table to render the achievement shelf with earned/locked states.
--
-- earned_at NULL = locked. seen_at NULL = unlock toast not yet dismissed.
--
-- Unlock conditions live in jobpipeline/achievements.py (check_and_unlock).

CREATE TABLE IF NOT EXISTS achievements (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT NOT NULL,
    icon        TEXT NOT NULL,
    earned_at   TEXT,
    seen_at     TEXT
);
