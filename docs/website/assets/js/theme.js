const root = document.documentElement;
// Shares the same local storage key as the Arelle iXBRL Viewer demo
const storageKey = "ixbrl-viewer-theme";
const darkScheme = matchMedia("(prefers-color-scheme: dark)");
let themeChangeTimer;

try {
  const savedTheme = localStorage.getItem(storageKey);
  if (savedTheme === "light" || savedTheme === "dark") {
    root.dataset.theme = savedTheme;
  }
} catch {}

const isDark = () =>
  root.dataset.theme ? root.dataset.theme === "dark" : darkScheme.matches;

const themeChangeMs = () => {
  const raw = getComputedStyle(root)
    .getPropertyValue("--duration-theme")
    .trim();
  const value = Number.parseFloat(raw);
  if (!Number.isFinite(value) || value < 0) {
    return 200;
  }
  return raw.endsWith("ms") || !raw.endsWith("s") ? value : value * 1000;
};

const initialize = () => {
  const button = document.querySelector("[data-theme-toggle]");
  if (!button) {
    return;
  }
  const updateLabel = () => {
    button.ariaLabel = button.title = isDark()
      ? "Switch to light"
      : "Switch to dark";
  };
  button.addEventListener("click", () => {
    const theme = isDark() ? "light" : "dark";
    clearTimeout(themeChangeTimer);
    root.dataset.themeChanging = "";
    root.dataset.theme = theme;
    try {
      localStorage.setItem(storageKey, theme);
    } catch {}
    themeChangeTimer = setTimeout(
      () => delete root.dataset.themeChanging,
      themeChangeMs(),
    );
    updateLabel();
  });
  darkScheme.addEventListener("change", updateLabel);
  updateLabel();
};

if (document.readyState === "loading") {
  document.addEventListener("readystatechange", initialize, { once: true });
} else {
  initialize();
}
