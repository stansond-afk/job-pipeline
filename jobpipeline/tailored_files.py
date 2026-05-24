"""Auto-discovery of tailored resume/cover-letter files for the dashboard's Apply modal.

Scans a watched directory (default ~/Downloads/) for files matching the
tailored-output naming convention:

    <AbbrevCompany>_<RoleTitle>_<USER_MARKER>_<DDMM>_v<N>_<resume|cover|notes>.<docx|md>

The USER_MARKER substring is configurable per user (config/profile.yaml
→ tailored_files.marker). Default: `_tailored_`. The original Solongo
build used `_solongo_`; a user named Alex would set `_alex_`.

For each posting, ranks the discovered files by how well they match the
posting's company + role title. The Apply modal populates Resume and
Cover Letter dropdowns with the right candidates pre-selected.

The module has no Flask dependencies and is fully testable in isolation.
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from . import config as _config


# ---------------------------------------------------------------------------
# Config — sources resolve in priority order: env var → profile.yaml → default
# ---------------------------------------------------------------------------

def get_watch_dir() -> Path:
    """Return the directory the dashboard scans for tailored files.

    Priority:
      1. $TAILORED_FILES_DIR env var if set
      2. config/profile.yaml → tailored_files.watch_dir
      3. ~/Downloads/ (default — where browser downloads land on macOS)
    """
    env = os.environ.get("TAILORED_FILES_DIR")
    if env:
        return Path(env).expanduser()
    return Path(_config.tailored_watch_dir()).expanduser()


def get_marker() -> str:
    """Return the substring that marks a file as a tailored output.

    Read from config/profile.yaml (default `_tailored_`). Must be unique
    enough that a substring match against arbitrary filenames in Downloads
    is safe — i.e. don't pick a single character or a common word.
    """
    return _config.tailored_marker()


# How far back to look. Older files are excluded — they're presumed stale
# from a previous job search and would only add noise to the dropdowns.
DEFAULT_MAX_AGE_DAYS = 30


# Doc types we surface to the dashboard. Notes are tracked but not exposed
# in the apply modal; users don't reference notes when applying.
SURFACED_DOC_TYPES = ("resume", "cover")


# ---------------------------------------------------------------------------
# Filename parsing
# ---------------------------------------------------------------------------

# Suffix patterns we recognize. Order matters when multiple match.
# Pattern: _<DDMM>_v<N>_<doc_type>.<ext>
SUFFIX_RE = re.compile(
    r"_(?P<ddmm>\d{4})_v(?P<version>\d+)_(?P<doc_type>resume|cover|notes)\."
    r"(?P<ext>docx|md)$"
)


@dataclass
class TailoredFile:
    """A parsed tailored file. Fields populated from the filename + filesystem."""
    path: Path
    basename: str
    company_slug: str        # e.g. "Brattle"
    title_slug: str          # e.g. "ESG-Analyst"
    ddmm: str                # e.g. "2904"
    version: int             # e.g. 1
    doc_type: str            # 'resume' | 'cover' | 'notes'
    mtime: float             # POSIX timestamp

    @property
    def title_tokens(self) -> list[str]:
        """Lowercased word tokens from the title slug."""
        return [t.lower() for t in self.title_slug.split("-") if t]

    @property
    def company_lower(self) -> str:
        return self.company_slug.lower()


def parse_tailored_filename(path: Path) -> Optional[TailoredFile]:
    """Parse a path into a TailoredFile if it matches our naming convention.

    Returns None if the filename doesn't match — caller can skip it.

    Example matches (with default marker `_tailored_`):
      Brattle_ESG-Analyst_tailored_2904_v1_resume.docx
      WRI_Sustainability-Consultant_tailored_2904_v2_cover.docx

    Example non-matches:
      resume.docx                            (no marker)
      Your_Name_Resume_X_Y.docx              (no marker)
      random_tailored_thing.docx             (marker present but suffix wrong)
    """
    marker = get_marker()
    name = path.name
    if marker not in name:
        return None

    # Split on the marker. Prefix = "<company>_<title>", suffix = "<DDMM>_v<N>_<type>.<ext>"
    prefix, _, rest = name.partition(marker)
    suffix_match = SUFFIX_RE.match("_" + rest)
    if not suffix_match:
        return None

    # Prefix must split cleanly into company + title. The split is on the
    # first underscore — company is one token (no underscores), title may
    # contain hyphens.
    if "_" not in prefix:
        return None
    company_slug, title_slug = prefix.split("_", 1)
    if not company_slug or not title_slug:
        return None

    try:
        mtime = path.stat().st_mtime
    except OSError:
        return None

    return TailoredFile(
        path=path,
        basename=name,
        company_slug=company_slug,
        title_slug=title_slug,
        ddmm=suffix_match.group("ddmm"),
        version=int(suffix_match.group("version")),
        doc_type=suffix_match.group("doc_type"),
        mtime=mtime,
    )


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def list_tailored_files(
    watch_dir: Optional[Path] = None,
    max_age_days: int = DEFAULT_MAX_AGE_DAYS,
) -> list[TailoredFile]:
    """Scan watch_dir and return all parseable tailored files within the age window.

    Sorted newest-first by mtime.
    """
    if watch_dir is None:
        watch_dir = get_watch_dir()
    if not watch_dir.is_dir():
        return []

    cutoff = time.time() - (max_age_days * 86400)
    out: list[TailoredFile] = []
    try:
        entries = list(watch_dir.iterdir())
    except OSError:
        return []

    for entry in entries:
        if not entry.is_file():
            continue
        parsed = parse_tailored_filename(entry)
        if parsed is None:
            continue
        if parsed.mtime < cutoff:
            continue
        out.append(parsed)

    out.sort(key=lambda f: f.mtime, reverse=True)
    return out


# ---------------------------------------------------------------------------
# Matching against a posting
# ---------------------------------------------------------------------------

# Generic words that should not contribute to company or title matching
# because they appear in many companies/titles and would inflate scores.
STOPWORDS = frozenset({
    "the", "and", "of", "a", "an", "for", "to", "with",
    "inc", "llc", "ltd", "corp", "corporation", "company", "co",
    "group", "holdings", "international", "global", "us", "usa", "n/a",
})


def _tokenize(s: str) -> list[str]:
    """Lowercase + split on any non-alphanumeric. Drop empties and stopwords."""
    if not s:
        return []
    tokens = re.split(r"[^A-Za-z0-9]+", s.lower())
    return [t for t in tokens if t and t not in STOPWORDS]


def _is_acronym_of(short: str, long_tokens: Iterable[str]) -> bool:
    """Check if `short` (e.g. 'WRI') is the acronym of `long_tokens` (e.g. ['world','resources','institute']).

    Acronym = first letter of each significant token, in order. Case-insensitive.
    """
    short = short.lower()
    initials = "".join(t[0] for t in long_tokens if t)
    return short == initials


@dataclass
class MatchResult:
    """A tailored file scored against a posting. Higher score = better match."""
    file: TailoredFile
    score: float
    reasons: list[str]   # human-readable match signals, for debug/UI tooltips

    def to_dict(self) -> dict:
        return {
            "path":         str(self.file.path),
            "basename":     self.file.basename,
            "doc_type":     self.file.doc_type,
            "version":      self.file.version,
            "ddmm":         self.file.ddmm,
            "mtime":        self.file.mtime,
            "company_slug": self.file.company_slug,
            "title_slug":   self.file.title_slug,
            "score":        round(self.score, 3),
            "reasons":      self.reasons,
        }


def _score_company(file_company: str, posting_company_tokens: list[str]) -> tuple[float, Optional[str]]:
    """Return (score in [0,1], reason or None) for the company match."""
    file_lower = file_company.lower()
    if not posting_company_tokens:
        return 0.0, None

    # Exact token match: filename's company slug appears as a token in the posting
    if file_lower in posting_company_tokens:
        return 1.0, f"company token '{file_company}' matches posting"

    # Acronym match: filename = initials of posting tokens (any prefix subset
    # of tokens, length >= 2 — protects against single-letter false positives)
    if 2 <= len(file_lower) <= 6 and _is_acronym_of(file_lower, posting_company_tokens):
        return 0.95, f"company '{file_company}' is acronym of posting tokens"

    # Substring match: filename's company slug appears as substring of any
    # posting token (catches "Brattle" → "TheBrattleGroup" if the posting
    # company has been concatenated)
    for token in posting_company_tokens:
        if file_lower in token or token in file_lower:
            return 0.7, f"company '{file_company}' substring-overlaps '{token}'"

    return 0.0, None


def _score_title(file_title_tokens: list[str], posting_role_tokens: list[str]) -> tuple[float, Optional[str]]:
    """Return (score in [0,1], reason or None) for the role-title match.

    Score = (matched tokens) / (max(file_tokens, posting_tokens)).
    Using max in the denominator penalizes both over- and under-matching.
    """
    if not file_title_tokens or not posting_role_tokens:
        return 0.0, None
    file_set = set(file_title_tokens)
    post_set = set(posting_role_tokens)
    matched = file_set & post_set
    if not matched:
        return 0.0, None
    score = len(matched) / max(len(file_set), len(post_set))
    return score, f"title overlap: {len(matched)} of {max(len(file_set), len(post_set))} tokens"


def _score_recency(mtime: float, max_age_days: int = DEFAULT_MAX_AGE_DAYS) -> float:
    """Return a [0,1] recency score. Today = 1.0; max_age_days ago = 0.0; linear."""
    age_seconds = time.time() - mtime
    age_days = age_seconds / 86400
    if age_days <= 0:
        return 1.0
    if age_days >= max_age_days:
        return 0.0
    return 1.0 - (age_days / max_age_days)


# Score weights — chosen so that strong company + title match dominates,
# but recency breaks ties between equally-matching candidates. Sum doesn't
# need to be 1.0; relative magnitudes are what matters.
W_COMPANY = 0.5
W_TITLE   = 0.4
W_RECENCY = 0.1


def score_file_against_posting(file: TailoredFile, posting: dict) -> MatchResult:
    """Score a single tailored file against a posting dict.

    posting expects keys: 'company' (str), 'role' (str). Other keys ignored.
    """
    company_tokens = _tokenize(posting.get("company", "") or "")
    role_tokens = _tokenize(posting.get("role", "") or "")

    company_score, company_reason = _score_company(file.company_slug, company_tokens)
    title_score, title_reason = _score_title(file.title_tokens, role_tokens)
    recency_score = _score_recency(file.mtime)

    total = (
        W_COMPANY * company_score +
        W_TITLE   * title_score +
        W_RECENCY * recency_score
    )

    reasons = []
    if company_reason:
        reasons.append(company_reason)
    if title_reason:
        reasons.append(title_reason)
    return MatchResult(file=file, score=total, reasons=reasons)


def find_candidates_for_posting(
    posting: dict,
    *,
    watch_dir: Optional[Path] = None,
    max_age_days: int = DEFAULT_MAX_AGE_DAYS,
    min_score: float = 0.0,
    limit_per_doc_type: int = 10,
) -> dict[str, list[MatchResult]]:
    """Return ranked candidates per surfaced doc type for the given posting.

    Returns:
      {'resume': [MatchResult, ...], 'cover': [MatchResult, ...]}

    Each list sorted by score desc, then mtime desc. Capped at limit_per_doc_type.

    posting expects keys: 'company', 'role'. Falsy/missing → empty results.
    """
    if not posting.get("company") and not posting.get("role"):
        return {dt: [] for dt in SURFACED_DOC_TYPES}

    files = list_tailored_files(watch_dir=watch_dir, max_age_days=max_age_days)
    out: dict[str, list[MatchResult]] = {dt: [] for dt in SURFACED_DOC_TYPES}

    for f in files:
        if f.doc_type not in SURFACED_DOC_TYPES:
            continue
        result = score_file_against_posting(f, posting)
        if result.score < min_score:
            continue
        out[f.doc_type].append(result)

    # Sort each list. Primary: score desc; tiebreak: mtime desc (newest first).
    for dt in out:
        out[dt].sort(key=lambda r: (-r.score, -r.file.mtime))
        out[dt] = out[dt][:limit_per_doc_type]

    return out
