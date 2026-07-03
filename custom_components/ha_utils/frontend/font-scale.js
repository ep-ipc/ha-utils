/**
 * Runtime font scaling for ha_utils.
 * Loaded as an ES module via add_extra_js_url — sets --ha-font-size-scale
 * on <html> so HA's built-in calc()-based font tokens scale automatically.
 * Works with the default theme (no /config/themes needed).
 */
const KEY = "ha_utils_font_scale";
let current = null;

function setProps(value) {
  const s = document.documentElement.style;
  if (value.scale != null) {
    s.setProperty("--ha-font-size-scale", String(value.scale));
  }
}

function apply(value) {
  if (!value || typeof value !== "object") return;
  current = value;
  setProps(value);
}

// Re-apply after HA theme changes clear inline styles on <html>.
new MutationObserver(() => {
  if (
    current &&
    !document.documentElement.style.getPropertyValue("--ha-font-size-scale")
  ) {
    setProps(current);
  }
}).observe(document.documentElement, {
  attributes: true,
  attributeFilter: ["style"],
});

// window.hassConnection is Promise<{auth, conn}>.
function getConn() {
  if (window.hassConnection) return window.hassConnection;
  return new Promise((resolve) => {
    const id = setInterval(() => {
      if (window.hassConnection) {
        clearInterval(id);
        resolve(window.hassConnection);
      }
    }, 100);
  });
}

getConn().then(({ conn }) => {
  conn
    .subscribeMessage(
      (msg) => apply(msg.value),
      { type: "frontend/subscribe_system_data", key: KEY }
    )
    .catch(() => {
      // HA version may lack subscribe_system_data — fall back to one-shot get.
      conn
        .sendMessagePromise({ type: "frontend/get_system_data", key: KEY })
        .then((msg) => apply(msg.value))
        .catch(() => {});
    });
});
