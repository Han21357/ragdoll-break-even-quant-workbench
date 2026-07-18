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

