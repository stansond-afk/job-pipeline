// content-providers.jsx — Pluggable content sources for the "pick-me-up" card.
//
// Each provider is an object: { id, name, description, kind, getOne(date?) }.
//   kind is one of: 'text', 'image+text', 'practice'  (controls how PickMeUp renders it)
//   getOne() returns { kind, ...payload } — pure data, no React.
//
// The user picks one or more providers in onboarding (or settings). The
// dashboard cycles through whichever they enabled. Adding a new provider =
// new entry in CONTENT_PROVIDERS, register it, done.
//
// All content here is public-domain, attributed where applicable, and
// scrubbed for negativity. Nothing political. Nothing recent enough to be
// contested. Optimistic, calming, or harmlessly silly.

// ─── 1. Optimistic quotes ──────────────────────────────────────────
const QUOTES = [
  { text: "It is never too late to be what you might have been.",         by: "George Eliot" },
  { text: "The world breaks everyone, and afterward many are strong at the broken places.", by: "Ernest Hemingway" },
  { text: "We must accept finite disappointment, but never lose infinite hope.", by: "Martin Luther King Jr." },
  { text: "What lies behind us and what lies before us are tiny matters compared to what lies within us.", by: "Ralph Waldo Emerson" },
  { text: "Hope is the thing with feathers that perches in the soul.",     by: "Emily Dickinson" },
  { text: "You are never too old to set another goal or to dream a new dream.", by: "C. S. Lewis" },
  { text: "Do not go where the path may lead, go instead where there is no path and leave a trail.", by: "Ralph Waldo Emerson" },
  { text: "The future belongs to those who believe in the beauty of their dreams.", by: "Eleanor Roosevelt" },
  { text: "Fall seven times and stand up eight.",                          by: "Japanese proverb" },
  { text: "Keep your face always toward the sunshine, and shadows will fall behind you.", by: "Walt Whitman" },
  { text: "The only way out is through.",                                  by: "Robert Frost" },
  { text: "She is too fond of books, and it has turned her brain.",        by: "Louisa May Alcott" },
  { text: "Whatever you are, be a good one.",                              by: "Abraham Lincoln" },
  { text: "Tomorrow is always fresh, with no mistakes in it yet.",         by: "L. M. Montgomery" },
  { text: "Begin at the beginning, the King said gravely, and go on till you come to the end: then stop.", by: "Lewis Carroll" },
  { text: "Out beyond ideas of wrongdoing and rightdoing, there is a field. I'll meet you there.", by: "Rumi" },
  { text: "We are all in the gutter, but some of us are looking at the stars.", by: "Oscar Wilde" },
  { text: "The best way out is always through.",                           by: "Robert Frost" },
  { text: "Patience is bitter, but its fruit is sweet.",                   by: "Aristotle" },
  { text: "Courage is being scared to death and saddling up anyway.",      by: "John Wayne" },
  { text: "The best time to plant a tree was twenty years ago. The second best time is now.", by: "Chinese proverb" },
  { text: "If we wait until we're ready, we'll be waiting for the rest of our lives.", by: "Lemony Snicket" },
  { text: "Not all those who wander are lost.",                            by: "J. R. R. Tolkien" },
  { text: "I am not afraid of storms, for I am learning how to sail my ship.", by: "Louisa May Alcott" },
  { text: "Above all, do not lose your desire to walk.",                   by: "Søren Kierkegaard" },
];

const QuotesProvider = {
  id: 'quotes',
  name: 'Quotes',
  description: 'Short, optimistic lines from people who got through hard things.',
  blurb: "Tomorrow is always fresh, with no mistakes in it yet. — L. M. Montgomery",
  kind: 'text',
  getOne() {
    const q = QUOTES[Math.floor(Math.random() * QUOTES.length)];
    return { kind: 'text', primary: `"${q.text}"`, secondary: `— ${q.by}`, mood: 'reflective' };
  },
};

