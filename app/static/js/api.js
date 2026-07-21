window.RagdollAPI = {
  async request(path, options = {}) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), options.timeoutMs || 25000);
    try {
      const isForm = options.body instanceof FormData;
      const response = await fetch(path, {
        headers: { ...(isForm ? {} : { "Content-Type": "application/json" }), ...(options.headers || {}) },
        ...options,
        signal: options.signal || controller.signal,
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) {
        const error = new Error(body.error || (body.errors || []).join("；") || `HTTP ${response.status}`);
        error.payload = body;
        throw error;
      }
      return body;
    } catch (error) {
      if (error.name === "AbortError") throw new Error(`请求25秒内未完成：${path}`);
      throw error;
    } finally {
      clearTimeout(timeout);
    }
  },
  get(path) { return this.request(path); },
  post(path, payload) { return this.request(path, { method: "POST", body: JSON.stringify(payload || {}) }); },
  put(path, payload) { return this.request(path, { method: "PUT", body: JSON.stringify(payload || {}) }); },
  delete(path) { return this.request(path, { method: "DELETE" }); },
  upload(path, form) { return this.request(path, { method: "POST", body: form, timeoutMs: 45000 }); },
};
