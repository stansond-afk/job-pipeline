// Shared dummy data + helpers used by all three directions.
// Schema mirrors the real Solongo DB (postings + applications + interest_level).

const sharedJobs = [
  { id: 1,  company: "World Resources Institute", role: "Sustainability Consultant",   location: "Washington, D.C.", source: "greenhouse", score: 0.86, interest: "very_interested", status: "tailored",     posted: "2d ago" },
  { id: 2,  company: "Brattle Group",             role: "ESG Research Analyst",        location: "Washington, D.C.", source: "greenhouse", score: 0.81, interest: "very_interested", status: "new",          posted: "1d ago" },
  { id: 3,  company: "U.S. Dept. of Energy",      role: "Climate Policy Specialist",   location: "Washington, D.C.", source: "usajobs",    score: 0.78, interest: "interested",      status: "new",          posted: "4h ago" },
  { id: 4,  company: "Fairfax County",            role: "Environmental Program Analyst", location: "Fairfax, VA",    source: "neogov",     score: 0.74, interest: "interested",      status: "new",          posted: "1d ago" },
  { id: 5,  company: "Palantir",                  role: "Operations Analyst — Federal", location: "Washington, D.C.", source: "lever",      score: 0.71, interest: "not_reviewed",    status: "new",          posted: "3d ago" },
  { id: 6,  company: "Bank of America",           role: "Climate Risk Associate",      location: "Remote (US)",      source: "jobspy",     score: 0.69, interest: "not_reviewed",    status: "new",          posted: "12h ago" },
  { id: 7,  company: "EPA",                       role: "Sustainability Program Analyst", location: "Washington, D.C.", source: "usajobs",  score: 0.83, interest: "very_interested", status: "submitted",    posted: "5d ago" },
  { id: 8,  company: "Arlington County",          role: "Climate Resilience Planner",  location: "Arlington, VA",    source: "neogov",     score: 0.66, interest: "interested",      status: "new",          posted: "6h ago" },
  { id: 9,  company: "Capital One",               role: "Sr. Business Analyst",        location: "McLean, VA",       source: "jobspy",     score: 0.58, interest: "not_reviewed",    status: "new",          posted: "2d ago" },
  { id: 10, company: "Montgomery County",         role: "Energy Program Specialist",   location: "Rockville, MD",    source: "neogov",     score: 0.62, interest: "not_reviewed",    status: "new",          posted: "8h ago" },
  { id: 11, company: "Deloitte",                  role: "ESG Consultant",              location: "Washington, D.C.", source: "jobspy",     score: 0.75, interest: "interested",      status: "tailored",     posted: "4d ago" },
  { id: 12, company: "NRDC",                      role: "Policy Associate, Climate",   location: "Washington, D.C.", source: "greenhouse", score: 0.79, interest: "very_interested", status: "interviewing", posted: "1w ago" },
  { id: 13, company: "Booz Allen Hamilton",       role: "Sustainability Strategy Analyst", location: "McLean, VA",  source: "jobspy",     score: 0.61, interest: "not_reviewed",    status: "new",          posted: "5h ago" },
  { id: 14, company: "U.S. Dept. of State",       role: "Foreign Affairs Officer — Energy", location: "Washington, D.C.", source: "usajobs", score: 0.72, interest: "interested",     status: "new",          posted: "1d ago" },
  { id: 15, company: "World Bank",                role: "Climate Finance Analyst",     location: "Washington, D.C.", source: "jobspy",     score: 0.84, interest: "very_interested", status: "submitted",    posted: "3d ago" },
  { id: 16, company: "Loudoun County",            role: "Solid Waste Operations Lead", location: "Leesburg, VA",     source: "neogov",     score: 0.32, interest: "not_interested",  status: "new",          posted: "2d ago" },
  { id: 17, company: "Pew Charitable Trusts",     role: "Officer, Climate & Energy",   location: "Washington, D.C.", source: "greenhouse", score: 0.77, interest: "interested",      status: "new",          posted: "9h ago" },
  { id: 18, company: "Accenture Federal",         role: "Strategy Analyst — Climate",  location: "Arlington, VA",    source: "jobspy",     score: 0.68, interest: "not_reviewed",    status: "new",          posted: "11h ago" },
];

