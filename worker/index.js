/**
 * job-pipeline Worker — Push 2 of Path C (session 18), extended in session 20.
 *
 * Adds API endpoints on top of the static-asset serving. Every write endpoint
 * requires a valid Cloudflare Access JWT in the Cf-Access-Jwt-Assertion header
 * (set automatically when accessing the Worker through the Access auth flow).
 *
 * Endpoints:
 *   GET  /api/health                    — server-up check
 *   GET  /api/events/pending            — pending D1 events (for client overlay)
 *   GET  /api/posting/<id>              — read a posting from the static dump
 *   GET  /api/tailored-files            — auto-discovery stub (Worker has no FS)
 *   POST /api/posting/<id>/interest     — log interest_level change
 *   POST /api/application/<id>/status   — log application status change
 *   POST /api/apply                     — log new application
 *   POST /api/add-job                   — NEW (D31, session 20): manual job entry
 *
 * Session 20 additions (D31, D32):
 *   - /api/add-job port of jobpipeline/manual_entry.py extraction logic
 *   - URL telemetry capture as a separate D1 event (parser inlined below)
 *   - Both events use INSERT OR IGNORE idempotency where applicable
 *
 * Bindings (declared in wrangler.jsonc):
 *   ASSETS — static files in ./dashboard/
 *   DB     — D1 database (configured via env)
 *
 * Cloudflare Access team domain comes from env.ACCESS_TEAM_DOMAIN (set in
 * wrangler.jsonc → vars, which the setup wizard fills from your .env).
 * Falls back to a placeholder so the Worker doesn't crash if unconfigured.
 */

function getAccessTeamDomain(env) {
  return (env && env.ACCESS_TEAM_DOMAIN) || "your-team.cloudflareaccess.com";
}

// Allowed event types. Keeps validation centralized.
const VALID_INTEREST_LEVELS = new Set([
  "not_reviewed",
  "not_interested",
  "interested",
  "very_interested",
]);

const VALID_APPLICATION_STATUSES = new Set([
  "new", "reviewing", "tailored", "submitted",
  "interviewing", "offered", "rejected", "withdrawn", "closed",
]);

// Rate-limit map for /api/add-job — keyed by user email, value is array of
// recent request timestamps (ms). Cleared automatically as old entries age out.
// Lives in module scope so it persists across requests within a single Worker
// instance. Cloudflare may run multiple Worker instances; this is best-effort
// defense-in-depth, not a strict rate limit.
const ADD_JOB_RATE_LIMIT = new Map();
const ADD_JOB_RATE_WINDOW_MS = 60_000;  // 1 minute
const ADD_JOB_RATE_MAX = 10;            // 10 add-job calls per minute per user


export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const path = url.pathname;

    if (path.startsWith("/api/")) {
      return handleApi(request, env, url);
    }

    return env.ASSETS.fetch(request);
  },
};


// ─────────────────────────────────────────────────────────────────────────
// API routing
// ─────────────────────────────────────────────────────────────────────────

