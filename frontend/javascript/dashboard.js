(async () => {
  const user = await requireAuth();
  if (!user) return;
  renderNav(user, "dashboard");
  document.querySelector("#welcome").textContent = `Welcome, ${user.username}`;
  try {
    const [docs, chats] = await Promise.all([apiFetch("/documents"), apiFetch("/chat/conversations")]);
    document.querySelector("#stat-docs").textContent = docs.length;
    document.querySelector("#stat-ready").textContent = docs.filter((d) => d.status === "ready").length;
    document.querySelector("#stat-chats").textContent = chats.length;
    const recent = document.querySelector("recent");
    if (docs.length === 0) {
      recent.append(el("p", "muted", "No documents yet. Upload your first one!"));
    }
    for (const doc of docs.slice(0, 5)) {
      const row = el("p");
      row.append(el("span", "", doc.filename + " "));
      row.append(el("span", `badge badge-${doc.status}`, doc.status));
      recent.append(row);
    }
    if (user.role === "admin") {
      document.querySelector("#admin-card").classList.remove("hidden");
      const users = await apiFetch("/auth/users");
      const body = document.querySelector("#users-body");
      for (const u of users) {
        const tr = el("tr");
        tr.append(el("td", "", u.id), el("td", "", u.username), el("td", "", u.email));
        const roleCell = el("td");
        roleCell.append(el("span", `badge badge-${u.role}`, u.role));
        tr.append(roleCell, el("td", "", formatDate(u.created_at)));
        body.append(tr);
      }
    }
  } catch (err) {
    document.querySelector("#error").textContent = err.message;
  }
})();