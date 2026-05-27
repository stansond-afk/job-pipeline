// mascots.jsx — One mascot per theme (or null). Registry pattern: the
// dashboard looks up window.MASCOTS[theme.mascot]; if null, falls back to
// a monogram avatar built from the user's initials.
//
// To add a mascot: write a new component, register it in MASCOTS below,
// reference it as `mascot: "yourkey"` in themes.js.

// ─── Capybara (Garden) ──────────────────────────────────────────────
function MascotCapybara({ size = 72, mood = "happy", style = {} }) {
  const eyeY = mood === "sleepy" ? 56 : 54;
  const eyeH = mood === "sleepy" ? 1 : 4;
  return (
    <svg viewBox="0 0 120 110" width={size} height={size * (110 / 120)} style={style}>
      <ellipse cx="42" cy="32" rx="9" ry="7" fill="#a47b56" />
      <ellipse cx="78" cy="32" rx="9" ry="7" fill="#a47b56" />
      <ellipse cx="42" cy="33" rx="4" ry="3" fill="#7d5d40" />
      <ellipse cx="78" cy="33" rx="4" ry="3" fill="#7d5d40" />
      <ellipse cx="60" cy="55" rx="36" ry="30" fill="#c39673" />
      <ellipse cx="60" cy="74" rx="22" ry="14" fill="#d8b08c" />
      <ellipse cx="48" cy={eyeY} rx="3.5" ry={eyeH} fill="#2a2a3a" />
      <ellipse cx="72" cy={eyeY} rx="3.5" ry={eyeH} fill="#2a2a3a" />
      {mood !== "sleepy" && (<>
        <circle cx="49" cy="53" r="1" fill="#fff" />
        <circle cx="73" cy="53" r="1" fill="#fff" />
      </>)}
      <ellipse cx="36" cy="66" rx="5" ry="3" fill="#f0a89c" opacity="0.55" />
      <ellipse cx="84" cy="66" rx="5" ry="3" fill="#f0a89c" opacity="0.55" />
      <ellipse cx="60" cy="70" rx="3" ry="2" fill="#2a2a3a" />
      <ellipse cx="60" cy="78" rx="6" ry="3" fill="none" stroke="#2a2a3a" strokeWidth="1.4" strokeLinecap="round" />
      <circle cx="32" cy="22" r="3" fill="#f4d87c" />
      <circle cx="30" cy="18" r="2.5" fill="#f0a89c" />
      <circle cx="34" cy="17" r="2.5" fill="#c9b8e0" />
      <circle cx="36" cy="22" r="2.5" fill="#9cc3e8" />
      <circle cx="32" cy="22" r="1.5" fill="#fbf7ef" />
    </svg>
  );
}

// ─── Otter (Tide) ───────────────────────────────────────────────────
function MascotOtter({ size = 72, style = {} }) {
  return (
    <svg viewBox="0 0 130 110" width={size} height={size * (110 / 130)} style={style}>
      <ellipse cx="65" cy="96" rx="50" ry="6" fill="#87B4C9" opacity=".4" />
      <ellipse cx="65" cy="100" rx="44" ry="3" fill="#87B4C9" opacity=".3" />
      <ellipse cx="65" cy="76" rx="48" ry="20" fill="#8B6849" />
      <ellipse cx="65" cy="78" rx="36" ry="12" fill="#D4A87A" />
      <circle cx="98" cy="64" r="18" fill="#8B6849" />
      <ellipse cx="108" cy="68" rx="10" ry="7" fill="#D4A87A" />
      <circle cx="96" cy="60" r="2" fill="#2A2A3A" />
      <circle cx="104" cy="60" r="2" fill="#2A2A3A" />
      <circle cx="96.7" cy="59.3" r="0.6" fill="#fff" />
      <circle cx="104.7" cy="59.3" r="0.6" fill="#fff" />
      <ellipse cx="113" cy="66" rx="2" ry="1.5" fill="#2A2A3A" />
      <path d="M111 70 L 118 71 M 111 72 L 118 74" stroke="#2A2A3A" strokeWidth="0.6" opacity=".6" />
      <path d="M108 71 Q 111 73 113 71" fill="none" stroke="#2A2A3A" strokeWidth="0.9" strokeLinecap="round" />
      <ellipse cx="55" cy="68" rx="7" ry="5" fill="#8B6849" />
      <ellipse cx="68" cy="66" rx="7" ry="5" fill="#8B6849" />
      <ellipse cx="55" cy="68" rx="4" ry="2.5" fill="#5E3F2A" opacity=".5" />
      <ellipse cx="68" cy="66" rx="4" ry="2.5" fill="#5E3F2A" opacity=".5" />
      <ellipse cx="20" cy="74" rx="10" ry="4" fill="#8B6849" />
      <circle cx="62" cy="80" r="3" fill="#E89B8E" />
      <path d="M60 80 L 64 80 M 62 78 L 62 82" stroke="#fff" strokeWidth="0.6" opacity=".7" />
    </svg>
  );
}