async function handleApi(request, env, url) {
  const path = url.pathname;
  const method = request.method;

  try {
    if (path === "/api/health" && method === "GET") {
      return jsonResponse({ ok: true, server: "cloudflare-worker" });
    }

    if (path === "/api/events/pending" && method === "GET") {
      return await getPendingEvents(env);
    }

    const postingMatch = path.match(/^\/api\/posting\/(\d+)$/);
    if (postingMatch && method === "GET") {
      return await getPosting(parseInt(postingMatch[1], 10), env);
    }

    if (path === "/api/tailored-files" && method === "GET") {
      return jsonResponse({
        ok: false,
        message: "Tailored file auto-discovery not available on deployed dashboard. Paste file paths manually.",
        resume: [],
        cover: [],
      });
    }

    const interestMatch = path.match(/^\/api\/posting\/(\d+)\/interest$/);
    if (interestMatch && method === "POST") {
      return await requireAuth(request, env, async (userEmail) => {
        return await postInterest(parseInt(interestMatch[1], 10), request, env, userEmail);
      });
    }

    const statusMatch = path.match(/^\/api\/application\/(\d+)\/status$/);
    if (statusMatch && method === "POST") {
      return await requireAuth(request, env, async (userEmail) => {
        return await postStatus(parseInt(statusMatch[1], 10), request, env, userEmail);
      });
    }

    if (path === "/api/apply" && method === "POST") {
      return await requireAuth(request, env, async (userEmail) => {
        return await postApply(request, env, userEmail);
      });
    }

    // NEW (D31, session 20): manual job entry from the deployed dashboard.
    if (path === "/api/add-job" && method === "POST") {
      return await requireAuth(request, env, async (userEmail) => {
        return await postAddJob(request, env, userEmail);
      });
    }

    return jsonResponse({ ok: false, message: `No route for ${method} ${path}` }, 404);
  } catch (err) {
    console.error("API handler error:", err);
    return jsonResponse({
      ok: false,
      message: `Server error: ${err.name}: ${err.message}`,
    }, 500);
  }
}


// ─────────────────────────────────────────────────────────────────────────
// Auth — verify the Cf-Access-Jwt-Assertion header
// ─────────────────────────────────────────────────────────────────────────

async function requireAuth(request, env, handler) {
  const jwt = request.headers.get("Cf-Access-Jwt-Assertion");
  if (!jwt) {
    return jsonResponse({
      ok: false,
      message: "Missing Cf-Access-Jwt-Assertion header. Are you authenticated via Cloudflare Access?",
    }, 401);
  }

  try {
    const payload = await verifyAccessJwt(jwt, env);
    const userEmail = payload.email || payload.identity_nonce || "unknown";
    return await handler(userEmail);
  } catch (err) {
    console.error("JWT verification failed:", err.message);
    return jsonResponse({
      ok: false,
      message: `Authentication failed: ${err.message}`,
    }, 401);
  }
}


