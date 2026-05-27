// dashboard.jsx — One token-driven dashboard. Every theme is rendered by this
// same component; theme = {tokens, copy, mascot, decoration, dark}. Adding a
// new theme = adding an entry in themes.js. No code branches per theme.

const D_FONT_SERIF = "var(--serif)";
const D_FONT_SANS  = "var(--sans)";
const D_FONT_HAND  = "var(--hand)";

// ─── Theme provider ────────────────────────────────────────────────
// Sets CSS vars on a wrapper div (scoped, not global :root) so multiple
// themed dashboards can live side-by-side on the canvas.
function ThemeShell({ theme, children, style = {} }) {
  return (
    <div style={{
      ...theme.tokens,
      width: "100%", height: "100%",
      background: "var(--bg)",
      color: "var(--ink)",
      fontFamily: D_FONT_SANS,
      position: "relative",
      overflow: "hidden",
      ...style,
    }}>
      {children}
    </div>
  );
}

// String interpolation helper: "you're {pct}% there" + {pct: 53}
function fmt(s, vars) {
  if (!s) return "";
  return s.replace(/\{(\w+)\}/g, (_, k) => vars[k] ?? "");
}

// ─── Card primitive ────────────────────────────────────────────────
function Card({ children, style = {}, pad = 22 }) {
  return (
    <div style={{
      background: "var(--paper)",
      borderRadius: "var(--radius-card)",
      padding: pad,
      border: "1px solid var(--line)",
      boxShadow: "var(--shadow-card)",
      position: "relative",
      ...style,
    }}>{children}</div>
  );
}

function CardTitle({ children, kicker, action }) {
  return (
    <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 14, gap: 12 }}>
      <div style={{ minWidth: 0 }}>
        {kicker && (
          <div style={{
            fontSize: 10, fontWeight: 700, letterSpacing: "var(--kicker-ls)",
            color: "var(--sub)", textTransform: "var(--kicker-tt)", fontFamily: D_FONT_SANS,
          }}>{kicker}</div>
        )}
        <div style={{ fontFamily: D_FONT_SERIF, fontSize: 22, fontWeight: 500, color: "var(--ink)", marginTop: 2, lineHeight: 1.2 }}>{children}</div>
      </div>
      <div style={{ flexShrink: 0 }}>{action}</div>
    </div>
  );
}

// Hand-font / script accent — falls back to italic serif on themes whose
// --hand var is identical to --serif (Paper, Quiet, Mountain).
function Hand({ children, size = 22, color = "var(--a1-dk)", style = {} }) {
  return (
    <span style={{
      fontFamily: D_FONT_HAND,
      fontSize: size,
      color, lineHeight: 1.15,
      // If hand falls back to serif, italics gives the same "soft accent" feel.
      fontStyle: "italic",
      fontWeight: 500,
      ...style,
    }}>{children}</span>
  );
}