// ─── Moth (Dusk) ────────────────────────────────────────────────────
function MascotMoth({ size = 72, style = {} }) {
  return (
    <svg viewBox="0 0 120 120" width={size} height={size} style={style}>
      <circle cx="60" cy="60" r="50" fill="#A684C9" opacity=".15" />
      <circle cx="60" cy="60" r="38" fill="#E8B86C" opacity=".1" />
      <path d="M60 56 Q 22 30 14 58 Q 22 74 60 64 Z" fill="#A8D4A8" />
      <path d="M60 56 Q 98 30 106 58 Q 98 74 60 64 Z" fill="#A8D4A8" />
      <path d="M60 64 Q 30 80 20 108 Q 38 96 60 76 Z" fill="#9BC498" />
      <path d="M60 64 Q 90 80 100 108 Q 82 96 60 76 Z" fill="#9BC498" />
      <circle cx="34" cy="58" r="5" fill="#E8B86C" />
      <circle cx="86" cy="58" r="5" fill="#E8B86C" />
      <circle cx="34" cy="58" r="2.5" fill="#2A2336" />
      <circle cx="86" cy="58" r="2.5" fill="#2A2336" />
      <circle cx="34.8" cy="57.2" r="0.8" fill="#fff" />
      <circle cx="86.8" cy="57.2" r="0.8" fill="#fff" />
      <ellipse cx="60" cy="64" rx="4" ry="22" fill="#2A2336" />
      <circle cx="60" cy="44" r="6" fill="#2A2336" />
      <circle cx="57.5" cy="43" r="1.1" fill="#E8B86C" />
      <circle cx="62.5" cy="43" r="1.1" fill="#E8B86C" />
      <path d="M58 40 Q 50 30 46 26 M 62 40 Q 70 30 74 26" stroke="#2A2336" strokeWidth="1.2" fill="none" strokeLinecap="round" />
      <path d="M50 32 L 47 30 M 52 34 L 49 33 M 54 36 L 51 36 M 70 32 L 73 30 M 68 34 L 71 33 M 66 36 L 69 36"
        stroke="#2A2336" strokeWidth="0.7" strokeLinecap="round" opacity=".8" />
    </svg>
  );
}

// ─── Monogram (themes with mascot:null, or mascot disabled) ────────
function MascotMonogram({ size = 72, style = {}, initials = "J" }) {
  return (
    <div style={{
      width: size, height: size, borderRadius: "50%",
      background: "var(--paper)", border: "1.5px solid var(--line)",
      display: "grid", placeItems: "center",
      fontFamily: "var(--serif)", fontSize: size * 0.42,
      fontWeight: 500, color: "var(--ink)", letterSpacing: "-0.02em",
      ...style,
    }}>{initials}</div>
  );
}

const MASCOTS = {
  capybara: MascotCapybara,
  otter:    MascotOtter,
  moth:     MascotMoth,
};

// ─── Decorations (the "skybox" of each greeting bar) ───────────────
// Each is positioned absolutely behind the greeting-bar content and
// reads theme tokens via CSS vars so it harmonizes automatically.

