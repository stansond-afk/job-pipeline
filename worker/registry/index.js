/**
 * job-pipeline community registry Worker
 * ────────────────────────────────────────────────────────────────────────
 *
 * SHARED community infrastructure. Deployed ONCE by the maintainer (not per
 * fork). All forks point at the same deployed URL via the
 * JOB_PIPELINE_REGISTRY_URL env var.
 *
 * Endpoints:
 *   GET  /api/community/health              health check
 *   GET  /api/community/slugs               pull consensus registry
 *     ?min_submissions=2  (default 2 — single-submitter rows held back)
 *     ?ats=greenhouse     (optional filter)
 *   POST /api/community/submit-slugs        contribute verified slugs
 *     Body: { contributor_email_hash, submissions: [...] }
 *
 * Data model — see schema.sql. Two tables:
 *   community_submissions  append-only, one row per (slug, contributor)
 *   community_consensus    materialized view, updated on each submit
 *
 * Trust model:
 *   - Anonymous submissions (no Access JWT). Rate-limited per IP by
 *     Cloudflare's default protections; per-contributor abuse cap below.
 *   - contributor_email_hash is sha256(email) — opaque identifier so we
 *     can dedupe + track abuse without storing PII.
 *   - Consensus pull defaults to min_submissions >= 2 so a single
 *     bad-faith submission can't pollute the canonical list.
 *   - Max 1000 submissions per contributor_hash per day (abuse cap).
 *
 * Deploy:
 *   cd worker/registry
 *   npx wrangler d1 create job-pipeline-registry
 *   # paste returned UUID into wrangler.template.jsonc → D1_DATABASE_ID
 *   npx wrangler d1 execute job-pipeline-registry --file=schema.sql
 *   npx wrangler deploy
 */

const VALID_ATS = new Set([
  "greenhouse", "lever", "icims", "workday", "bamboohr",
  "smartrecruiters", "ashby", "workable", "jobvite", "neogov",
  "greenjobs", "manual",
]);

const SLUG_RE = /^[a-z0-9][a-z0-9_-]{0,80}$/;
const HASH_RE = /^[a-f0-9]{64}$/;  // sha256 hex
const MAX_SUBMISSIONS_PER_REQUEST = 200;
const MAX_SUBMISSIONS_PER_CONTRIBUTOR_PER_DAY = 1000;


export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const path = url.pathname;
    const method = request.method;

    try {
      if (path === "/api/community/health" && method === "GET") {
        return jsonResponse({ ok: true, server: "registry" });
      }

      if (path === "/api/community/slugs" && method === "GET") {
        return await getRegistry(url, env);
      }

      if (path === "/api/community/submit-slugs" && method === "POST") {
        return await submitSlugs(request, env);
      }

      return jsonResponse({ ok: false, message: `No route for ${method} ${path}` }, 404);
    } catch (err) {
      console.error("registry worker error:", err);
      return jsonResponse({
        ok: false,
        message: `Server error: ${err.name}: ${err.message}`,
      }, 500);
    }
  },
};


// ─────────────────────────────────────────────────────────────────────────
// GET /api/community/slugs — read the consensus registry
// ─────────────────────────────────────────────────────────────────────────

async function getRegistry(url, env) {
  const minSubmissions = Math.max(1, parseInt(url.searchParams.get("min_submissions") || "2", 10));
  const atsFilter = (url.searchParams.get("ats") || "").trim().toLowerCase();

  let sql = `
    SELECT ats, slug, company_canonical, submission_count, first_seen, last_seen
    FROM community_consensus
    WHERE submission_count >= ?
  `;
  const params = [minSubmissions];

  if (atsFilter) {
    sql += " AND ats = ?";
    params.push(atsFilter);
  }
  sql += " ORDER BY ats, slug";

  const result = await env.DB.prepare(sql).bind(...params).all();

  return jsonResponse({
    ok: true,
    min_submissions: minSubmissions,
    ats_filter: atsFilter || null,
    count: result.results.length,
    registry: result.results,
  });
}


// ─────────────────────────────────────────────────────────────────────────
// POST /api/community/submit-slugs — record contributions + update consensus
// ─────────────────────────────────────────────────────────────────────────

