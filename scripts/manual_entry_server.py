"""Local Flask server for the dashboard's Add Job + Tracker features.

Single-file. Endpoints:
  GET  /                              → static dashboard
  GET  /api/health                    → server-up check (Add Job panel toggle)
  POST /api/add-job                   → manual posting entry (session 9)
  GET  /api/posting/<id>              → posting fields for Apply modal pre-fill
  GET  /api/tailored-files?posting_id=<id>  → ranked .docx candidates from ~/Downloads/
  POST /api/apply                     → log application + JD snapshot + paths (session 10)
  POST /api/application/<id>/status   → inline status update from tracker view
  POST /api/posting/<id>/interest     → inline interest-level update (D27, session 15)

The dashboard JS pings /api/health on load. If it succeeds, server-driven
features (Add Job panel, Apply button) become active. If it fails (server
not running), the dashboard works as a static read-only page.

Usage:
    python scripts/manual_entry_server.py
    # → server at http://127.0.0.1:5050

Or via the launcher (recommended for daily use):
    Double-click launch.command at the repo root.

Why port 5050: avoids collisions with common dev servers (5000=Flask default,
3000=node, 8000=python http.server). Easy to remember.
"""

from __future__ import annotations

import logging
import sys
import webbrowser
from pathlib import Path

# Make sibling package importable when this is called from a script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from flask import Flask, jsonify, request, send_from_directory
except ImportError:
    print("Flask is not installed. Install with:")
    print("    pip install flask")
    sys.exit(1)

from jobpipeline.db import connect
from jobpipeline.manual_entry import add_manual_posting
from jobpipeline.models import Application, APPLICATION_STATUSES, INTEREST_LEVELS, utcnow_iso
from jobpipeline.persistence import (
    get_application_by_id,
    get_application_by_posting_id,
    get_posting_by_id,
    update_application_status,
    update_posting_interest,
    upsert_application,
)
from jobpipeline.tailored_files import find_candidates_for_posting

# Import the dashboard generator so we can refresh dashboard/index.html after
# state changes. This lets the user's page-reload pick up the new state
# without them having to re-run generate_dashboard.py manually.
try:
    from scripts.generate_dashboard import main as regenerate_dashboard
except ImportError:
    # Fallback for environments where the scripts package isn't importable
    # — we'll just skip regen rather than crash.
    regenerate_dashboard = None

REPO_ROOT = Path(__file__).resolve().parent.parent
DASHBOARD_DIR = REPO_ROOT / "dashboard"
DASHBOARD_INDEX = DASHBOARD_DIR / "index.html"
PORT = 5050

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("manual_entry_server")

app = Flask(__name__, static_folder=None)


def _safe_regen_dashboard(reason: str) -> None:
    """Regenerate dashboard/index.html. Wrapped so failures never break responses."""
    if regenerate_dashboard is None:
        return
    try:
        regenerate_dashboard()
    except Exception as e:
        log.warning("dashboard regen after %s failed (state still saved): %s", reason, e)


# ---------------------------------------------------------------------------
# Static + health
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    if not DASHBOARD_INDEX.exists():
        return (
            "<h1>Dashboard not found</h1>"
            f"<p>Expected at: <code>{DASHBOARD_INDEX}</code></p>"
            "<p>Run <code>python scripts/generate_dashboard.py</code> first.</p>",
            404,
        )
    return send_from_directory(DASHBOARD_DIR, "index.html")


@app.route("/api/health")
def health():
    """Dashboard JS uses this to detect whether the server is running."""
    return jsonify({"ok": True, "service": "manual_entry_server"})


# ---------------------------------------------------------------------------
# Manual posting entry (session 9)
# ---------------------------------------------------------------------------