// ─── 2. This day in history ────────────────────────────────────────
// Date-keyed; falls back to a curated default if the day has no entry.
// Filtered HARD for positivity — no wars, disasters, deaths, controversy.
// Keys are 'MM-DD'.
const HISTORY = {
  '01-04': { year: 1809, event: "Louis Braille was born — the boy who invented a way for blind people to read." },
  '01-15': { year: 1929, event: "Martin Luther King Jr. was born." },
  '01-27': { year: 1756, event: "Mozart was born in Salzburg." },
  '02-11': { year: 1990, event: "Nelson Mandela walked free after 27 years in prison." },
  '02-12': { year: 1809, event: "Both Abraham Lincoln and Charles Darwin were born — on the same day, on different continents." },
  '03-03': { year: 1847, event: "Alexander Graham Bell was born — the same week the telephone became possible to imagine." },
  '03-14': { year: 1879, event: "Albert Einstein was born in Ulm, Germany." },
  '04-12': { year: 1961, event: "Yuri Gagarin became the first human in space." },
  '04-15': { year: 1452, event: "Leonardo da Vinci was born." },
  '04-22': { year: 1970, event: "The first Earth Day — twenty million people gathered to celebrate the planet." },
  '05-05': { year: 1961, event: "Alan Shepard became the first American in space." },
  '05-19': { year: 1962, event: "Marilyn Monroe sang to John F. Kennedy at Madison Square Garden — a moment of warmth and theatre." },
  '05-20': { year: 1932, event: "Amelia Earhart took off to become the first woman to fly solo across the Atlantic." },
  '05-25': { year: 1977, event: "Star Wars opened — and a generation gained a shared mythology overnight." },
  '05-29': { year: 1953, event: "Edmund Hillary and Tenzing Norgay reached the summit of Everest." },
  '06-05': { year: 1981, event: "The first ride of a sun-powered aircraft across the English Channel." },
  '06-19': { year: 1865, event: "Juneteenth — the enslaved people of Galveston, Texas learned of their freedom." },
  '06-21': { year: 2004, event: "SpaceShipOne became the first privately-built craft to reach space." },
  '07-04': { year: 1776, event: "The American colonies declared independence." },
  '07-20': { year: 1969, event: "Humans walked on the moon for the first time." },
  '07-30': { year: 2003, event: "The last classic Volkswagen Beetle rolled off the production line — over 21 million made." },
  '08-04': { year: 1944, event: "Anne Frank was discovered, but her diary survived to become a quiet voice for the world." },
  '08-28': { year: 1963, event: "Martin Luther King Jr. delivered \"I Have a Dream\" on the steps of the Lincoln Memorial." },
  '09-09': { year: 1956, event: "Elvis Presley first appeared on Ed Sullivan — and television was never the same." },
  '09-22': { year: 1862, event: "Lincoln issued the preliminary Emancipation Proclamation." },
  '10-04': { year: 1957, event: "Sputnik launched — humans began to leave the planet." },
  '10-31': { year: 1517, event: "Martin Luther nailed his 95 theses to the church door — the start of the Reformation." },
  '11-09': { year: 1989, event: "The Berlin Wall fell." },
  '11-14': { year: 1840, event: "Claude Monet was born — and would teach the world to see light differently." },
  '12-01': { year: 1955, event: "Rosa Parks refused to give up her seat in Montgomery, Alabama." },
  '12-17': { year: 1903, event: "The Wright brothers flew the first powered aircraft at Kitty Hawk." },
  '12-25': { year: 1642, event: "Isaac Newton was born — and quietly began reshaping our understanding of the universe." },
};
const HISTORY_DEFAULTS = [
  { year: null, event: "Today, somewhere, someone is starting over. So are you." },
  { year: null, event: "Today, somewhere, a kid is reading their first book." },
  { year: null, event: "Today, the sun rose. It will rise again tomorrow. That's the deal." },
];

const HistoryProvider = {
  id: 'history',
  name: 'On this day',
  description: 'Something positive that happened today, in history.',
  blurb: "On May 20, 1932 — Amelia Earhart took off to fly the Atlantic solo.",
  kind: 'text',
  getOne(date) {
    const d = date || new Date();
    const key = String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
    const entry = HISTORY[key] || HISTORY_DEFAULTS[Math.floor(Math.random() * HISTORY_DEFAULTS.length)];
    const dateStr = d.toLocaleDateString('en-US', { month: 'long', day: 'numeric' });
    const primary = entry.event;
    const secondary = entry.year
      ? `${dateStr}, ${entry.year}`
      : `${dateStr}`;
    return { kind: 'text', primary, secondary, mood: 'reflective' };
  },
};

