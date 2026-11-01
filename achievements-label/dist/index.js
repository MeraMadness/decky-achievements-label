// Achievements Label - Decky plugin (frontend only, no build step).
// Runs in SharedJSContext. Reads the current game's achievement progress from
// Steam's own cache and renders it as an extra column in the Big Picture
// game details bar (next to Last Played / Play Time / Controller).

const manifest = { name: "Achievements Label" };

// Extension point. Steam games get their numbers from Steam itself. For games
// Steam has no achievement data for (non-Steam shortcuts, emulators...), other
// plugins can register a provider here:
//
//   const hub = (window.__achievementsLabel = window.__achievementsLabel || { providers: [] });
//   hub.providers.push(async (appid, name) => ({ unlocked: 3, total: 20 }) /* or null */);
//
// A provider receives the Steam app id and the game's display name and returns
// { unlocked, total } or null. Providers are asked in order; the first answer
// with total > 0 wins. Whichever plugin loads first creates the hub.
const hub = (window.__achievementsLabel = window.__achievementsLabel || { providers: [] });

const STYLE_ID = "ach-label-style";
const BAR_ATTR = "data-ach-bar";
// Hashed class of the bar's flex container (changes on some Steam updates).
// If it stops matching, the text lookup below is used as a fallback.
const BAR_CLASS = "._1mDAVT4sTzFRwJtlKCw2Ws";
const LABEL_TEXT = "Last Played"; // English UI; only used by the fallback

// Layout: put the new column between Play Time and Controller (like the old
// Steam UI) by giving it order 1 and pushing everything after the first two
// columns (Last Played, Play Time) - i.e. Controller, if shown - to order 2. The progress bar is drawn with two background gradients; tune
// the 64px (x offset), 31px (y offset) and 80px (bar width) values to taste.
const CSS = `
[${BAR_ATTR}] > :nth-child(n+3) { order: 2; }
[${BAR_ATTR}]::after {
  order: 1;
  content: "Achievements\\A " var(--ach-text, "—");
  display: var(--ach-display, block);
  white-space: pre;
  margin-left: 24px;
  padding-right: 40px;
  font-size: 12px;
  font-weight: bold;
  line-height: 22px;
  letter-spacing: .5px;
  text-transform: uppercase;
  color: hsla(0, 0%, 100%, .7);
  background:
    linear-gradient(var(--ctp-accent-color, #cba6f7), var(--ctp-accent-color, #cba6f7))
      64px 31px / calc(80px * var(--ach-pct, 0)) 4px no-repeat,
    linear-gradient(hsla(0, 0%, 100%, .2), hsla(0, 0%, 100%, .2))
      64px 31px / 80px 4px no-repeat;
}`;

// Ask Steam to load progress for an app, at most once every 5s per app.
const lastRequest = new Map();
function requestProgress(cache, id) {
  const now = Date.now();
  if (now - (lastRequest.get(id) || 0) < 5000) return;
  lastRequest.set(id, now);
  try { cache.GetAchievementProgress(id); } catch (e) {}
  try { cache.QueueCacheUpdate(id); } catch (e) {}
  try { cache.RequestCacheUpdate(); } catch (e) {} // takes no arguments
}

// Games Steam has no achievement data for: ask the registered providers (if any).
const external = new Map(); // appid -> { data, pending, ts }
const EXTERNAL_REFRESH_MS = 60000;

function appName(id) {
  try {
    const o = appStore.GetAppOverviewByAppID(id);
    if (o && o.display_name) return o.display_name;
  } catch (e) {}
  try {
    const o = [...appStore.allApps].find((a) => a.appid === id);
    if (o && o.display_name) return o.display_name;
  } catch (e) {}
  return null;
}

async function askProviders(id, name) {
  for (const provider of [...hub.providers]) {
    try {
      const r = await provider(id, name);
      if (r && r.total > 0) return { unlocked: r.unlocked, total: r.total };
    } catch (e) {
      console.warn("[Achievements Label] provider failed", e);
    }
  }
  return null;
}

