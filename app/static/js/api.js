window.RagdollAPI = {
  async request(path, options = {}) {
    const response = await fetch(path, {
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      ...options,
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(body.error || (body.errors || []).join("；") || `HTTP ${response.status}`);
    }
    return body;
  },
  get(path) { return this.request(path); },
  post(path, payload) { return this.request(path, { method: "POST", body: JSON.stringify(payload || {}) }); },
};

// Theme and interaction enhancements are deliberately layered on top of the
// stable workbench scripts so the quant/data paths remain untouched.
const catTheme = document.createElement("link");
catTheme.rel = "stylesheet";
catTheme.href = "/static/css/cat-theme.css";
document.head.appendChild(catTheme);

window.addEventListener("DOMContentLoaded", () => {
  const catExperience = document.createElement("script");
  catExperience.src = "/static/js/cat-experience.js";
  document.body.appendChild(catExperience);
}, { once: true });