// ─── Greeting bar ──────────────────────────────────────────────────
function TopBar({ theme, prefs, onCelebrate }) {
  const Mascot = theme.mascot ? window.MASCOTS[theme.mascot] : null;
  const Deco = window.DECORATIONS[theme.decoration];
  const initials = (prefs.name || "?").trim().split(/\s+/).map(w => w[0]).join("").slice(0, 2).toUpperCase() || "J";

  // Greeting gradient is per-theme via blended a1/a2/sun; falls back if not present.
  const grad = theme.dark
    ? "linear-gradient(135deg, var(--paper) 0%, var(--row) 60%, var(--bg) 100%)"
    : "linear-gradient(135deg, color-mix(in oklch, var(--a1) 30%, var(--paper)) 0%, color-mix(in oklch, var(--a2) 25%, var(--paper)) 60%, color-mix(in oklch, var(--sun) 35%, var(--paper)) 100%)";

  return (
    <div style={{
      display: "grid", gridTemplateColumns: "1fr auto", alignItems: "center",
      padding: "22px 28px", borderRadius: "calc(var(--radius-card) + 4px)",
      background: grad,
      border: "1px solid var(--line)",
      position: "relative", overflow: "hidden",
    }}>
      {Deco && <Deco />}

      <div style={{ display: "flex", gap: 18, alignItems: "center", position: "relative", zIndex: 2 }}>
        <div style={{
          width: 78, height: 78, borderRadius: "50%", background: "var(--paper)",
          display: "grid", placeItems: "center", border: "2px solid var(--bg)",
          boxShadow: "0 6px 18px -8px rgba(0,0,0,0.18)",
        }}>
          {Mascot && prefs.mascotEnabled ? <Mascot size={62} /> : <MascotMonogram size={62} initials={initials} />}
        </div>
        <div>
          <Hand size={28} color="var(--a1-dk)" style={{ display: "block" }}>{theme.copy.greetingScript}</Hand>
          <div style={{
            fontFamily: D_FONT_SERIF, fontSize: 42, fontWeight: 500, color: "var(--ink)",
            lineHeight: 1.05, marginTop: 2, letterSpacing: "-0.4px",
          }}>
            {prefs.name}<span style={{ color: "var(--warm)" }}>{theme.copy.nameSuffix}</span>
          </div>
          <div style={{ marginTop: 6, color: "var(--sub)", fontSize: 14 }}>
            Wednesday, May 20 · {theme.copy.mascotSays} <em>"{theme.copy.mascotQuote}"</em>
          </div>
        </div>
      </div>

      <div style={{ display: "flex", gap: 10, alignItems: "center", position: "relative", zIndex: 2 }}>
        <div style={{
          display: "flex", alignItems: "center", gap: 8, background: "var(--paper)",
          padding: "8px 14px", borderRadius: "var(--radius-pill)", border: "1px solid var(--line)",
        }}>
          <span style={{ fontSize: 18 }}>{theme.copy.streakIcon}</span>
          <div>
            <div style={{ fontWeight: 800, fontSize: 18, lineHeight: 1, color: "var(--ink)" }}>7 days</div>
            <div style={{ fontSize: 10, color: "var(--sub)", marginTop: 2 }}>{theme.copy.streakSuffix}</div>
          </div>
        </div>
        <button onClick={onCelebrate} style={{
          background: "var(--ink)", color: "var(--bg)", border: "none",
          padding: "12px 18px", borderRadius: "var(--radius-pill)", fontFamily: D_FONT_SANS,
          fontWeight: 700, fontSize: 13, cursor: "pointer", boxShadow: "var(--shadow-cta)",
          letterSpacing: 0.2,
        }}>{theme.copy.celebrate}</button>
      </div>
    </div>
  );
}

