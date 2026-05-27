// onboarding.jsx — Theme picker. The first screen a new user sees.
// Asks for theme, mascot toggle, name, supporter — writes prefs and shows
// the dashboard.

function ThemeSwatch({ theme }) {
  const Deco = window.DECORATIONS[theme.decoration];
  const Mascot = theme.mascot ? window.MASCOTS[theme.mascot] : null;
  return (
    <div style={{
      ...theme.tokens,
      background: "var(--bg)",
      borderRadius: 10,
      height: 88, position: "relative", overflow: "hidden",
      border: "1px solid var(--line)",
    }}>
      {Deco && <div style={{ position: "absolute", inset: 0 }}><Deco /></div>}
      <div style={{ position: "absolute", left: 10, bottom: 10, display: "flex", alignItems: "flex-end", gap: 8 }}>
        {Mascot ? <Mascot size={36} /> : (
          <div style={{
            width: 36, height: 36, borderRadius: "50%", background: "var(--paper)",
            border: "1.5px solid var(--line)", display: "grid", placeItems: "center",
            fontFamily: "var(--serif)", fontSize: 15, color: "var(--ink)", fontWeight: 500,
          }}>—</div>
        )}
        <div style={{ display: "flex", gap: 4 }}>
          {["--a1", "--a2", "--sun", "--warm", "--good"].map(v => (
            <div key={v} style={{
              width: 10, height: 10, borderRadius: "50%",
              background: `var(${v})`, border: "1px solid rgba(0,0,0,0.06)",
            }} />
          ))}
        </div>
      </div>
      <div style={{ position: "absolute", right: 10, top: 10,
        fontFamily: "var(--serif)", fontSize: 13, fontWeight: 500, color: "var(--ink)" }}>
        Aa
      </div>
    </div>
  );
}

function ThemeCard({ theme, selected, onSelect }) {
  return (
    <button onClick={() => onSelect(theme.id)} style={{
      background: selected ? "color-mix(in oklch, var(--ob-accent) 8%, #fff)" : "#fff",
      border: `2px solid ${selected ? "var(--ob-accent)" : "rgba(0,0,0,0.08)"}`,
      borderRadius: 14, padding: 14, cursor: "pointer", textAlign: "left",
      transition: "all 0.15s ease",
      boxShadow: selected ? "0 8px 20px -10px rgba(0,0,0,0.2)" : "0 1px 2px rgba(0,0,0,0.03)",
      display: "flex", flexDirection: "column", gap: 10,
      fontFamily: "'Inter', system-ui, sans-serif",
    }}>
      <ThemeSwatch theme={theme} />
      <div>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 6 }}>
          <div style={{ fontSize: 15, fontWeight: 600, color: "#1a1a1a", letterSpacing: -0.2 }}>{theme.name}</div>
          {selected && <div style={{
            width: 18, height: 18, borderRadius: "50%", background: "var(--ob-accent)",
            color: "#fff", fontSize: 11, fontWeight: 800,
            display: "grid", placeItems: "center", flexShrink: 0,
          }}>✓</div>}
        </div>
        <div style={{ fontSize: 11, color: "#6b6b6b", marginTop: 3, textTransform: "uppercase", letterSpacing: 0.6, fontWeight: 600 }}>
          {theme.tagline}
        </div>
        <div style={{ fontSize: 12, color: "#4a4a4a", marginTop: 6, lineHeight: 1.45 }}>{theme.blurb}</div>
      </div>
    </button>
  );
}