@app.route("/api/add-job", methods=["POST"])
def add_job():
    """Accept JSON with optional url, jd_text, role, company, location.

    Returns the EntryResult as JSON. Always 200 — the result's `ok` field
    indicates success or failure (rather than HTTP status codes for
    application-level errors).
    """
    payload = request.get_json(silent=True) or {}
    url = (payload.get("url") or "").strip() or None
    jd_text = (payload.get("jd_text") or "").strip() or None
    role = (payload.get("role") or "").strip() or None
    company = (payload.get("company") or "").strip() or None
    location = (payload.get("location") or "").strip() or None

    if not url and not jd_text and not (role and company):
        return jsonify({
            "ok": False,
            "message": "Provide a URL, pasted JD text, or at least role + company.",
        })

    try:
        result = add_manual_posting(
            url=url,
            jd_text=jd_text,
            role=role,
            company=company,
            location=location,
        )
        log.info(
            "add-job: %s, posting_id=%s, fit=%s, role=%r company=%r",
            "ok" if result.ok else "fail",
            result.posting_id,
            result.fit_score,
            role or (result.extracted or {}).get("role"),
            company or (result.extracted or {}).get("company"),
        )
        if result.ok:
            _safe_regen_dashboard("add-job")
        return jsonify(result.to_dict())
    except Exception as e:
        log.exception("add-job crashed")
        return jsonify({"ok": False, "message": f"Server error: {type(e).__name__}: {e}"})


# ---------------------------------------------------------------------------
# Application tracker (session 10)
# ---------------------------------------------------------------------------

@app.route("/api/posting/<int:posting_id>", methods=["GET"])
def get_posting(posting_id: int):
    """Return posting fields needed to pre-fill the Apply modal.

    Also returns the existing application (if any) so the modal can show
    "you already applied on X" + load existing jd_snapshot for editing.
    """
    conn = connect()
    try:
        posting = get_posting_by_id(conn, posting_id)
        if posting is None:
            return jsonify({"ok": False, "message": f"Posting {posting_id} not found"})

        existing_app = get_application_by_posting_id(conn, posting_id)
        existing_app_dict = dict(existing_app) if existing_app is not None else None

        return jsonify({
            "ok": True,
            "posting": {
                "id":       posting["id"],
                "company":  posting["company"],
                "role":     posting["role"],
                "url":      posting["url"],
                "location": posting["location"],
                "jd_text":  posting["jd_text"],
            },
            "application": existing_app_dict,
        })
    except Exception as e:
        log.exception("get-posting crashed")
        return jsonify({"ok": False, "message": f"Server error: {type(e).__name__}: {e}"})
    finally:
        conn.close()


@app.route("/api/tailored-files", methods=["GET"])
def get_tailored_files():
    """Scan the tailored-files watch dir (default ~/Downloads/) and return
    ranked candidates for the modal's Resume + Cover Letter dropdowns.

    Query param: posting_id=<int>

    Response shape:
      {
        "ok": true,
        "watch_dir": "/Users/.../Downloads",
        "resume": [<MatchResult dict>, ...],   # ranked, top 10
        "cover":  [<MatchResult dict>, ...]
      }

    Empty arrays if no posting found, no tailored files exist, or watch
    dir doesn't exist. The dashboard treats empty arrays as "no auto-discovery
    today; user can paste a path manually."
    """
    posting_id_raw = request.args.get("posting_id")
    try:
        posting_id = int(posting_id_raw)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "message": "posting_id query param (int) required"})

    conn = connect()
    try:
        posting = get_posting_by_id(conn, posting_id)
        if posting is None:
            return jsonify({"ok": False, "message": f"Posting {posting_id} not found"})

        from jobpipeline.tailored_files import get_watch_dir

        candidates = find_candidates_for_posting({
            "company": posting["company"],
            "role":    posting["role"],
        })

        resume_list = [c.to_dict() for c in candidates.get("resume", [])]
        cover_list  = [c.to_dict() for c in candidates.get("cover", [])]

        log.info(
            "tailored-files: posting_id=%d, resumes=%d, covers=%d",
            posting_id, len(resume_list), len(cover_list),
        )

        return jsonify({
            "ok": True,
            "watch_dir": str(get_watch_dir()),
            "resume": resume_list,
            "cover":  cover_list,
        })
    except Exception as e:
        log.exception("tailored-files crashed")
        return jsonify({"ok": False, "message": f"Server error: {type(e).__name__}: {e}"})
    finally:
        conn.close()