// ─── Love note ─────────────────────────────────────────────────────
// The "someone loves you" pillar — a dismissible soft pill below the greeting.
// Cycles between supporter affirmations and a steady core message.
function LoveNote({ theme, prefs, onClose }) {
  if (!prefs.showPersonalNote || !prefs.supporter) return null;
  const message = prefs.supporter.trim().match(/^(someone|self|me)$/i)
    ? `Remember — you are loved. You are the best thing in someone's world.`
    : `${prefs.supporter} thinks you are the best thing in the world. ${theme.copy.mascotName ? theme.copy.mascotName + " agrees." : "We agree."}`;
  return (
    <div style={{
      marginTop: 12, padding: "10px 18px",
      background: "color-mix(in oklch, var(--warm) 18%, var(--paper))",
      border: "1px solid color-mix(in oklch, var(--warm) 40%, var(--line))",
      borderRadius: "var(--radius-pill)",
      display: "flex", alignItems: "center", gap: 12, justifyContent: "space-between",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <span style={{ fontSize: 14 }}>♥</span>
        <Hand size={20} color="var(--ink)">{message}</Hand>
      </div>
      <button onClick={onClose} style={{
        background: "transparent", border: "none", color: "var(--sub)",
        fontSize: 16, cursor: "pointer", opacity: 0.6, padding: 4,
      }}>×</button>
    </div>
  );
}

// ─── Weekly ring ───────────────────────────────────────────────────
function WeeklyRing({ theme, done = 8, goal = 15 }) {
  const pct = Math.min(1, done / goal);
  const R = 64, C = 2 * Math.PI * R;
  const ringText = fmt(theme.copy.ringCopy, { pct: Math.round(pct * 100), done, goal });
  const ringSub = fmt(theme.copy.ringSub, { remaining: Math.max(0, goal - done), done, goal });
  return (
    <Card pad={20}>
      <CardTitle kicker="this week">Weekly goal</CardTitle>
      <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
        <div style={{ position: "relative", width: 152, height: 152, flexShrink: 0 }}>
          <svg viewBox="0 0 152 152" width={152} height={152}>
            <circle cx="76" cy="76" r={R} fill="none" stroke="var(--row)" strokeWidth="14" />
            <circle cx="76" cy="76" r={R} fill="none"
              stroke="var(--sun)" strokeWidth="14" strokeLinecap="round"
              strokeDasharray={`${C * pct} ${C}`} transform="rotate(-90 76 76)" />
            <circle cx="76" cy="6" r="4" fill="var(--warm)" />
            <circle cx="146" cy="76" r="4" fill="var(--a1)" />
            <circle cx="76" cy="146" r="4" fill="var(--a2)" />
            <circle cx="6" cy="76" r="4" fill="var(--good)" />
          </svg>
          <div style={{ position: "absolute", inset: 0, display: "grid", placeItems: "center", textAlign: "center" }}>
            <div>
              <div style={{ fontFamily: D_FONT_SERIF, fontSize: 40, fontWeight: 500, color: "var(--ink)", lineHeight: 1 }}>{done}</div>
              <div style={{ fontSize: 12, color: "var(--sub)", marginTop: 4 }}>of {goal}</div>
            </div>
          </div>
        </div>
        <div style={{ minWidth: 0 }}>
          <Hand size={22} color="var(--a1-dk)" style={{ display: "block" }}>{ringText}</Hand>
          <div style={{ marginTop: 8, color: "var(--sub)", fontSize: 13, lineHeight: 1.45 }}>{ringSub}</div>
          <div style={{ display: "flex", gap: 4, marginTop: 12, flexWrap: "wrap" }}>
            {["M","T","W","T","F","S","S"].map((d, i) => {
              const has = i < 4;
              return (
                <div key={i} style={{
                  width: 28, height: 36, borderRadius: "var(--radius-tag)", display: "grid", placeItems: "center",
                  background: has ? "var(--sun)" : "var(--row)",
                  color: has ? "var(--ink)" : "var(--sub)",
                  fontWeight: 700, fontSize: 11,
                }}>{d}</div>
              );
            })}
          </div>
        </div>
      </div>
    </Card>
  );
}

// ─── Funnel ────────────────────────────────────────────────────────
function Funnel({ theme, items }) {
  const tone = {
    neutral: "var(--row)",
    sky:     "var(--a1)",
    lilac:   "var(--a2)",
    sun:     "var(--sun)",
    coral:   "var(--warm)",
    mint:    "var(--good)",
  };
  return (
    <Card>
      <CardTitle kicker="your funnel">{theme.copy.funnelTitle}</CardTitle>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: 8 }}>
        {items.map((it, i) => (
          <div key={it.key} style={{ position: "relative" }}>
            <div style={{
              background: tone[it.tone] || "var(--row)",
              borderRadius: "var(--radius-tag)", padding: "14px 12px", textAlign: "center",
              border: it.tone === "neutral" ? "1px solid var(--line)" : "none",
              opacity: it.count === 0 ? 0.55 : (theme.dark ? 0.92 : 1),
              minHeight: 84,
            }}>
              <div style={{ fontFamily: D_FONT_SERIF, fontSize: 26, fontWeight: 500, color: "var(--ink)", lineHeight: 1 }}>{it.count}</div>
              <div style={{ fontSize: 11, color: "var(--ink)", marginTop: 6, fontWeight: 600 }}>{it.label}</div>
            </div>
            {i < items.length - 1 && (
              <div style={{ position: "absolute", right: -7, top: "50%", transform: "translateY(-50%)", color: "var(--sub)", fontSize: 14, zIndex: 1 }}>→</div>
            )}
          </div>
        ))}
      </div>
      <Hand size={18} color="var(--a2-dk)" style={{ display: "block", marginTop: 14, textAlign: "right" }}>
        {theme.copy.funnelFooter}
      </Hand>
    </Card>
  );
}