function Onboarding({ initialPrefs, onComplete, onLive }) {
  // onLive is called whenever any pref changes, so the right-hand preview
  // (in the live demo) can update in real time. onComplete is the final
  // "let me in" handoff.
  const [prefs, setPrefs] = React.useState({ ...DEFAULT_PREFS, ...(initialPrefs || {}) });
  const theme = THEMES[prefs.theme] || THEMES.garden;

  const set = (patch) => setPrefs(p => {
    const next = { ...p, ...patch };
    if (onLive) onLive(next);
    return next;
  });

  // Onboarding chrome uses a neutral palette regardless of theme picked.
  const obStyle = {
    "--ob-bg":     "#FAF8F3",
    "--ob-paper":  "#FFFFFF",
    "--ob-ink":    "#1A1A1A",
    "--ob-sub":    "#6B6B6B",
    "--ob-line":   "rgba(0,0,0,0.1)",
    "--ob-accent": "#2C5282",
  };

  return (
    <div style={{
      ...obStyle,
      width: "100%", height: "100%", overflow: "auto",
      background: "var(--ob-bg)",
      fontFamily: "'Inter', system-ui, sans-serif",
      color: "var(--ob-ink)",
    }}>
      <div style={{ maxWidth: 880, margin: "0 auto", padding: "48px 36px" }}>

        {/* Header */}
        <div style={{ marginBottom: 32 }}>
          <div style={{
            display: "inline-flex", alignItems: "center", gap: 8,
            padding: "4px 10px", borderRadius: 999,
            background: "rgba(0,0,0,0.04)", color: "var(--ob-sub)",
            fontSize: 11, fontWeight: 700, letterSpacing: 1.2, textTransform: "uppercase",
          }}>step 1 · make it yours</div>
          <h1 style={{
            fontFamily: "'Fraunces', Georgia, serif", fontSize: 44, fontWeight: 500,
            margin: "12px 0 8px", letterSpacing: -1, lineHeight: 1.05,
          }}>Welcome to Jobline.</h1>
          <p style={{ fontSize: 16, color: "var(--ob-sub)", lineHeight: 1.55, maxWidth: 600, margin: 0 }}>
            Looking for a job is hard. We made this calm on purpose. Pick a feel that fits
            you — you can change it any time.
          </p>
        </div>

        {/* Theme grid */}
        <Section title="1 · Pick your space" subtitle="Each is a complete reskin. Try them on.">
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 12 }}>
            {Object.values(THEMES).map(t => (
              <ThemeCard key={t.id} theme={t} selected={prefs.theme === t.id} onSelect={(id) => set({ theme: id })} />
            ))}
          </div>
        </Section>

        {/* Mascot toggle (only if current theme has one) */}
        {theme.mascot && (
          <Section title="2 · Want a companion?" subtitle={`${theme.copy.mascotName} is calm, quiet, and quietly proud of you.`}>
            <div style={{ display: "flex", gap: 8 }}>
              <OBToggle label={`Yes — ${theme.copy.mascotName} stays`} active={prefs.mascotEnabled} onClick={() => set({ mascotEnabled: true })} />
              <OBToggle label="No mascot — just initials" active={!prefs.mascotEnabled} onClick={() => set({ mascotEnabled: false })} />
            </div>
          </Section>
        )}

        {/* Personalisation */}
        <Section
          title={theme.mascot ? "3 · Tell us about you" : "2 · Tell us about you"}
          subtitle="Your name shows in greetings. The 'in your corner' name shows in soft reminders that you're not doing this alone.">
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <OBInput label="Your first name"
              value={prefs.name === DEFAULT_PREFS.name ? "" : prefs.name}
              placeholder="Solongo"
              onChange={(v) => set({ name: v || DEFAULT_PREFS.name })} />
            <OBInput label="Who's in your corner?"
              value={prefs.supporter === DEFAULT_PREFS.supporter ? "" : prefs.supporter}
              placeholder="Stanson, my partner"
              onChange={(v) => set({ supporter: v || DEFAULT_PREFS.supporter })} />
          </div>
          <label style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 12, fontSize: 13, color: "var(--ob-sub)", cursor: "pointer" }}>
            <input type="checkbox" checked={prefs.showPersonalNote}
              onChange={(e) => set({ showPersonalNote: e.target.checked })}
              style={{ accentColor: "var(--ob-accent)", width: 15, height: 15 }} />
            Show me a "you are loved" reminder on the dashboard.
          </label>
        </Section>

        {/* Pick-me-up providers */}
        <Section
          title={theme.mascot ? "4 · Your pick-me-up corner" : "3 · Your pick-me-up corner"}
          subtitle="A small daily lift on the dashboard. Pick the kinds you like — or none, and it disappears.">
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 10 }}>
            {Object.values(CONTENT_PROVIDERS).map(p => (
              <ProviderCard key={p.id} provider={p}
                selected={(prefs.providers || []).includes(p.id)}
                onToggle={() => {
                  const cur = prefs.providers || [];
                  const next = cur.includes(p.id) ? cur.filter(x => x !== p.id) : [...cur, p.id];
                  set({ providers: next });
                }} />
            ))}
          </div>
          {(!prefs.providers || prefs.providers.length === 0) && (
            <div style={{
              marginTop: 12, padding: "10px 14px", borderRadius: 8,
              background: "rgba(0,0,0,0.03)", color: "var(--ob-sub)",
              fontSize: 12, fontStyle: "italic",
            }}>None selected — the pick-me-up card will hide itself on your dashboard. That's fine; some people don't want it.</div>
          )}
        </Section>

        {/* Live preview strip */}
        <Section title="Your space, on a Wednesday morning" subtitle="A real card from your future dashboard.">
          <div style={theme.tokens}>
            <div style={{
              background: "var(--bg)", borderRadius: 14, padding: 20, border: "1px solid var(--ob-line)",
            }}>
              <PreviewCard theme={theme} prefs={prefs} />
            </div>
          </div>
        </Section>

        {/* Start button */}
        <div style={{ marginTop: 32, display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16 }}>
          <div style={{ fontSize: 13, color: "var(--ob-sub)" }}>
            You can change any of this later from the dashboard settings.
          </div>
          <button onClick={() => onComplete && onComplete(prefs)} style={{
            background: "var(--ob-ink)", color: "#fff", border: "none",
            padding: "14px 24px", borderRadius: 8, fontSize: 14, fontWeight: 700,
            cursor: "pointer", fontFamily: "inherit", letterSpacing: 0.2,
          }}>Open my dashboard →</button>
        </div>

      </div>
    </div>
  );
}