const sharedFunnel = [
  { key: "active",       label: "Active postings", count: 4115, tone: "neutral" },
  { key: "interested",   label: "On her radar",    count: 47,   tone: "sky" },
  { key: "tailored",     label: "Tailored",        count: 12,   tone: "lilac" },
  { key: "submitted",    label: "Applied",         count: 8,    tone: "sun" },
  { key: "interviewing", label: "Interviewing",    count: 1,    tone: "coral" },
  { key: "offered",      label: "Offers",          count: 0,    tone: "mint" },
];

const sharedSparkline = [0,1,0,2,1,3,2,0,1,2,4,2,3,1]; // last 14 days apps

const sharedAchievements = [
  { id: "first_app",    name: "First brave step", desc: "Sent your first application",  earned: true,  icon: "🌱" },
  { id: "tailor_5",     name: "Tailor's apprentice", desc: "Tailored 5 resumes",        earned: true,  icon: "🧵" },
  { id: "week_streak",  name: "Week one warrior", desc: "7-day streak",                 earned: true,  icon: "🔥" },
  { id: "interview",    name: "First interview", desc: "Status → Interviewing",         earned: true,  icon: "💬" },
  { id: "apps_10",      name: "Double digits",   desc: "10 applications submitted",     earned: false, icon: "🏅" },
  { id: "weekly_15",    name: "Quota crusher",   desc: "Hit 15 in a week",              earned: false, icon: "🚀" },
  { id: "month_streak", name: "Steady gardener", desc: "30-day streak",                 earned: false, icon: "🌳" },
  { id: "offer",        name: "The big one",     desc: "Receive an offer",              earned: false, icon: "🌟" },
];

const sharedAffirmations = [
  "Great job, Solongo!",
  "You showed up today. That's enough.",
  "Every 'no' is data, not a verdict.",
  "Look at you go 👀",
  "Beautiful work. Onward.",
  "Pip is so proud of you.",
  "You are doing the hard thing. Slowly. Bravely.",
  "Future you is cheering for present you.",
];

const sharedJokes = [
  { q: "Why did the resume go to therapy?", a: "It had too many unresolved bullet points." },
  { q: "What did the cover letter say to the hiring manager?", a: "'Dear Sir/Madam, please love me.'" },
  { q: "How do you make a hiring manager laugh?", a: "Tell them your salary expectations." },
  { q: "Why don't job searches get along with calendars?", a: "Too many 'we'll get back to you next week's." },
  { q: "What's a job seeker's favorite tea?", a: "Recruitea. (It never arrives.)" },
];

const sharedPickMeUps = [
  { kind: "animal", caption: "Today's baby otter says: you got this 🦦", bg: "#C5D8E8" },
  { kind: "animal", caption: "Capybara on a capybara on a capybara 🐹", bg: "#D8C5E8" },
  { kind: "animal", caption: "A duckling, just for you 🐥",              bg: "#E8E1C5" },
  { kind: "animal", caption: "Sleepy puppy. Big yawn. Tiny paws. 🐶",     bg: "#E8C5C5" },
];

// Soft pastel placeholder: striped sky+cloud animal-photo stand-in.
// Looks intentional, never hides the fact that it's a placeholder.
function PhotoPlaceholder({ caption, bg = "#C5D8E8", height = 140, radius = 18, style = {} }) {
  return (
    <div style={{
      position: "relative", borderRadius: radius, overflow: "hidden", height,
      background: `repeating-linear-gradient(135deg, ${bg} 0 14px, ${shade(bg, 6)} 14px 28px)`,
      display: "flex", alignItems: "flex-end", padding: 12,
      boxShadow: "inset 0 0 0 1px rgba(0,0,0,0.04)",
      ...style,
    }}>
      <div style={{
        background: "rgba(255,255,255,0.92)", color: "#3b3b48",
        fontFamily: "ui-monospace, Menlo, monospace", fontSize: 11,
        padding: "5px 9px", borderRadius: 8, letterSpacing: 0.2,
      }}>{caption}</div>
    </div>
  );
}

function shade(hex, pct) {
  const n = parseInt(hex.slice(1), 16);
  const r = Math.max(0, Math.min(255, (n >> 16) - pct));
  const g = Math.max(0, Math.min(255, ((n >> 8) & 0xff) - pct));
  const b = Math.max(0, Math.min(255, (n & 0xff) - pct));
  return "#" + ((r << 16) | (g << 8) | b).toString(16).padStart(6, "0");
}