// ─── Sparkline ─────────────────────────────────────────────────────
function Sparkline({ theme, data }) {
  const W = 280, H = 70, max = Math.max(...data, 1);
  const step = W / (data.length - 1);
  const pts = data.map((v, i) => [i*step, H - (v/max)*H]).map(p => p.join(",")).join(" ");
  const area = `0,${H} ` + pts + ` ${W},${H}`;
  return (
    <Card pad={20}>
      <CardTitle kicker="momentum">Last 14 days</CardTitle>
      <svg viewBox={`0 0 ${W} ${H+12}`} width="100%" height={H+12}>
        <polygon points={area} fill="var(--a1)" opacity="0.25" />
        <polyline points={pts} fill="none" stroke="var(--a1-dk)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
        {data.map((v, i) => (
          <circle key={i} cx={i*step} cy={H - (v/max)*H} r={v > 0 ? 3 : 1.5} fill={v > 0 ? "var(--sun)" : "var(--line)"} />
        ))}
      </svg>
      <div style={{ display: "flex", justifyContent: "space-between", marginTop: 6, color: "var(--sub)", fontSize: 11 }}>
        <span>May 7</span><span>today</span>
      </div>
      <div style={{ marginTop: 10, fontSize: 13, color: "var(--ink)", lineHeight: 1.45 }}>{theme.copy.sparklineCopy}</div>
    </Card>
  );
}

// ─── Job card + Today's picks ──────────────────────────────────────
function JobCard({ job, onTailor, onApply }) {
  const interestColor = {
    very_interested: "var(--warm)",
    interested:      "var(--a1)",
    not_reviewed:    "var(--line)",
    not_interested:  "var(--sub)",
  }[job.interest];
  return (
    <div style={{
      background: "var(--paper)",
      borderRadius: "calc(var(--radius-card) - 4px)",
      padding: 16,
      border: "1px solid var(--line)",
      borderLeft: `5px solid ${interestColor}`,
      display: "flex", flexDirection: "column", gap: 10, height: "100%",
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: 11, color: "var(--sub)", fontWeight: 700, letterSpacing: 0.5, textTransform: "uppercase" }}>{job.company}</div>
          <div style={{ fontFamily: D_FONT_SERIF, fontSize: 18, fontWeight: 500, color: "var(--ink)", marginTop: 2, lineHeight: 1.2 }}>{job.role}</div>
        </div>
        <div style={{
          background: "var(--sun)", color: "var(--ink)",
          padding: "4px 9px", borderRadius: "var(--radius-pill)", fontWeight: 800, fontSize: 12,
        }}>{Math.round(job.score * 100)}</div>
      </div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", fontSize: 12, color: "var(--sub)" }}>
        <span>📍 {job.location}</span><span>·</span><span>{job.source}</span><span>·</span><span>{job.posted}</span>
      </div>
      <div style={{ display: "flex", gap: 8, marginTop: "auto" }}>
        <button onClick={onTailor} style={{
          flex: 1, background: "var(--a2)", color: "var(--ink)", border: "none",
          padding: "8px 12px", borderRadius: "calc(var(--radius-pill) / 1.5)",
          fontWeight: 700, fontSize: 12, cursor: "pointer", fontFamily: D_FONT_SANS,
        }}>Tailor →</button>
        <button onClick={onApply} style={{
          flex: 1, background: "var(--ink)", color: "var(--bg)", border: "none",
          padding: "8px 12px", borderRadius: "calc(var(--radius-pill) / 1.5)",
          fontWeight: 700, fontSize: 12, cursor: "pointer", fontFamily: D_FONT_SANS,
        }}>Apply ✓</button>
      </div>
    </div>
  );
}