async function submitSlugs(request, env) {
  let body;
  try {
    body = await request.json();
  } catch {
    return jsonResponse({ ok: false, message: "Invalid JSON body" }, 400);
  }

  const contribHash = (body.contributor_email_hash || "").trim().toLowerCase();
  if (!HASH_RE.test(contribHash)) {
    return jsonResponse({
      ok: false,
      message: "contributor_email_hash must be a SHA256 hex string (64 chars)",
    }, 400);
  }

  const submissions = body.submissions;
  if (!Array.isArray(submissions) || submissions.length === 0) {
    return jsonResponse({ ok: false, message: "submissions must be a non-empty array" }, 400);
  }
  if (submissions.length > MAX_SUBMISSIONS_PER_REQUEST) {
    return jsonResponse({
      ok: false,
      message: `Too many submissions in one request. Max ${MAX_SUBMISSIONS_PER_REQUEST}.`,
    }, 400);
  }

  // Abuse cap: how many submissions has this contributor made today?
  const cutoff = new Date(Date.now() - 24 * 3600 * 1000).toISOString();
  const recent = await env.DB.prepare(
    "SELECT COUNT(*) AS c FROM community_submissions WHERE contributor_hash = ? AND submitted_at >= ?"
  ).bind(contribHash, cutoff).first();
  if ((recent?.c || 0) >= MAX_SUBMISSIONS_PER_CONTRIBUTOR_PER_DAY) {
    return jsonResponse({
      ok: false,
      message: "Daily submission cap exceeded. Try again tomorrow.",
    }, 429);
  }

  const now = new Date().toISOString();
  let accepted = 0;
  let duplicates = 0;
  let rejected = 0;
  const rejectReasons = [];

  for (const s of submissions) {
    const ats = (s.ats || "").trim().toLowerCase();
    const slug = (s.slug || "").trim().toLowerCase();
    const companyHint = (s.company_hint || "").trim().slice(0, 200);
    const jobCount = Math.max(0, Math.min(99999, parseInt(s.job_count_observed || "0", 10) || 0));

    if (!VALID_ATS.has(ats)) {
      rejected++; rejectReasons.push(`bad ats: ${ats}`);
      continue;
    }
    if (!SLUG_RE.test(slug)) {
      rejected++; rejectReasons.push(`bad slug: ${slug}`);
      continue;
    }

    // Insert the raw submission. UNIQUE(ats, slug, contributor_hash) means
    // re-submissions from the same contributor are silently deduped.
    const insertResult = await env.DB.prepare(
      `INSERT OR IGNORE INTO community_submissions
         (ats, slug, company_hint, job_count, contributor_hash, submitted_at)
       VALUES (?, ?, ?, ?, ?, ?)`
    ).bind(ats, slug, companyHint, jobCount, contribHash, now).run();

    if (insertResult.meta.changes > 0) {
      // New submission — update consensus.
      await env.DB.prepare(`
        INSERT INTO community_consensus
          (ats, slug, company_canonical, submission_count, first_seen, last_seen)
        VALUES (?, ?, ?, 1, ?, ?)
        ON CONFLICT(ats, slug) DO UPDATE SET
          submission_count = submission_count + 1,
          last_seen = excluded.last_seen,
          -- Prefer the longer / more specific company_hint over older ones,
          -- but only overwrite if the new one is meaningfully different.
          company_canonical = CASE
            WHEN LENGTH(excluded.company_canonical) > LENGTH(company_canonical)
                 THEN excluded.company_canonical
            ELSE company_canonical
          END
      `).bind(ats, slug, companyHint, now, now).run();
      accepted++;
    } else {
      duplicates++;
    }
  }

  return jsonResponse({
    ok: true,
    accepted,
    duplicates,
    rejected,
    reject_reasons: rejected > 0 ? rejectReasons.slice(0, 5) : undefined,
  });
}


// ─────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────

function jsonResponse(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "content-type": "application/json",
      // Permissive CORS so any fork can call us from local Flask too.
      "access-control-allow-origin": "*",
      "access-control-allow-methods": "GET, POST, OPTIONS",
      "access-control-allow-headers": "content-type",
    },
  });
}