function Section({ title, subtitle, children }) {
  return (
    <div style={{ marginBottom: 32 }}>
      <div style={{ marginBottom: 12 }}>
        <h2 style={{ fontFamily: "'Fraunces', Georgia, serif", fontSize: 22, fontWeight: 500, margin: 0, letterSpacing: -0.3 }}>{title}</h2>
        {subtitle && <p style={{ fontSize: 13, color: "var(--ob-sub)", margin: "4px 0 0", lineHeight: 1.5 }}>{subtitle}</p>}
      </div>
      {children}
    </div>
  );
}

function OBToggle({ label, active, onClick }) {
  return (
    <button onClick={onClick} style={{
      padding: "10px 14px", borderRadius: 8,
      background: active ? "var(--ob-ink)" : "#fff",
      color: active ? "#fff" : "var(--ob-ink)",
      border: `1.5px solid ${active ? "var(--ob-ink)" : "var(--ob-line)"}`,
      fontSize: 13, fontWeight: 600, cursor: "pointer", fontFamily: "inherit",
    }}>{label}</button>
  );
}

function OBInput({ label, value, onChange, placeholder }) {
  return (
    <label style={{ display: "block" }}>
      <div style={{ fontSize: 12, fontWeight: 600, color: "var(--ob-sub)", marginBottom: 6, letterSpacing: 0.2 }}>{label}</div>
      <input value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} style={{
        width: "100%", padding: "10px 12px", borderRadius: 8,
        border: "1.5px solid var(--ob-line)", background: "#fff",
        fontSize: 14, color: "var(--ob-ink)", fontFamily: "inherit",
        outline: "none", boxSizing: "border-box",
      }} />
    </label>
  );
}