function TodaysPicks({ theme, jobs, onTailor, onApply }) {
  return (
    <Card>
      <CardTitle kicker={theme.copy.picksKicker} action={
        <span style={{ fontSize: 12, color: "var(--sub)" }}>3 of 47</span>
      }>{theme.copy.picksTitle}</CardTitle>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
        {jobs.slice(0, 3).map(j => <JobCard key={j.id} job={j} onTailor={onTailor} onApply={onApply} />)}
      </div>
    </Card>
  );
}

// ─── Pick-me-up ────────────────────────────────────────────────────
// Reads from the content-providers registry. The user picks which
// providers feed this card during onboarding (saved in prefs.providers).
// Each shuffle pulls from the next enabled provider in rotation, so the
// card is never the same kind two times running unless only one is on.
function PickMeUp({ theme, content, providerName, onShuffle }) {
  // If the user disabled every provider, the card hides entirely.
  if (!content) return null;
  const isImage = content.kind === 'image+text';
  const isPractice = content.kind === 'practice';

  return (
    <Card style={{ background: "linear-gradient(160deg, var(--paper), var(--row))" }}>
      <CardTitle kicker={providerName || theme.copy.pickMeUpKicker} action={
        <button onClick={onShuffle} style={{
          background: "var(--row)", border: "1px solid var(--line)",
          color: "var(--ink)", fontSize: 11, fontWeight: 700, padding: "6px 10px",
          borderRadius: "var(--radius-pill)", cursor: "pointer", fontFamily: D_FONT_SANS,
        }}>🎲 new one</button>
      }>{theme.copy.pickMeUpTitle}</CardTitle>

      {isImage && (
        <PhotoPlaceholder caption={content.caption} bg={content.bg} height={130} />
      )}

      <div style={{
        marginTop: isImage ? 12 : 0, padding: isPractice ? "18px 14px" : 14,
        borderRadius: "var(--radius-tag)",
        background: "var(--row)",
        border: isPractice ? "1px solid var(--a1)" : "1px dashed var(--line)",
        minHeight: isImage ? 'auto' : 130,
        display: "flex", flexDirection: "column", justifyContent: "center",
      }}>
        <Hand size={22} color="var(--a1-dk)"
          style={{ display: "block", whiteSpace: content.multiline ? "pre-line" : "normal", lineHeight: 1.4 }}>
          {content.primary}
        </Hand>
        {content.secondary && (
          <div style={{
            fontSize: 13, color: "var(--ink)", marginTop: 6, lineHeight: 1.5,
            opacity: content.mood === 'reflective' ? 0.75 : 1,
            fontStyle: content.mood === 'reflective' ? 'italic' : 'normal',
          }}>{content.secondary}</div>
        )}
      </div>
    </Card>
  );
}

// ─── Achievements ──────────────────────────────────────────────────
function Achievements({ theme, items }) {
  return (
    <Card>
      <CardTitle kicker={theme.copy.achKicker}>
        Achievements <span style={{ fontSize: 12, color: "var(--sub)", fontWeight: 400 }}>· 4 of 8</span>
      </CardTitle>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10 }}>
        {items.map(b => (
          <div key={b.id} style={{
            background: b.earned ? "linear-gradient(180deg, var(--row), var(--paper))" : "var(--row)",
            border: `1px dashed ${b.earned ? "var(--sun)" : "var(--line)"}`,
            borderRadius: "var(--radius-tag)", padding: 12, textAlign: "center",
            opacity: b.earned ? 1 : 0.5, position: "relative",
          }}>
            <div style={{ fontSize: 28, filter: b.earned ? "none" : "grayscale(0.8)" }}>{b.icon}</div>
            <div style={{ fontFamily: D_FONT_SERIF, fontSize: 13, color: "var(--ink)", marginTop: 4, fontWeight: 500 }}>{b.name}</div>
            <div style={{ fontSize: 10, color: "var(--sub)", marginTop: 2, lineHeight: 1.3 }}>{b.desc}</div>
            {b.earned && (
              <div style={{ position: "absolute", top: -6, right: -6, width: 22, height: 22, borderRadius: "50%",
                background: "var(--sun)", display: "grid", placeItems: "center", fontSize: 12, fontWeight: 800, color: "var(--ink)" }}>✓</div>
            )}
          </div>
        ))}
      </div>
    </Card>
  );
}