@app.route("/api/apply", methods=["POST"])
def apply_to_posting():
    """Log an application for a posting.

    Required in payload:
      posting_id  — int
      jd_snapshot — str (the edited JD text from the modal)

    Optional:
      status            — defaults to 'submitted'
      notes             — freeform notes
      tailored_notes    — paste-back from tailoring chat (Phase 2 use)
      resume_path       — full path to tailored resume .docx
      cover_letter_path — full path to tailored cover letter .docx
      submitted_at_now  — bool, if True set submitted_at to now (default True
                          when status='submitted', False otherwise)

    Idempotent: applying twice on the same posting updates the existing row.
    """
    payload = request.get_json(silent=True) or {}

    posting_id = payload.get("posting_id")
    if not isinstance(posting_id, int):
        return jsonify({"ok": False, "message": "posting_id (int) is required"})

    jd_snapshot = (payload.get("jd_snapshot") or "").strip() or None
    notes = (payload.get("notes") or "").strip() or None
    tailored_notes = (payload.get("tailored_notes") or "").strip() or None
    resume_path = (payload.get("resume_path") or "").strip() or None
    cover_letter_path = (payload.get("cover_letter_path") or "").strip() or None
    status = (payload.get("status") or "submitted").strip()

    if status not in APPLICATION_STATUSES:
        return jsonify({
            "ok": False,
            "message": f"Invalid status {status!r}. Must be one of: {', '.join(APPLICATION_STATUSES)}",
        })

    # If status is 'submitted' (the default), record submitted_at unless
    # the caller explicitly opted out. For other statuses, only record it
    # if the caller asked for it.
    submitted_at_now = payload.get("submitted_at_now")
    if submitted_at_now is None:
        submitted_at_now = (status == "submitted")
    submitted_at = utcnow_iso() if submitted_at_now else None

    conn = connect()
    try:
        # Verify posting exists
        posting = get_posting_by_id(conn, posting_id)
        if posting is None:
            return jsonify({"ok": False, "message": f"Posting {posting_id} not found"})

        # If there's an existing application, preserve fields the caller
        # didn't send. This makes partial updates work cleanly: e.g., the
        # inline status dropdown only sends status — we don't want it to
        # blow away resume_path/notes/etc.
        existing = get_application_by_posting_id(conn, posting_id)
        if existing is not None:
            if submitted_at is None:
                submitted_at = existing["submitted_at"]
            if jd_snapshot is None:
                jd_snapshot = existing["jd_snapshot"]
            if notes is None:
                notes = existing["notes"]
            if tailored_notes is None:
                tailored_notes = existing["tailored_notes"]
            if resume_path is None:
                resume_path = existing["resume_path"]
            if cover_letter_path is None:
                cover_letter_path = existing["cover_letter_path"]

        app_obj = Application(
            posting_id=posting_id,
            status=status,
            submitted_at=submitted_at,
            notes=notes,
            jd_snapshot=jd_snapshot,
            tailored_notes=tailored_notes,
            resume_path=resume_path,
            cover_letter_path=cover_letter_path,
        )
        now = utcnow_iso()
        app_id, is_new = upsert_application(conn, app_obj, now)
        conn.commit()

        log.info(
            "apply: posting_id=%d, app_id=%d, is_new=%s, status=%s, "
            "jd_snapshot_len=%d, resume=%s, cover=%s",
            posting_id, app_id, is_new, status,
            len(jd_snapshot) if jd_snapshot else 0,
            "yes" if resume_path else "no",
            "yes" if cover_letter_path else "no",
        )

        _safe_regen_dashboard("apply")

        return jsonify({
            "ok": True,
            "message": ("Application logged" if is_new else "Application updated"),
            "application_id": app_id,
            "is_new": is_new,
            "status": status,
        })
    except Exception as e:
        log.exception("apply crashed")
        return jsonify({"ok": False, "message": f"Server error: {type(e).__name__}: {e}"})
    finally:
        conn.close()


