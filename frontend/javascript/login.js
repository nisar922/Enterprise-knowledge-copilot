const loginForm = document.querySelector("#login-form");
const registerForm = document.querySelector("#register-form");
const errorBox = document.querySelector("#error");
if (getToken()) window.location.href = "/ui/html/dashboard.html";
function showTab(which) {
  const isLogin = which === "login";
  loginForm.classList.toggle("hidden", !isLogin);
  registerForm.classList.toggle("hidden", isLogin);
  document.querySelector("#tab-login").classList.toggle("active", isLogin);
  document.querySelector("#tab-register").classList.toggle("active", !isLogin);
  errorBox.textContent = "";
}
document.querySelector("#tab-login").addEventListener("click", () => showTab("login"));
document.querySelector("#tab-register").addEventListener("click", () => showTab("register"));
async function login(username, password) {
  const body = new URLSearchParams({ username, password });
  const data = await apiFetch("/auth/login", { method: "POST", body });
  setToken(data.access_token);
  window.location.href = "/ui/html/dashboard.html";
}
loginForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  errorBox.textContent = "";
  try {
    await login(document.querySelector("#login-username").value, document.querySelector("#login-password").value);
  } catch (err) {
    errorBox.textContent = err.message;
  }
});
registerForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  errorBox.textContent = "";
  const username = document.querySelector("#reg-username").value;
  const password = document.querySelector("#reg-password").value;
  try {
    await apiFetch("/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, email: document.querySelector("#reg-email").value, password }),
    });
    await login(username, password);
  } catch (err) {
    errorBox.textContent = err.message;
  }
});