// ─── 3. Job-search jokes ───────────────────────────────────────────
const JOKES = [
  { q: "Why did the resume go to therapy?", a: "Too many gaps." },
  { q: "What's a recruiter's favorite chord?", a: "B-flat. (\"Let's circle back.\")" },
  { q: "Why don't applications ever take vacations?", a: "They're always being submitted." },
  { q: "What did the cover letter say to the resume?", a: "\"You complete me. Don't tell HR.\"" },
  { q: "Why was the LinkedIn profile so calm?", a: "It was open to opportunities." },
  { q: "How does a job seeker make tea?", a: "Steeped in optimism, two minutes of doubt, one cube of confetti." },
  { q: "Why did the application cross the road?", a: "To get to the other tab." },
  { q: "What's the most honest line in any job description?", a: "\"Other duties as assigned.\"" },
  { q: "Why do recruiters love spreadsheets?", a: "Because rows don't take rejection personally." },
];

const JokesProvider = {
  id: 'jokes',
  name: 'A little joke',
  description: 'Mostly-corny one-liners about the job hunt.',
  blurb: "Why did the resume go to therapy? Too many gaps.",
  kind: 'text',
  getOne() {
    const j = JOKES[Math.floor(Math.random() * JOKES.length)];
    return { kind: 'text', primary: j.q, secondary: j.a, mood: 'playful' };
  },
};

// ─── 4. Baby animals ───────────────────────────────────────────────
// Until a real photo source is wired in, this returns a placeholder
// description (caption + tinted gradient seed). When the real fetcher
// is wired (e.g. Pexels / Unsplash / a curated set), it returns
// { kind: 'image+text', src, caption, alt }.
const BABY_ANIMAL_CAPTIONS = [
  { caption: "A capybara at sunset.",        bg: ["#f4d87c", "#f0a89c"] },
  { caption: "Two ducklings, sharing.",      bg: ["#fff3c4", "#c9e7f5"] },
  { caption: "A kitten learning gravity.",   bg: ["#fbf7ef", "#e7dfcd"] },
  { caption: "A fox kit, mid-yawn.",         bg: ["#f4d87c", "#c39673"] },
  { caption: "A sleepy red panda.",          bg: ["#f0a89c", "#c39673"] },
  { caption: "Three penguin chicks.",        bg: ["#c9e7f5", "#fbf7ef"] },
  { caption: "An otter floating, paws up.",  bg: ["#87B4C9", "#E8D6A8"] },
  { caption: "A puppy, mid-rumple.",         bg: ["#f4d87c", "#f0a89c"] },
];

const AnimalsProvider = {
  id: 'animals',
  name: 'Baby animals',
  description: 'A daily photo of something small and warm.',
  blurb: "A capybara at sunset. A duckling, mid-step.",
  kind: 'image+text',
  getOne() {
    const a = BABY_ANIMAL_CAPTIONS[Math.floor(Math.random() * BABY_ANIMAL_CAPTIONS.length)];
    return { kind: 'image+text', caption: a.caption, bg: a.bg, mood: 'warm', alt: a.caption };
  },
};

// ─── 5. Calming nature ─────────────────────────────────────────────
const NATURE_CAPTIONS = [
  { caption: "A still lake at first light.",       bg: ["#CFDDE4", "#E8D6A8"] },
  { caption: "Tall grass moving in slow wind.",    bg: ["#A8C089", "#F4E4C9"] },
  { caption: "A pine forest after rain.",          bg: ["#5C7A4F", "#D4CFC4"] },
  { caption: "A wide quiet beach, no one on it.",  bg: ["#EAF1F4", "#E8D6A8"] },
  { caption: "Snow on a single branch.",           bg: ["#F2EFE8", "#CFDDE4"] },
  { caption: "Soft sun through a window.",         bg: ["#F4D87C", "#FBF7EF"] },
  { caption: "A meadow at the long edge of day.",  bg: ["#D9B872", "#9BC498"] },
];

const NatureProvider = {
  id: 'nature',
  name: 'Calm scenes',
  description: 'Quiet places. Nothing happens. That\'s the point.',
  blurb: "A still lake at first light. A pine forest after rain.",
  kind: 'image+text',
  getOne() {
    const n = NATURE_CAPTIONS[Math.floor(Math.random() * NATURE_CAPTIONS.length)];
    return { kind: 'image+text', caption: n.caption, bg: n.bg, mood: 'calm', alt: n.caption };
  },
};

