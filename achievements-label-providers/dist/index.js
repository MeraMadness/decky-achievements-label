// Achievements Label Providers - Decky plugin (frontend, no build step).
//
// "Achievements Label" draws the Achievements column for Steam games. This plugin
// supplies the numbers for games Steam has no data for (RPCS3 trophies,
// RetroAchievements, Alice's MadnessPatch) through its Python backend (main.py).
// It draws nothing in Big Picture itself; its panel only shows what is set up.

const manifest = { name: "Achievements Label Providers" };

// Same hub Achievements Label uses; whichever plugin loads first creates it.
const hub = (window.__achievementsLabel = window.__achievementsLabel || { providers: [] });

let getProgress = null;
let getStatus = null;
try {
  const init = window.__DECKY_SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED_deckyLoaderAPIInit;
  let api;
  try { api = init.connect(2, manifest.name); } catch (e) { api = init.connect(1, manifest.name); }
  getProgress = api.callable("get_progress");
  getStatus = api.callable("get_status");
} catch (e) {
  console.warn("[Achievements Label Providers] backend unavailable", e);
}

const definePlugin = (fn) => (...args) => fn(...args);

function StatusPanel() {
  const R = window.SP_REACT;
  const h = R.createElement;
  const [s, setS] = R.useState(null);
  R.useEffect(() => {
    let alive = true;
    if (getStatus) Promise.resolve(getStatus()).then((r) => alive && setS(r)).catch(() => {});
    return () => { alive = false; };
  }, []);
  const line = (text) => h("div", { style: { padding: "2px 16px", opacity: 0.85 } }, text);
  if (!s) return line("Loading...");
  return h(
    "div",
    null,
    line("Supplies achievements for non-Steam games to Achievements Label (needs that plugin)."),
    line("RPCS3 trophies: " + (s.rpcs3_games ? s.rpcs3_games + " games found" : "none found")),
    line("RetroAchievements: " + (s.ra_configured ? "user and key set" : "not set up")),
    s.ra_problem ? line("Problem: " + s.ra_problem) : null,
    line("Settings file: " + s.config_path)
  );
}

var index = definePlugin(() => {
  // (appid, name) -> { unlocked, total } | null
  const provider = (appid, name) => (getProgress ? getProgress(name, appid) : null);
  hub.providers.push(provider);

  const h = window.SP_REACT.createElement;
  return {
    name: manifest.name,
    content: h(StatusPanel, null),
    icon: h("span", null, "🏆"),
    onDismount() {
      const i = hub.providers.indexOf(provider);
      if (i >= 0) hub.providers.splice(i, 1);
    },
  };
});

export { index as default };