// ─── Jobs table (simplified — same filter logic, themed) ───────────
function JobsTable({ theme, jobs }) {
  const [query, setQuery] = React.useState("");
  const [status, setStatus] = React.useState("all");
  const [hideNot, setHideNot] = React.useState(true);

  const tierOf = (s) => s >= 0.75 ? "strong" : s >= 0.5 ? "good" : s >= 0.2 ? "medium" : "low";
  const filtered = React.useMemo(() => {
    const q = query.trim().toLowerCase();
    return jobs.filter(j => {
      if (hideNot && j.interest === "not_interested") return false;
      if (status !== "all" && j.status !== status) return false;
      if (q && !(`${j.company} ${j.role} ${j.location}`.toLowerCase().includes(q))) return false;
      return true;
    });
  }, [jobs, query, status, hideNot]);

  const selectStyle = {
    background: "var(--paper)", border: "1px solid var(--line)",
    borderRadius: "calc(var(--radius-pill) / 1.5)", padding: "7px 26px 7px 10px",
    fontSize: 12, fontFamily: D_FONT_SANS, color: "var(--ink)", fontWeight: 600,
    cursor: "pointer", appearance: "none",
    backgroundImage: `url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'><path fill='%236F6A82' d='M5 6L0 0h10z'/></svg>")`,
    backgroundRepeat: "no-repeat", backgroundPosition: "right 9px center",
  };

  const statusBg = {
    new: "var(--row)", tailored: "var(--a2)",
    submitted: "var(--sun)", interviewing: "var(--warm)", offered: "var(--good)",
  };

  return (
    <Card>
      <CardTitle kicker={theme.copy.tableKicker} action={
        <span style={{ fontSize: 12, color: "var(--sub)" }}>
          showing <strong style={{ color: "var(--ink)" }}>{filtered.length}</strong> of {jobs.length}
        </span>
      }>{theme.copy.tableTitle}</CardTitle>

      <div style={{
        display: "grid", gridTemplateColumns: "minmax(220px, 1.4fr) 1fr 1fr auto",
        gap: 8, alignItems: "center", marginBottom: 12,
      }}>
        <div style={{ position: "relative" }}>
          <span style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)", fontSize: 14, color: "var(--sub)", pointerEvents: "none" }}>🔎</span>
          <input value={query} onChange={(e) => setQuery(e.target.value)}
            placeholder="search company, role, location…" style={{
              width: "100%", padding: "9px 12px 9px 34px",
              border: "1px solid var(--line)", borderRadius: "calc(var(--radius-pill) / 1.5)",
              background: "var(--paper)", fontFamily: D_FONT_SANS, fontSize: 13,
              color: "var(--ink)", outline: "none",
            }} />
        </div>
        <select value={status} onChange={(e) => setStatus(e.target.value)} style={selectStyle}>
          <option value="all">any status</option>
          <option value="new">new</option>
          <option value="tailored">tailored</option>
          <option value="submitted">submitted</option>
          <option value="interviewing">interviewing</option>
        </select>
        <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: "var(--sub)", cursor: "pointer" }}>
          <input type="checkbox" checked={hideNot} onChange={(e) => setHideNot(e.target.checked)}
            style={{ accentColor: "var(--a1-dk)", width: 14, height: 14 }} />
          hide "pass" jobs
        </label>
        <button onClick={() => { setQuery(""); setStatus("all"); setHideNot(true); }} style={{
          background: "var(--row)", color: "var(--sub)", border: "1px solid var(--line)",
          padding: "8px 14px", borderRadius: "calc(var(--radius-pill) / 1.5)",
          fontWeight: 700, fontSize: 12, cursor: "pointer", fontFamily: D_FONT_SANS, whiteSpace: "nowrap",
        }}>reset</button>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1.6fr 1.6fr 0.9fr 0.7fr 0.8fr 0.9fr", fontSize: 12 }}>
        {["Company","Role","Location","Score","Interest","Action"].map(h => (
          <div key={h} style={{ padding: "8px 8px", color: "var(--sub)", fontWeight: 700, fontSize: 10, textTransform: "uppercase", letterSpacing: 0.8, borderBottom: "1px solid var(--line)" }}>{h}</div>
        ))}
        {filtered.slice(0, 10).map(j => {
          const tier = tierOf(j.score);
          const scoreBg = tier === "strong" ? "var(--sun)" : tier === "good" ? "var(--good)" : tier === "medium" ? "var(--row)" : "var(--line)";
          return (
            <React.Fragment key={j.id}>
              <div style={{ padding: "12px 8px", borderBottom: "1px solid var(--row)", fontWeight: 600, color: "var(--ink)" }}>{j.company}</div>
              <div style={{ padding: "12px 8px", borderBottom: "1px solid var(--row)", color: "var(--ink)" }}>
                {j.role}
                <div style={{ fontSize: 10, color: "var(--sub)", marginTop: 2 }}>{j.source} · {j.posted}</div>
              </div>
              <div style={{ padding: "12px 8px", borderBottom: "1px solid var(--row)", color: "var(--sub)" }}>{j.location}</div>
              <div style={{ padding: "12px 8px", borderBottom: "1px solid var(--row)" }}>
                <span style={{ background: scoreBg, borderRadius: "var(--radius-pill)", padding: "2px 8px", fontWeight: 800, fontSize: 11, color: "var(--ink)" }}>{Math.round(j.score*100)}</span>
              </div>
              <div style={{ padding: "12px 8px", borderBottom: "1px solid var(--row)" }}>
                <span style={{
                  background: j.interest === "very_interested" ? "var(--warm)" : j.interest === "interested" ? "var(--a1)" : "var(--row)",
                  borderRadius: "var(--radius-pill)", padding: "4px 8px", fontSize: 11, fontWeight: 700, color: "var(--ink)",
                }}>
                  {j.interest === "very_interested" ? "♥ very" : j.interest === "interested" ? "● yes" : j.interest === "not_reviewed" ? "—" : "pass"}
                </span>
              </div>
              <div style={{ padding: "12px 8px", borderBottom: "1px solid var(--row)" }}>
                {j.status === "new" || j.status === "tailored" ? (
                  <button style={{ background: "var(--ink)", color: "var(--bg)", border: "none", padding: "5px 12px", borderRadius: "var(--radius-pill)", fontWeight: 700, fontSize: 11, cursor: "pointer", fontFamily: D_FONT_SANS }}>
                    {j.status === "tailored" ? "Apply ✓" : "Apply →"}
                  </button>
                ) : (
                  <span style={{ background: statusBg[j.status] || "var(--row)", color: "var(--ink)", padding: "4px 10px", borderRadius: "var(--radius-pill)", fontWeight: 700, fontSize: 11 }}>{j.status}</span>
                )}
              </div>
            </React.Fragment>
          );
        })}
      </div>
    </Card>
  );
}