// Returns the last known { unlocked, total } (or null) and refreshes in the background.
function externalProgress(id) {
  if (!hub.providers.length) return null;
  let s = external.get(id);
  if (!s) {
    s = { data: null, pending: false, ts: 0 };
    external.set(id, s);
  }
  if (!s.pending && Date.now() - s.ts > EXTERNAL_REFRESH_MS) {
    const name = appName(id);
    if (!name) {
      s.ts = Date.now();
    } else {
      s.pending = true;
      askProviders(id, name)
        .then((r) => { s.data = r; })
        .catch(() => { s.data = null; })
        .finally(() => { s.pending = false; s.ts = Date.now(); });
    }
  }
  return s.data;
}

function findBigPictureWindow() {
  try {
    const pm = g_PopupManager;
    const popups = pm.GetPopups ? pm.GetPopups() : [...pm.m_mapPopups.values()];
    for (const p of popups) {
      const w = p.m_popup || p.window || p;
      if (w && w.document && w.document.title === "Steam Big Picture Mode") return w;
    }
  } catch (e) {}
  return null;
}

function currentAppId() {
  try {
    const path = SteamUIStore.m_WindowStore.GamepadUIMainWindowInstance.m_history.location.pathname;
    const m = /\/library\/app\/(\d+)/.exec(path);
    return m ? Number(m[1]) : null;
  } catch (e) {
    return null;
  }
}

function ensureStyle(doc) {
  let s = doc.getElementById(STYLE_ID);
  if (!s) {
    s = doc.createElement("style");
    s.id = STYLE_ID;
    doc.head.appendChild(s);
  }
  if (s.textContent !== CSS) s.textContent = CSS; // pick up edits after a plugin reload
}

function ensureBarMarked(doc) {
  if (doc.querySelector(`[${BAR_ATTR}]`)) return;
  let bar = doc.querySelector(BAR_CLASS);
  if (!bar) {
    const label = [...doc.querySelectorAll("div")].find(
      (d) => d.children.length === 0 && d.textContent.trim() === LABEL_TEXT
    );
    // label -> column -> panel -> tool-tip-source -> bar
    bar = label?.parentElement?.parentElement?.parentElement?.parentElement ?? null;
  }
  if (bar) bar.setAttribute(BAR_ATTR, "1");
}

function tick() {
  const win = findBigPictureWindow();
  if (!win) return;
  const doc = win.document;
  ensureStyle(doc);
  ensureBarMarked(doc);

  let text = '"—"';
  let display = "none";
  let pct = 0;
  const id = currentAppId();
  if (id !== null) {
    const cache = appAchievementProgressCache;
    let e = null;
    if (cache.BGameHasAchievements(id)) {
      display = "block"; // Steam knows achievements; show "—" until its cache has them
      e = cache.m_achievementProgress.mapCache.get(id);
      if (!e) requestProgress(cache, id);
    } else {
      e = externalProgress(id); // from registered providers, if any (see "hub" above)
      if (e) display = "block";
    }
    if (e) {
      text = `"${e.unlocked} / ${e.total}"`;
      pct = e.total > 0 ? e.unlocked / e.total : 0;
    }
  }
  const st = doc.documentElement.style;
  st.setProperty("--ach-text", text);
  st.setProperty("--ach-display", display);
  st.setProperty("--ach-pct", String(pct));
}

function cleanup() {
  const win = findBigPictureWindow();
  if (!win) return;
  const doc = win.document;
  doc.getElementById(STYLE_ID)?.remove();
  doc.querySelectorAll(`[${BAR_ATTR}]`).forEach((el) => el.removeAttribute(BAR_ATTR));
  doc.documentElement.style.removeProperty("--ach-text");
  doc.documentElement.style.removeProperty("--ach-display");
  doc.documentElement.style.removeProperty("--ach-pct");
}

const definePlugin = (fn) => (...args) => fn(...args);

var index = definePlugin(() => {
  let timer = null;
  try {
    tick();
    timer = setInterval(() => {
      try { tick(); } catch (e) { console.warn("[Achievements Label]", e); }
    }, 1000);
  } catch (e) {
    console.warn("[Achievements Label] failed to start", e);
  }
  const h = window.SP_REACT.createElement;
  return {
    name: manifest.name,
    content: h(
      "div",
      { style: { padding: "8px 16px", opacity: 0.8 } },
      "Shows unlocked / total achievements in the Big Picture game bar. Nothing to configure."
    ),
    icon: h("span", null, "🏆"),
    onDismount() {
      if (timer) clearInterval(timer);
      try { cleanup(); } catch (e) {}
    },
  };
});

export { index as default };