// Simple confetti burst — absolutely-positioned dots falling.
function ConfettiBurst({ palette, count = 36 }) {
  const pieces = React.useMemo(() => Array.from({ length: count }, (_, i) => ({
    left: Math.random() * 100,
    delay: Math.random() * 0.5,
    duration: 2.4 + Math.random() * 1.2,
    color: palette[i % palette.length],
    size: 6 + Math.random() * 8,
    rot: Math.random() * 360,
    drift: -40 + Math.random() * 80,
  })), [count, palette]);
  return (
    <div style={{ position: "absolute", inset: 0, pointerEvents: "none", overflow: "hidden", zIndex: 50 }}>
      <style>{`
        @keyframes confetti-fall {
          0%   { transform: translate(0, -20px) rotate(0deg); opacity: 1; }
          90%  { opacity: 1; }
          100% { transform: translate(var(--dx, 0px), 1200px) rotate(720deg); opacity: 0.4; }
        }
      `}</style>
      {pieces.map((p, i) => (
        <div key={i} style={{
          position: "absolute", top: 0, left: p.left + "%", width: p.size, height: p.size * 1.4,
          background: p.color, borderRadius: 2,
          transform: `rotate(${p.rot}deg)`,
          animation: `confetti-fall ${p.duration}s cubic-bezier(.2,.6,.4,1) ${p.delay}s forwards`,
          ["--dx"]: p.drift + "px",
        }} />
      ))}
    </div>
  );
}

// Capybara mascot — drawn entirely from ellipses + circles (no complex paths).
function Capybara({ size = 72, mood = "happy", style = {} }) {
  // mood: happy | encouraging | sleepy
  const eyeY = mood === "sleepy" ? 56 : 54;
  const eyeH = mood === "sleepy" ? 1 : 4;
  return (
    <svg viewBox="0 0 120 110" width={size} height={size * (110/120)} style={style}>
      {/* ears */}
      <ellipse cx="42" cy="32" rx="9" ry="7" fill="#a47b56" />
      <ellipse cx="78" cy="32" rx="9" ry="7" fill="#a47b56" />
      <ellipse cx="42" cy="33" rx="4" ry="3" fill="#7d5d40" />
      <ellipse cx="78" cy="33" rx="4" ry="3" fill="#7d5d40" />
      {/* head */}
      <ellipse cx="60" cy="55" rx="36" ry="30" fill="#c39673" />
      {/* snout */}
      <ellipse cx="60" cy="74" rx="22" ry="14" fill="#d8b08c" />
      {/* eyes */}
      <ellipse cx="48" cy={eyeY} rx="3.5" ry={eyeH} fill="#2a2a3a" />
      <ellipse cx="72" cy={eyeY} rx="3.5" ry={eyeH} fill="#2a2a3a" />
      {/* eye highlights */}
      {mood !== "sleepy" && <>
        <circle cx="49" cy="53" r="1" fill="#fff" />
        <circle cx="73" cy="53" r="1" fill="#fff" />
      </>}
      {/* cheek blush */}
      <ellipse cx="36" cy="66" rx="5" ry="3" fill="#f0a89c" opacity="0.55" />
      <ellipse cx="84" cy="66" rx="5" ry="3" fill="#f0a89c" opacity="0.55" />
      {/* nose */}
      <ellipse cx="60" cy="70" rx="3" ry="2" fill="#2a2a3a" />
      {/* smile */}
      <ellipse cx="60" cy="78" rx="6" ry="3" fill="none" stroke="#2a2a3a" strokeWidth="1.4" strokeLinecap="round" />
      {/* flower behind ear */}
      <circle cx="32" cy="22" r="3" fill="#f4d87c" />
      <circle cx="30" cy="18" r="2.5" fill="#f0a89c" />
      <circle cx="34" cy="17" r="2.5" fill="#c9b8e0" />
      <circle cx="36" cy="22" r="2.5" fill="#9cc3e8" />
      <circle cx="32" cy="22" r="1.5" fill="#fbf7ef" />
    </svg>
  );
}