// ProviderCard — a multi-select card for the pick-me-up content registry.
// User can tap any combination; the dashboard cycles through them.
function ProviderCard({ provider, selected, onToggle }) {
  return (
    <button onClick={onToggle} style={{
      textAlign: "left", cursor: "pointer",
      background: selected ? "color-mix(in oklch, var(--ob-accent) 6%, #fff)" : "#fff",
      border: `1.5px solid ${selected ? "var(--ob-accent)" : "var(--ob-line)"}`,
      borderRadius: 10, padding: "12px 14px",
      display: "grid", gridTemplateColumns: "1fr auto", alignItems: "start", gap: 10,
      fontFamily: "inherit",
    }}>
      <div>
        <div style={{ fontSize: 14, fontWeight: 600, color: "var(--ob-ink)" }}>{provider.name}</div>
        <div style={{ fontSize: 12, color: "var(--ob-sub)", marginTop: 3, lineHeight: 1.45 }}>{provider.description}</div>
        <div style={{ fontSize: 11, color: "var(--ob-sub)", marginTop: 6, fontStyle: "italic", opacity: 0.85, lineHeight: 1.4 }}>
          e.g. "{provider.blurb}"
        </div>
      </div>
      <div style={{
        width: 22, height: 22, borderRadius: 6, flexShrink: 0,
        background: selected ? "var(--ob-accent)" : "transparent",
        border: `1.5px solid ${selected ? "var(--ob-accent)" : "var(--ob-line)"}`,
        color: "#fff", fontSize: 13, fontWeight: 800,
        display: "grid", placeItems: "center",
      }}>{selected ? "✓" : ""}</div>
    </button>
  );
}

// A miniature greeting bar — the same TopBar from dashboard.jsx would be
// overkill in onboarding, so this is a streamlined preview.
function PreviewCard({ theme, prefs }) {
  const Mascot = theme.mascot ? window.MASCOTS[theme.mascot] : null;
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 14, padding: "14px 18px",
      borderRadius: "var(--radius-card)", background: "var(--paper)",
      border: "1px solid var(--line)",
    }}>
      <div style={{
        width: 56, height: 56, borderRadius: "50%", background: "var(--bg)",
        display: "grid", placeItems: "center", flexShrink: 0,
      }}>
        {Mascot && prefs.mascotEnabled ? <Mascot size={48} /> : (
          <div style={{ fontFamily: "var(--serif)", fontSize: 22, fontWeight: 500, color: "var(--ink)" }}>
            {(prefs.name || "?").trim()[0]?.toUpperCase() || "?"}
          </div>
        )}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontFamily: "var(--hand)", fontStyle: "italic", fontSize: 18, color: "var(--a1-dk)", lineHeight: 1 }}>
          {theme.copy.greetingScript}
        </div>
        <div style={{
          fontFamily: "var(--serif)", fontSize: 28, fontWeight: 500, color: "var(--ink)",
          lineHeight: 1.05, marginTop: 2, letterSpacing: "-0.3px",
        }}>{prefs.name}<span style={{ color: "var(--warm)" }}>{theme.copy.nameSuffix}</span></div>
        <div style={{ marginTop: 4, color: "var(--sub)", fontSize: 12 }}>
          {theme.copy.mascotSays} <em>"{theme.copy.mascotQuote}"</em>
        </div>
      </div>
      <div style={{
        background: "var(--ink)", color: "var(--bg)", padding: "10px 14px",
        borderRadius: "var(--radius-pill)", fontSize: 12, fontWeight: 700, flexShrink: 0,
      }}>{theme.copy.celebrate}</div>
    </div>
  );
}

Object.assign(window, { Onboarding, ThemeSwatch, ThemeCard, ProviderCard });
