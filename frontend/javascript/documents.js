const MAX_MB = 10;
const ALLOWED = [".pdf", ".docx", ".txt"];
const dropzone = document.querySelector("#dropzone");
const fileInput = document.querySelector("#file-input");
const uploadLog = document.querySelector("#upload-log");
const tbody = document.querySelector("#docs-body");
const searchInput = document.querySelector("#search");
const errorBox = document.querySelector("#error");
const dialog = document.querySelector("#preview-dialog");
let pollTimer = null;

function logMessage(text, type) {
  uploadLog.append(el("li", type, text));
}
async function uploadFiles(files) {
  for (const file of files) {
    const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
    if (!ALLOWED.includes(ext)) { logMessage(`${file.name}: unsupported file type`, "error"); continue; }
    if (file.size > MAX_MB * 1024 * 1024) { logMessage(`${file.name}: larger than ${MAX_MB} MB`, "error"); continue; }
    const form = new FormData();
    form.append("file", file);
    try {
      await apiFetch("/documents/upload", { method: "POST", body: form });
      logMessage(`${file.name}: uploaded, processing...`, "success");
    } catch (err) {
      logMessage(`${file.name}: ${err.message}`, "error");
    }
  }
  fileInput.value = "";
  await loadDocuments();
}
function renderDocuments(docs) {
  tbody.replaceChildren();
  if (docs.length === 0) {
    const tr = el("tr");
    const td = el("td", "muted", "No documents found");
    td.colSpan = 4;
    tr.append(td);
    tbody.append(tr);
    return;
  }
  for (const doc of docs) {
    const tr = el("tr");
    tr.append(el("td", "", doc.filename));
    const statusCell = el("td");
    statusCell.append(el("span", `badge badge-${doc.status}`, doc.status));
    tr.append(statusCell, el("td", "", formatDate(doc.uploaded_at)));
    const actions = el("td");
    const previewBtn = el("button", "btn btn-outline btn-sm", "Preview");
    previewBtn.disabled = doc.status !== "ready";
    previewBtn.addEventListener("click", () => showPreview(doc));
    const deleteBtn = el("button", "btn btn-danger btn-sm", "Delete");
    deleteBtn.style.marginLeft = ".4rem";
    deleteBtn.addEventListener("click", () => deleteDocument(doc));
    actions.append(previewBtn, deleteBtn);
    tr.append(actions);
    tbody.append(tr);
  }
}
async function loadDocuments() {
  clearTimeout(pollTimer);
  try {
    const search = searchInput.value.trim();
    const docs = await apiFetch("/documents" + (search ? `?search=${encodeURIComponent(search)}` : ""));
    errorBox.textContent = "";
    renderDocuments(docs);
    if (docs.some((d) => d.status === "processing")) pollTimer = setTimeout(loadDocuments, 3000);
  } catch (err) {
    errorBox.textContent = err.message;
  }
}
async function deleteDocument(doc) {
  if (!confirm(`Delete "${doc.filename}"? This cannot be undone.`)) return;
  try {
    await apiFetch(`/documents/${doc.id}`, { method: "DELETE" });
    await loadDocuments();
  } catch (err) {
    errorBox.textContent = err.message;
  }
}
async function showPreview(doc) {
  try {
    const data = await apiFetch(`/documents/${doc.id}/preview?limit=3`);
    document.querySelector("#preview-title").textContent = `${doc.filename} (${data.total_chunks} chunks)`;
    const body = document.querySelector("#preview-body");
    body.replaceChildren();
    for (const chunk of data.chunks) {
      const box = el("div", "chunk");
      box.append(el("div", "meta", `Page ${chunk.page_number} · chunk ${chunk.chunk_index}`));
      box.append(el("pre", "", chunk.content));
      body.append(box);
    }
    dialog.showModal();
  } catch (err) {
    errorBox.textContent = err.message;
  }
}
dropzone.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", () => uploadFiles(fileInput.files));
dropzone.addEventListener("dragover", (e) => { e.preventDefault(); dropzone.classList.add("dragover"); });
dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
dropzone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropzone.classList.remove("dragover");
  uploadFiles(e.dataTransfer.files);
});
document.querySelector("#preview-close").addEventListener("click", () => dialog.close());
let searchTimer;
searchInput.addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(loadDocuments, 300);
});
(async () => {
  const user = await requireAuth();
  if (!user) return;
  renderNav(user, "documents");
  loadDocuments();
})();