// ─── Affirmation toast ─────────────────────────────────────────────
function Affirmation({ theme, prefs, text, onClose }) {
  const Mascot = theme.mascot ? window.MASCOTS[theme.mascot] : null;
  return (
    <div style={{
      position: "absolute", left: "50%", top: 90, transform: "translateX(-50%)",
      background: "var(--ink)", color: "var(--bg)",
      padding: "14px 22px", borderRadius: "var(--radius-pill)",
      boxShadow: "0 16px 30px -10px rgba(0,0,0,0.4)",
      display: "flex", alignItems: "center", gap: 12, zIndex: 60, maxWidth: 520,
      animation: "a-pop 0.4s cubic-bezier(.2,.8,.4,1.4)",
    }}>
      <style>{`@keyframes a-pop { from { transform: translateX(-50%) translateY(-10px) scale(0.9); opacity: 0; } to { transform: translateX(-50%) translateY(0) scale(1); opacity: 1; } }`}</style>
      {Mascot ? <div style={{ flexShrink: 0 }}><Mascot size={36} /></div> : null}
      <div style={{ fontFamily: D_FONT_SERIF, fontSize: 18, lineHeight: 1.3 }}>{text}</div>
      <button onClick={onClose} style={{ background: "transparent", border: "none", color: "var(--bg)", fontSize: 18, cursor: "pointer", marginLeft: 6, opacity: 0.7 }}>×</button>
    </div>
  );
}