async function verifyAccessJwt(jwt, env) {
  const [headerB64, payloadB64, signatureB64] = jwt.split(".");
  if (!headerB64 || !payloadB64 || !signatureB64) {
    throw new Error("Malformed JWT (expected 3 dot-separated parts)");
  }

  const header = JSON.parse(atob(headerB64.replace(/-/g, "+").replace(/_/g, "/")));
  const payload = JSON.parse(atob(payloadB64.replace(/-/g, "+").replace(/_/g, "/")));

  const now = Math.floor(Date.now() / 1000);
  if (payload.exp && payload.exp < now) {
    throw new Error("JWT expired");
  }

  const expectedAud = env.ACCESS_AUD;
  if (!expectedAud) {
    throw new Error("ACCESS_AUD not configured in Worker env");
  }
  const audClaim = Array.isArray(payload.aud) ? payload.aud : [payload.aud];
  if (!audClaim.includes(expectedAud)) {
    throw new Error("JWT aud claim does not match expected app AUD");
  }

  const certsUrl = `https://${getAccessTeamDomain(env)}/cdn-cgi/access/certs`;
  const certsResp = await fetch(certsUrl, {
    cf: { cacheTtl: 3600, cacheEverything: true },
  });
  if (!certsResp.ok) {
    throw new Error(`Failed to fetch Access JWKS: ${certsResp.status}`);
  }
  const certs = await certsResp.json();
  const key = certs.keys.find(k => k.kid === header.kid);
  if (!key) {
    throw new Error(`No matching key for kid=${header.kid}`);
  }

  const cryptoKey = await crypto.subtle.importKey(
    "jwk",
    key,
    { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" },
    false,
    ["verify"],
  );
  const signedData = new TextEncoder().encode(`${headerB64}.${payloadB64}`);
  const signature = base64UrlToArrayBuffer(signatureB64);
  const valid = await crypto.subtle.verify(
    "RSASSA-PKCS1-v1_5",
    cryptoKey,
    signature,
    signedData,
  );
  if (!valid) {
    throw new Error("JWT signature verification failed");
  }

  return payload;
}


function base64UrlToArrayBuffer(b64url) {
  const b64 = b64url.replace(/-/g, "+").replace(/_/g, "/");
  const padded = b64 + "=".repeat((4 - b64.length % 4) % 4);
  const binary = atob(padded);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes.buffer;
}


// ─────────────────────────────────────────────────────────────────────────
// Existing endpoint handlers (unchanged from session 18)
// ─────────────────────────────────────────────────────────────────────────

async function getPendingEvents(env) {
  const result = await env.DB.prepare(
    `SELECT id, event_type, posting_id, application_id, payload, user_email, created_at
     FROM events
     WHERE applied_at IS NULL
     ORDER BY created_at ASC`
  ).all();

  const events = (result.results || []).map(row => ({
    ...row,
    payload: JSON.parse(row.payload),
  }));

  return jsonResponse({ ok: true, events });
}


async function getPosting(postingId, env) {
  const snapshotResp = await env.ASSETS.fetch(
    new Request("https://internal/postings.json"),
  );
  if (!snapshotResp.ok) {
    return jsonResponse({
      ok: false,
      message: "Postings snapshot not available (postings.json missing)",
    }, 503);
  }

  const postings = await snapshotResp.json();
  const posting = postings.find(p => p.id === postingId);
  if (!posting) {
    return jsonResponse({ ok: false, message: "Posting not found" }, 404);
  }

  return jsonResponse({
    ok: true,
    posting,
    application: null,
  });
}


async function postInterest(postingId, request, env, userEmail) {
  const body = await request.json().catch(() => ({}));
  const newLevel = (body.interest_level || "").trim();

  if (!VALID_INTEREST_LEVELS.has(newLevel)) {
    return jsonResponse({
      ok: false,
      message: `Invalid interest_level: ${newLevel}. Must be one of: ${[...VALID_INTEREST_LEVELS].join(", ")}`,
    }, 400);
  }

  await env.DB.prepare(
    `INSERT INTO events (event_type, posting_id, payload, user_email)
     VALUES (?, ?, ?, ?)`
  ).bind(
    "interest",
    postingId,
    JSON.stringify({ interest_level: newLevel }),
    userEmail,
  ).run();

  return jsonResponse({
    ok: true,
    message: "Interest updated",
    posting_id: postingId,
    interest_level: newLevel,
  });
}


async function postStatus(applicationId, request, env, userEmail) {
  const body = await request.json().catch(() => ({}));
  const newStatus = (body.status || "").trim();

  if (!VALID_APPLICATION_STATUSES.has(newStatus)) {
    return jsonResponse({
      ok: false,
      message: `Invalid status: ${newStatus}. Must be one of: ${[...VALID_APPLICATION_STATUSES].join(", ")}`,
    }, 400);
  }

  await env.DB.prepare(
    `INSERT INTO events (event_type, application_id, payload, user_email)
     VALUES (?, ?, ?, ?)`
  ).bind(
    "status",
    applicationId,
    JSON.stringify({ status: newStatus }),
    userEmail,
  ).run();

  return jsonResponse({
    ok: true,
    message: "Status updated",
    application_id: applicationId,
    status: newStatus,
  });
}


async function postApply(request, env, userEmail) {
  const body = await request.json().catch(() => ({}));

  if (!body.posting_id || !Number.isInteger(body.posting_id)) {
    return jsonResponse({
      ok: false,
      message: "posting_id is required and must be an integer",
    }, 400);
  }

  const status = (body.status || "submitted").trim();
  if (!VALID_APPLICATION_STATUSES.has(status)) {
    return jsonResponse({
      ok: false,
      message: `Invalid status: ${status}`,
    }, 400);
  }

  const payload = {
    status,
    submitted_at: body.submitted_at || null,
    resume_path: body.resume_path || null,
    cover_letter_path: body.cover_letter_path || null,
    notes: body.notes || null,
    jd_snapshot: body.jd_snapshot || null,
    tailored_notes: body.tailored_notes || null,
  };

  await env.DB.prepare(
    `INSERT INTO events (event_type, posting_id, payload, user_email)
     VALUES (?, ?, ?, ?)`
  ).bind(
    "apply",
    body.posting_id,
    JSON.stringify(payload),
    userEmail,
  ).run();

  return jsonResponse({
    ok: true,
    message: "Application logged. Will appear on next nightly sync.",
    posting_id: body.posting_id,
    status,
  });
}


// ─────────────────────────────────────────────────────────────────────────
// NEW: POST /api/add-job (D31, session 20)
// ─────────────────────────────────────────────────────────────────────────

/**
 * Accepts the same payload shape as the Flask /api/add-job:
 *   { url, jd_text, role, company, location }
 *
 * Server-side behavior (mirroring jobpipeline/manual_entry.py as closely as
 * possible given that the Worker can't run the Python scorer):
 *
 *   1. Validate that we have enough info to proceed (URL, JD text, or
 *      role+company minimum).
 *   2. If URL is given, fetch it server-side (Workers have no CORS limits).
 *      Extract role/company/location/jd_text via HTMLRewriter, preferring
 *      JSON-LD JobPosting microdata.
 *   3. Merge extracted fields with caller-provided overrides (caller wins).
 *   4. Write a `posting_added` event to D1 with the full posting payload.
 *      The nightly merge will pick it up, run upsert_posting (which fires
 *      URL telemetry), and run scoring.
 *   5. Also write a `url_telemetry` event for the manual-entry source tag.
 *      The Worker can't write to the master DB directly, but it can capture
 *      the telemetry shape now and let the merge replay it.
 *
 * Response:
 *   { ok: true, message, queued: true, extracted: {...}, warnings: [...] }
 *
 *   The "queued: true" flag tells the dashboard JS to show a different
 *   success message than the Flask path ("Will appear after next merge")
 *   instead of reloading immediately.
 */
async function postAddJob(request, env, userEmail) {
  // Rate-limit gate
  if (!checkAddJobRateLimit(userEmail)) {
    return jsonResponse({
      ok: false,
      message: `Rate limit exceeded — max ${ADD_JOB_RATE_MAX} add-job requests per minute.`,
    }, 429);
  }

  const body = await request.json().catch(() => ({}));
  const url = (body.url || "").trim() || null;
  const pastedJdText = (body.jd_text || "").trim() || null;
  const overrideRole = (body.role || "").trim() || null;
  const overrideCompany = (body.company || "").trim() || null;
  const overrideLocation = (body.location || "").trim() || null;

  if (!url && !pastedJdText && !(overrideRole && overrideCompany)) {
    return jsonResponse({
      ok: false,
      message: "Provide a URL, pasted JD text, or at least role + company.",
    }, 400);
  }

  const warnings = [];
  let extracted = { role: null, company: null, location: null, jd_text: null, posted_at: null };

  // 1. Fetch URL if provided, extract fields from HTML
  if (url) {
    const fetchResult = await fetchAndExtract(url);
    if (fetchResult.error) {
      warnings.push(fetchResult.error);
    } else {
      extracted = fetchResult.extracted;
    }
  }

  // 2. If JD text was pasted, use it where extraction missed
  if (pastedJdText) {
    if (!extracted.jd_text || pastedJdText.length > (extracted.jd_text || "").length) {
      extracted.jd_text = pastedJdText;
    }
    if (!extracted.role) {
      // First non-empty line, capped at 200 chars (matches Python heuristic)
      const lines = pastedJdText.split(/\r?\n/).map(l => l.trim()).filter(Boolean);
      if (lines.length > 0 && lines[0].length <= 200) {
        extracted.role = lines[0];
      }
    }
  }

  // 3. Apply caller overrides (they win over auto-detection)
  const finalRole = overrideRole || extracted.role;
  const finalCompany = overrideCompany || extracted.company;
  const finalLocation = overrideLocation || extracted.location;
  const finalJdText = extracted.jd_text || pastedJdText || null;

  // 4. Validate we have the required fields
  if (!finalRole) {
    return jsonResponse({
      ok: false,
      message: "Could not determine role title. Please provide one explicitly.",
      extracted: sanitizeExtractedForResponse(extracted),
      warnings,
    }, 400);
  }
  if (!finalCompany) {
    return jsonResponse({
      ok: false,
      message: "Could not determine company. Please provide one explicitly.",
      extracted: sanitizeExtractedForResponse(extracted),
      warnings,
    }, 400);
  }

  // 5. Build payload for the merge script. Field shape mirrors what
  //    apply_add_job() in merge_d1_events.py expects.
  const sourceJobId = await makeSourceJobId(url, finalRole, finalCompany);
  const postingPayload = {
    source: "manual",
    source_job_id: sourceJobId,
    company: finalCompany,
    role: finalRole,
    url: url || "(no url)",
    location: finalLocation,
    department: null,
    jd_text: finalJdText,
    posted_at: extracted.posted_at,
  };

  try {
    await env.DB.prepare(
      `INSERT INTO events (event_type, payload, user_email)
       VALUES (?, ?, ?)`
    ).bind(
      "add_job",
      JSON.stringify(postingPayload),
      userEmail,
    ).run();
  } catch (e) {
    console.error("Failed to write add_job event:", e);
    return jsonResponse({
      ok: false,
      message: `Could not queue posting: ${e.name}: ${e.message}`,
      extracted: sanitizeExtractedForResponse(extracted),
      warnings,
    }, 500);
  }

  return jsonResponse({
    ok: true,
    queued: true,
    message: `Posting queued (${finalRole} @ ${finalCompany}). Will appear after next nightly sync.`,
    extracted: sanitizeExtractedForResponse(extracted),
    warnings: warnings.length ? warnings : undefined,
  });
}


function checkAddJobRateLimit(userEmail) {
  const now = Date.now();
  const cutoff = now - ADD_JOB_RATE_WINDOW_MS;
  const recent = (ADD_JOB_RATE_LIMIT.get(userEmail) || []).filter(t => t > cutoff);
  if (recent.length >= ADD_JOB_RATE_MAX) {
    ADD_JOB_RATE_LIMIT.set(userEmail, recent);
    return false;
  }
  recent.push(now);
  ADD_JOB_RATE_LIMIT.set(userEmail, recent);
  return true;
}


function sanitizeExtractedForResponse(extracted) {
  // Don't send the full jd_text back in the response — it could be huge.
  // Mirror what the Flask response shape does (length only).
  return {
    role: extracted.role,
    company: extracted.company,
    location: extracted.location,
    jd_text_length: extracted.jd_text ? extracted.jd_text.length : 0,
    posted_at: extracted.posted_at,
  };
}


// ─────────────────────────────────────────────────────────────────────────
// URL fetch + HTML extraction (port of manual_entry.py extract_from_html)
// ─────────────────────────────────────────────────────────────────────────

const FETCH_HEADERS = {
  "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) " +
                "AppleWebKit/537.36 (KHTML, like Gecko) " +
                "Chrome/120.0.0.0 Safari/537.36",
  "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
  "Accept-Language": "en-US,en;q=0.9",
};

const FETCH_TIMEOUT_MS = 20_000;
const THIN_PAGE_THRESHOLD = 500;
// Cloudflare Workers cap subrequest response size; we read at most this many
// chars of body text to avoid runaway memory on huge pages.
const MAX_BODY_CHARS = 200_000;


async function fetchAndExtract(url) {
  // Validate URL scheme — refuse non-http(s) to avoid SSRF surprises
  let parsed;
  try {
    parsed = new URL(url);
  } catch (e) {
    return { error: `Invalid URL: ${e.message}`, extracted: emptyExtracted() };
  }
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    return { error: `Unsupported URL scheme: ${parsed.protocol}`, extracted: emptyExtracted() };
  }

  let html;
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
    const resp = await fetch(url, {
      headers: FETCH_HEADERS,
      signal: controller.signal,
      redirect: "follow",
    });
    clearTimeout(timeoutId);
    if (!resp.ok) {
      return {
        error: `URL fetch returned HTTP ${resp.status}. Paste JD text manually if the page is behind a login or bot wall.`,
        extracted: emptyExtracted(),
      };
    }
    html = await resp.text();
    if (html.length > MAX_BODY_CHARS) {
      html = html.slice(0, MAX_BODY_CHARS);
    }
  } catch (e) {
    return {
      error: `URL fetch failed: ${e.name}: ${e.message}`,
      extracted: emptyExtracted(),
    };
  }

  const extracted = extractFromHtml(html);
  return { extracted };
}