// ─── 6. A breath (mindfulness prompt) ──────────────────────────────
const BREATHS = [
  { lead: "Breathe in for 4.",  body: "Hold for 4. Out for 6. Twice." },
  { lead: "Shoulders down.",    body: "Unclench your jaw. Notice your feet on the floor." },
  { lead: "Look up.",           body: "Find the farthest thing you can see. Hold it for a moment." },
  { lead: "Drink some water.",  body: "Right now, while you read this. The tab will wait." },
  { lead: "Soft eyes.",         body: "Let the screen blur. Look past it. Come back when you're ready." },
  { lead: "Stand up once.",     body: "Stretch your arms over your head. Sit back down. That's it." },
  { lead: "Hands warm?",        body: "Rub your palms together until they are. Hold them over your closed eyes." },
];

const BreathProvider = {
  id: 'breath',
  name: 'A breath',
  description: 'A 10-second prompt to reset your body. No image, no reading.',
  blurb: "Breathe in for 4. Hold for 4. Out for 6.",
  kind: 'practice',
  getOne() {
    const b = BREATHS[Math.floor(Math.random() * BREATHS.length)];
    return { kind: 'practice', primary: b.lead, secondary: b.body, mood: 'practice' };
  },
};

// ─── 7. Short poems ────────────────────────────────────────────────
// Public domain, short, optimistic or quietly hopeful.
const POEMS = [
  { lines: ["Hope is the thing with feathers", "that perches in the soul,", "and sings the tune — without the words,", "and never stops at all."], by: "Emily Dickinson" },
  { lines: ["I dwell in Possibility —", "A fairer House than Prose —"], by: "Emily Dickinson" },
  { lines: ["The woods are lovely, dark and deep,", "But I have promises to keep,", "And miles to go before I sleep."], by: "Robert Frost" },
  { lines: ["Tomorrow, and tomorrow, and tomorrow,", "Creeps in this petty pace from day to day."], by: "Shakespeare" },
  { lines: ["I am the master of my fate,", "I am the captain of my soul."], by: "W. E. Henley" },
  { lines: ["This is the day", "which the Lord hath made;", "let us rejoice and be glad in it."], by: "Psalms 118:24" },
  { lines: ["The fog comes", "on little cat feet."], by: "Carl Sandburg" },
];

const PoemsProvider = {
  id: 'poems',
  name: 'A small poem',
  description: 'Three or four lines. Read them slowly.',
  blurb: "Hope is the thing with feathers / that perches in the soul.",
  kind: 'text',
  getOne() {
    const p = POEMS[Math.floor(Math.random() * POEMS.length)];
    return { kind: 'text', primary: p.lines.join("\n"), secondary: `— ${p.by}`, mood: 'reflective', multiline: true };
  },
};

// ─── Registry ──────────────────────────────────────────────────────
const CONTENT_PROVIDERS = {
  quotes:  QuotesProvider,
  history: HistoryProvider,
  jokes:   JokesProvider,
  animals: AnimalsProvider,
  nature:  NatureProvider,
  breath:  BreathProvider,
  poems:   PoemsProvider,
};

// Default enabled set for new users — broad, inoffensive, optimistic.
// Paper / Quiet Focus / Mountain users tend to want less noise; we don't
// enforce that, just pick a calm default. Users override in onboarding.
const DEFAULT_PROVIDERS = ['quotes', 'history', 'nature', 'breath'];

// Returns the next content item, cycling through enabled providers
// fairly. State (lastProviderIndex) is held by the dashboard component.
function getNextContent(enabledIds, lastIndex) {
  const ids = (enabledIds && enabledIds.length) ? enabledIds : DEFAULT_PROVIDERS;
  const nextIndex = (lastIndex + 1) % ids.length;
  const providerId = ids[nextIndex];
  const provider = CONTENT_PROVIDERS[providerId];
  if (!provider) return { content: null, index: nextIndex, providerId: null };
  return { content: provider.getOne(), index: nextIndex, providerId, providerName: provider.name };
}

Object.assign(window, {
  CONTENT_PROVIDERS, DEFAULT_PROVIDERS, getNextContent,
});