// ─── Confetti (theme-palette aware) ────────────────────────────────
function ThemedConfetti({ theme }) {
  const palette = ["var(--sun)", "var(--warm)", "var(--a1)", "var(--a2)", "var(--good)"];
  // ConfettiBurst doesn't read CSS vars (inline style), so resolve to real hex.
  const resolve = (varname) => {
    const m = varname.match(/var\((--[\w-]+)\)/);
    if (!m) return varname;
    return theme.tokens[m[1]] || varname;
  };
  return <ConfettiBurst palette={palette.map(resolve)} />;
}

// ─── Top-level Dashboard ───────────────────────────────────────────
function Dashboard({ theme, prefs }) {
  const [celebrate, setCelebrate] = React.useState(false);
  const [affirmation, setAffirmation] = React.useState(null);
  const [showLove, setShowLove] = React.useState(true);

  // Pick-me-up content cycles through prefs.providers (an ordered list of
  // provider IDs). Initial pick uses the first; shuffle advances. If the
  // user enabled zero providers, the card hides itself.
  const enabledIds = (prefs.providers && prefs.providers.length) ? prefs.providers : DEFAULT_PROVIDERS;
  const [providerIndex, setProviderIndex] = React.useState(0);
  const [contentState, setContentState] = React.useState(() => {
    const first = getNextContent(enabledIds, -1);
    return { content: first.content, providerName: first.providerName };
  });

  // If the user changes providers (live theme switcher / settings),
  // resync to the new list.
  React.useEffect(() => {
    const next = getNextContent(enabledIds, -1);
    setProviderIndex(next.index);
    setContentState({ content: next.content, providerName: next.providerName });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabledIds.join(',')]);

  const triggerCelebrate = () => {
    setCelebrate(true);
    const arr = theme.copy.affirmations;
    setAffirmation(arr[Math.floor(Math.random() * arr.length)]);
    setTimeout(() => setCelebrate(false), 3200);
    setTimeout(() => setAffirmation(null), 3600);
  };

  const shufflePickMeUp = () => {
    const next = getNextContent(enabledIds, providerIndex);
    setProviderIndex(next.index);
    setContentState({ content: next.content, providerName: next.providerName });
  };

  return (
    <ThemeShell theme={theme}>
      <div style={{ padding: 24, position: "relative", height: "100%" }}>
        {celebrate && <ThemedConfetti theme={theme} />}
        {affirmation && <Affirmation theme={theme} prefs={prefs} text={affirmation} onClose={() => setAffirmation(null)} />}

        <TopBar theme={theme} prefs={prefs} onCelebrate={triggerCelebrate} />
        {showLove && <LoveNote theme={theme} prefs={prefs} onClose={() => setShowLove(false)} />}

        <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: 16, marginTop: 16 }}>
          <WeeklyRing theme={theme} done={8} goal={15} />
          <Sparkline theme={theme} data={sharedSparkline} />
        </div>

        <div style={{ marginTop: 16 }}>
          <Funnel theme={theme} items={sharedFunnel} />
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1.6fr 1fr", gap: 16, marginTop: 16 }}>
          <TodaysPicks theme={theme} jobs={sharedJobs} onTailor={triggerCelebrate} onApply={triggerCelebrate} />
          <PickMeUp theme={theme} content={contentState.content} providerName={contentState.providerName} onShuffle={shufflePickMeUp} />
        </div>

        <div style={{ marginTop: 16 }}>
          <Achievements theme={theme} items={sharedAchievements} />
        </div>

        <div style={{ marginTop: 16 }}>
          <JobsTable theme={theme} jobs={sharedJobs} />
        </div>

        <div style={{ marginTop: 18, textAlign: "center", color: "var(--sub)", fontSize: 12 }}>
          <Hand size={18} color="var(--a2-dk)">{theme.copy.footer}</Hand>
        </div>
      </div>
    </ThemeShell>
  );
}

Object.assign(window, { Dashboard, ThemeShell, Card, CardTitle, Hand });