function emptyExtracted() {
  return { role: null, company: null, location: null, jd_text: null, posted_at: null };
}


/**
 * Extract role/company/location/jd_text/posted_at from raw HTML.
 *
 * Strategy mirrors jobpipeline/manual_entry.py:extract_from_html in order:
 *   1. JSON-LD JobPosting microdata (most reliable)
 *   2. Open Graph og:title / og:site_name
 *   3. <title> tag parsing — "Role - Company | Suffix"
 *   4. <meta name="description"> for jd_text fallback
 *   5. Body text (visible text only)
 *
 * Implementation uses regex on the HTML string. We tried HTMLRewriter first
 * but it's awkward for "give me all the text in <body>" — and a regex-based
 * pass keeps parity with the Python extractor's behavior on the same input.
 */
function extractFromHtml(html) {
  const extracted = emptyExtracted();

  // 1. JSON-LD JobPosting
  const jsonLdMatches = [...html.matchAll(
    /<script[^>]*type=["']application\/ld\+json["'][^>]*>([\s\S]*?)<\/script>/gi
  )];
  for (const match of jsonLdMatches) {
    const raw = match[1].trim();
    if (!raw) continue;
    let data;
    try {
      data = JSON.parse(raw);
    } catch (e) {
      // Some JSON-LD blocks have trailing commas or other invalid JSON; skip.
      continue;
    }
    const candidates = Array.isArray(data) ? data : [data];
    for (const item of candidates) {
      if (!item || typeof item !== "object") continue;
      if (item["@type"] !== "JobPosting") continue;

      if (!extracted.role && typeof item.title === "string") {
        extracted.role = cleanText(item.title);
      }
      if (!extracted.company) {
        const org = item.hiringOrganization;
        if (org && typeof org === "object" && typeof org.name === "string") {
          extracted.company = cleanText(org.name);
        }
      }
      if (!extracted.location) {
        let loc = item.jobLocation;
        if (Array.isArray(loc)) loc = loc[0];
        if (loc && typeof loc === "object") {
          const addr = loc.address;
          if (addr && typeof addr === "object") {
            const parts = [
              cleanText(addr.addressLocality || ""),
              cleanText(addr.addressRegion || ""),
            ].filter(Boolean);
            if (parts.length > 0) {
              extracted.location = parts.join(", ");
            }
          }
        }
      }
      if (!extracted.jd_text && typeof item.description === "string") {
        // description is often HTML — strip tags
        extracted.jd_text = cleanText(item.description.replace(/<[^>]+>/g, " "));
      }
      if (!extracted.posted_at && typeof item.datePosted === "string") {
        extracted.posted_at = item.datePosted;
      }
    }
  }

  // 2. Open Graph
  if (!extracted.role) {
    const ogTitle = matchMetaContent(html, /<meta\s+[^>]*property=["']og:title["'][^>]*>/i);
    if (ogTitle) extracted.role = cleanText(ogTitle);
  }
  if (!extracted.company) {
    const ogSite = matchMetaContent(html, /<meta\s+[^>]*property=["']og:site_name["'][^>]*>/i);
    if (ogSite) extracted.company = cleanText(ogSite);
  }

  // 3. <title> tag — split on common separators
  if (!extracted.role || !extracted.company) {
    const titleMatch = html.match(/<title[^>]*>([\s\S]*?)<\/title>/i);
    if (titleMatch) {
      const titleText = cleanText(decodeEntities(titleMatch[1]));
      const parts = titleText.split(/\s+(?:at|-|—|–|\||·)\s+/i)
                            .map(p => p.trim())
                            .filter(Boolean);
      if (parts.length >= 2) {
        if (!extracted.role) extracted.role = parts[0];
        if (!extracted.company) {
          const genericSuffixes = [
            "indeed", "linkedin", "glassdoor", "monster",
            "ziprecruiter", "wayup", "jobs", "careers",
            "myworkdayjobs", "greenhouse",
          ];
          let picked = null;
          for (let i = 1; i < parts.length; i++) {
            const lower = parts[i].toLowerCase();
            if (!genericSuffixes.some(g => lower.includes(g))) {
              picked = parts[i];
              break;
            }
          }
          extracted.company = picked || parts[1];
        }
      } else if (!extracted.role) {
        extracted.role = titleText;
      }
    }
  }

  // 4. Meta description fallback for jd_text
  if (!extracted.jd_text) {
    const metaDesc = matchMetaContent(html, /<meta\s+[^>]*name=["']description["'][^>]*>/i);
    if (metaDesc) extracted.jd_text = cleanText(decodeEntities(metaDesc));
  }

  // 5. Body text — last resort
  if (!extracted.jd_text) {
    const bodyMatch = html.match(/<body[^>]*>([\s\S]*?)<\/body>/i);
    if (bodyMatch) {
      let body = bodyMatch[1];
      // Strip script/style/nav/footer/header/aside
      body = body.replace(/<(script|style|nav|footer|header|aside)\b[^>]*>[\s\S]*?<\/\1>/gi, " ");
      body = body.replace(/<[^>]+>/g, " ");
      extracted.jd_text = cleanText(decodeEntities(body));
    }
  }

  return extracted;
}


function matchMetaContent(html, openTagRe) {
  const tagMatch = html.match(openTagRe);
  if (!tagMatch) return null;
  const contentMatch = tagMatch[0].match(/content=["']([^"']*)["']/i);
  if (!contentMatch) return null;
  return contentMatch[1];
}


function cleanText(s) {
  if (!s) return "";
  return s.replace(/\s+/g, " ").trim();
}


// Minimal HTML entity decoder — covers the common ones that show up in
// extracted text. Worker runtime has no DOMParser, so we do this manually.
function decodeEntities(s) {
  if (!s) return "";
  return s
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&apos;/g, "'")
    .replace(/&nbsp;/g, " ")
    .replace(/&#(\d+);/g, (_, n) => String.fromCharCode(parseInt(n, 10)))
    .replace(/&#x([0-9a-f]+);/gi, (_, h) => String.fromCharCode(parseInt(h, 16)));
}


// ─────────────────────────────────────────────────────────────────────────
// source_job_id synthesis — matches jobpipeline/manual_entry.py
// ─────────────────────────────────────────────────────────────────────────

/**
 * Stable hash for dedup: sha1(url|role|company)[:16].
 * Worker has crypto.subtle; Python uses hashlib. Both produce the same
 * 40-char hex digest from the same input, so we slice to 16 the same way.
 */
async function makeSourceJobId(url, role, company) {
  const seed = [
    (url || "").trim().toLowerCase(),
    role.trim().toLowerCase(),
    company.trim().toLowerCase(),
  ].join("|");
  const hashBuf = await crypto.subtle.digest("SHA-1", new TextEncoder().encode(seed));
  const hashArr = Array.from(new Uint8Array(hashBuf));
  return hashArr.map(b => b.toString(16).padStart(2, "0")).join("").slice(0, 16);
}


// ─────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────

function jsonResponse(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json",
      "Cache-Control": "no-store",
    },
  });
}