// Bumblebee mascot for direction B — concentric ellipses.
function Bumblebee({ size = 64, style = {} }) {
  return (
    <svg viewBox="0 0 120 100" width={size} height={size * (100/120)} style={style}>
      {/* wings */}
      <ellipse cx="42" cy="34" rx="22" ry="14" fill="#dfeaf6" opacity="0.85" />
      <ellipse cx="78" cy="34" rx="22" ry="14" fill="#dfeaf6" opacity="0.85" />
      <ellipse cx="42" cy="34" rx="22" ry="14" fill="none" stroke="#9cc3e8" strokeWidth="1.5" />
      <ellipse cx="78" cy="34" rx="22" ry="14" fill="none" stroke="#9cc3e8" strokeWidth="1.5" />
      {/* body */}
      <ellipse cx="60" cy="58" rx="32" ry="22" fill="#f4d87c" />
      {/* stripes */}
      <ellipse cx="50" cy="58" rx="3.5" ry="22" fill="#3b3b48" />
      <ellipse cx="70" cy="58" rx="3.5" ry="22" fill="#3b3b48" />
      {/* head */}
      <circle cx="32" cy="58" r="11" fill="#3b3b48" />
      {/* eye */}
      <circle cx="28" cy="56" r="2" fill="#fff" />
      <circle cx="28" cy="56" r="1" fill="#2a2a3a" />
      {/* smile */}
      <path d="M 25 62 Q 28 65 31 62" fill="none" stroke="#f4d87c" strokeWidth="1.4" strokeLinecap="round" />
      {/* antennae */}
      <circle cx="26" cy="46" r="2" fill="#3b3b48" />
      <circle cx="34" cy="44" r="2" fill="#3b3b48" />
      <ellipse cx="26" cy="50" rx="0.8" ry="4" fill="#3b3b48" />
      <ellipse cx="34" cy="49" rx="0.8" ry="4" fill="#3b3b48" />
      {/* stinger */}
      <ellipse cx="91" cy="58" rx="3" ry="2" fill="#3b3b48" />
    </svg>
  );
}

// Cloud sheep mascot for direction C — clusters of circles.
function CloudSheep({ size = 80, style = {} }) {
  return (
    <svg viewBox="0 0 130 100" width={size} height={size * (100/130)} style={style}>
      {/* cloud body */}
      <circle cx="40" cy="60" r="20" fill="#fbf7ef" />
      <circle cx="60" cy="50" r="24" fill="#fbf7ef" />
      <circle cx="82" cy="58" r="20" fill="#fbf7ef" />
      <circle cx="50" cy="70" r="18" fill="#fbf7ef" />
      <circle cx="72" cy="72" r="16" fill="#fbf7ef" />
      <ellipse cx="60" cy="70" rx="38" ry="14" fill="#fbf7ef" />
      {/* outline */}
      <ellipse cx="60" cy="65" rx="42" ry="22" fill="none" stroke="#dfe5f0" strokeWidth="1.5" />
      {/* face */}
      <circle cx="98" cy="62" r="12" fill="#3b3b48" />
      <circle cx="95" cy="60" r="2" fill="#fff" />
      <circle cx="101" cy="60" r="2" fill="#fff" />
      <circle cx="95" cy="60" r="0.9" fill="#2a2a3a" />
      <circle cx="101" cy="60" r="0.9" fill="#2a2a3a" />
      <ellipse cx="98" cy="67" rx="3" ry="2" fill="#f0a89c" opacity="0.7" />
      {/* tuft on top */}
      <circle cx="98" cy="50" r="6" fill="#fbf7ef" />
      {/* legs */}
      <rect x="46" y="84" width="4" height="8" rx="2" fill="#3b3b48" />
      <rect x="58" y="86" width="4" height="8" rx="2" fill="#3b3b48" />
      <rect x="70" y="86" width="4" height="8" rx="2" fill="#3b3b48" />
      <rect x="82" y="84" width="4" height="8" rx="2" fill="#3b3b48" />
    </svg>
  );
}

Object.assign(window, {
  sharedJobs, sharedFunnel, sharedSparkline, sharedAchievements,
  sharedAffirmations, sharedJokes, sharedPickMeUps,
  PhotoPlaceholder, ConfettiBurst,
  Capybara, Bumblebee, CloudSheep, shade,
});