function DecoSunClouds() {
  return (<>
    <div style={{ position: "absolute", right: 220, top: -30, width: 90, height: 90, borderRadius: "50%", background: "var(--sun)", opacity: 0.7 }} />
    <div style={{ position: "absolute", right: 210, top: -20, width: 70, height: 70, borderRadius: "50%", background: "var(--sun)" }} />
    <div style={{ position: "absolute", left: 220, top: 18, width: 60, height: 16, borderRadius: 20, background: "var(--paper)", opacity: 0.85 }} />
    <div style={{ position: "absolute", left: 380, top: 40, width: 40, height: 12, borderRadius: 20, background: "var(--paper)", opacity: 0.85 }} />
  </>);
}

function DecoHorizon() {
  return (
    <svg viewBox="0 0 1200 200" preserveAspectRatio="none" style={{ position: "absolute", inset: 0, width: "100%", height: "100%", opacity: 0.4 }}>
      <line x1="0" y1="160" x2="1200" y2="160" stroke="var(--a1)" strokeWidth="1" opacity="0.4" />
      <line x1="0" y1="170" x2="1200" y2="170" stroke="var(--a1)" strokeWidth="0.6" opacity="0.25" />
      <line x1="0" y1="178" x2="1200" y2="178" stroke="var(--a1)" strokeWidth="0.4" opacity="0.15" />
    </svg>
  );
}

function DecoWaves() {
  return (
    <svg viewBox="0 0 1200 200" preserveAspectRatio="none" style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}>
      <path d="M0 150 Q 150 130 300 150 T 600 150 T 900 150 T 1200 150 L 1200 200 L 0 200 Z" fill="var(--a2)" opacity="0.25" />
      <path d="M0 170 Q 200 155 400 170 T 800 170 T 1200 170 L 1200 200 L 0 200 Z" fill="var(--a1)" opacity="0.2" />
      <circle cx="1080" cy="50" r="40" fill="var(--sun)" opacity="0.5" />
    </svg>
  );
}

function DecoPaper() {
  return (<>
    <div style={{ position: "absolute", left: 0, top: 0, right: 0, height: 1, background: "var(--line)" }} />
    <div style={{ position: "absolute", left: 0, bottom: 0, right: 0, height: 1, background: "var(--line)" }} />
  </>);
}

function DecoStars() {
  const stars = React.useMemo(() => Array.from({length: 22}).map(() => ({
    x: Math.random() * 100, y: Math.random() * 100, r: 0.6 + Math.random() * 1.6, o: 0.3 + Math.random() * 0.6,
  })), []);
  return (
    <svg viewBox="0 0 100 100" preserveAspectRatio="none" style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}>
      {stars.map((s, i) => <circle key={i} cx={s.x} cy={s.y} r={s.r * 0.18} fill="var(--ink)" opacity={s.o} />)}
      <circle cx="92" cy="22" r="6" fill="var(--sun)" opacity="0.8" />
      <circle cx="88" cy="22" r="6" fill="var(--paper)" />
    </svg>
  );
}

function DecoPeak() {
  return (
    <svg viewBox="0 0 1200 200" preserveAspectRatio="none" style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}>
      <path d="M0 180 L 280 70 L 460 150 L 720 30 L 940 130 L 1200 80 L 1200 200 L 0 200 Z" fill="var(--a1)" opacity="0.18" />
      <path d="M0 180 L 280 70 L 460 150 L 720 30 L 940 130 L 1200 80" fill="none" stroke="var(--a1-dk)" strokeWidth="1" opacity="0.4" />
      <path d="M720 30 L 700 60 L 720 50 L 740 60 Z" fill="var(--paper)" opacity="0.6" />
    </svg>
  );
}

const DECORATIONS = {
  "sun-clouds": DecoSunClouds,
  "horizon":    DecoHorizon,
  "waves":      DecoWaves,
  "paper":      DecoPaper,
  "stars":      DecoStars,
  "peak":       DecoPeak,
};

Object.assign(window, {
  MASCOTS, DECORATIONS,
  MascotCapybara, MascotOtter, MascotMoth, MascotMonogram,
});