@app.route("/api/application/<int:application_id>/status", methods=["POST"])
def update_status(application_id: int):
    """Inline status update from the tracker view.

    Payload: {"status": "<new status>"}
    """
    payload = request.get_json(silent=True) or {}
    new_status = (payload.get("status") or "").strip()

    if new_status not in APPLICATION_STATUSES:
        return jsonify({
            "ok": False,
            "message": f"Invalid status {new_status!r}. Must be one of: {', '.join(APPLICATION_STATUSES)}",
        })

    conn = connect()
    try:
        # Verify the application exists first, for a cleaner error
        existing = get_application_by_id(conn, application_id)
        if existing is None:
            return jsonify({"ok": False, "message": f"Application {application_id} not found"})

        update_application_status(conn, application_id, new_status)
        conn.commit()

        log.info(
            "status update: app_id=%d, %s → %s",
            application_id, existing["status"], new_status,
        )

        _safe_regen_dashboard("status-update")

        return jsonify({
            "ok": True,
            "message": "Status updated",
            "application_id": application_id,
            "status": new_status,
        })
    except Exception as e:
        log.exception("status-update crashed")
        return jsonify({"ok": False, "message": f"Server error: {type(e).__name__}: {e}"})
    finally:
        conn.close()


@app.route("/api/posting/<int:posting_id>/interest", methods=["POST"])
def update_interest(posting_id: int):
    """Update interest_level for a posting (D27).

    Payload: {"interest_level": "<level>"}
    Valid levels: not_reviewed | not_interested | interested | very_interested

    Triggers dashboard regen so the new sort order takes effect on next page load.
    """
    payload = request.get_json(silent=True) or {}
    new_level = (payload.get("interest_level") or "").strip()

    if new_level not in INTEREST_LEVELS:
        return jsonify({
            "ok": False,
            "message": f"Invalid interest_level {new_level!r}. Must be one of: {', '.join(INTEREST_LEVELS)}",
        })

    conn = connect()
    try:
        # Verify the posting exists first, for a cleaner error
        existing = get_posting_by_id(conn, posting_id)
        if existing is None:
            return jsonify({"ok": False, "message": f"Posting {posting_id} not found"})

        update_posting_interest(conn, posting_id, new_level)
        conn.commit()

        log.info(
            "interest update: posting_id=%d, %s → %s",
            posting_id, existing["interest_level"], new_level,
        )

        _safe_regen_dashboard("interest-update")

        return jsonify({
            "ok": True,
            "message": "Interest updated",
            "posting_id": posting_id,
            "interest_level": new_level,
        })
    except Exception as e:
        log.exception("interest-update crashed")
        return jsonify({"ok": False, "message": f"Server error: {type(e).__name__}: {e}"})
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Boot
# ---------------------------------------------------------------------------

def open_browser_after_delay():
    """Open the default browser to the dashboard once the server is up.

    Runs in a daemon thread so it doesn't block startup. We delay a moment
    so Flask has time to actually start listening.
    """
    import threading
    import time

    def _open():
        time.sleep(1.0)
        webbrowser.open(f"http://127.0.0.1:{PORT}/")

    threading.Thread(target=_open, daemon=True).start()


def main():
    log.info("Starting manual entry server on http://127.0.0.1:%d", PORT)
    log.info("Dashboard:       http://127.0.0.1:%d/", PORT)
    log.info("Health check:    http://127.0.0.1:%d/api/health", PORT)
    log.info("Press Ctrl-C to stop.")
    open_browser_after_delay()
    # use_reloader=False because reloader respawns the process and re-runs the
    # browser-open thread, which is annoying.
    app.run(host="127.0.0.1", port=PORT, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
