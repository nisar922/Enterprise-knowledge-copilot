const TOKEN_KEY = "copilot_token";
const LOGIN_URL = "/ui/html/login.html";
function getToken() { return localStorage.getItem(TOKEN_KEY); }
function setToken(token) { localStorage.setItem(TOKEN_KEY, token); }
function logout() {
  localStorage.removeItem(TOKEN_KEY);
  window.location.href = LOGIN_URL;
}
async function apiFetch(path, options = {}) {
  const headers = new Headers(options.headers || {});
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const res = await fetch(path, { ...options, headers });
  if (res.status === 401 && path !== "/auth/login") {
    logout();
    throw new Error("Session expired, please log in again");
  }
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const data = await res.json();
      if (typeof data.detail === "string") detail = data.detail;
      else if (Array.isArray(data.detail)) detail = data.detail.map((d) => d.msg).join(", ");
    } catch (_) {}
    throw new Error(detail);
  }
  return res.status === 204 ? null : res.json();
}
async function requireAuth() {
  if (!getToken()) {
    logout();
    return null;
  }
  return apiFetch("/auth/me");
}
function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}
function formatDate(iso) {
  return new Date(iso).toLocaleString();
}
function renderNav(user, active) {
  const nav = document.querySelector("#nav");
  nav.className = "navbar";
  nav.replaceChildren(el("span", "brand", "Knowledge Copilot"));
  const pages = [["dashboard", "Dashboard"], ["documents", "Documents"], ["chat", "Chat"], ["analytics", "Analytics"]];
  for (const [page, label] of pages) {
    const link = el("a", page === active ? "active" : "", label);
    link.href = `/ui/html/${page}.html`;
    nav.append(link);
  }
  nav.append(el("span", "spacer"));
  nav.append(el("span", "muted", user.username));
  nav.append(el("span", `badge badge-${user.role}`, user.role));
  const btn = el("button", "btn btn-outline btn-sm", "Logout");
  btn.addEventListener("click", logout);
  nav.append(btn);
}