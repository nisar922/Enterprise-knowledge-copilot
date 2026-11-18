const messagesBox = document.querySelector("#messages");
const form = document.querySelector("#chat-form");
const questionInput = document.querySelector("#question");
const sendBtn = document.querySelector("#send-btn");
const convList = document.querySelector("#conv-list");
let currentConversationId = null;
let busy = false;
function renderMarkdown(text) {
  return DOMPurify.sanitize(marked.parse(text, { breaks: true }));
}
function scrollToBottom() {
  messagesBox.scrollTop = messagesBox.scrollHeight;
}
function showEmptyHint() {
  messagesBox.replaceChildren(el("div", "empty-hint", "Ask anything about your uploaded documents."));
}
function addMessage(role, text) {
  const row = el("div", `msg msg-${role}`);
  const bubble = el("div", "bubble");
  const content = el("div", role === "assistant" ? "md" : "");
  if (role === "user") content.textContent = text;
  else if (text) content.innerHTML = renderMarkdown(text);
  bubble.append(content);
  row.append(bubble);
  messagesBox.append(row);
  scrollToBottom();
  return { bubble, content };
}
function renderSources(bubble, sources) {
  if (!sources || sources.length === 0) return;
  const wrap = el("div", "sources");
  wrap.append(el("div", "sources-title", "Sources"));
  sources.forEach((s, i) => {
    const details = document.createElement("details");
    const label = `[${s.ref || i + 1}] ${s.filename} · page ${s.page_number ?? "-"} · relevance ${s.relevance}`;
    details.append(el("summary", "", label), el("pre", "", s.text));
    wrap.append(details);
  });
  bubble.append(wrap);
}
function renderMeta(bubble, info) {
  const tokens = info.prompt_tokens + info.completion_tokens;
  const text = `${info.latency_ms} ms · ${tokens} tokens · searched for: ${info.rewritten_query}`;
  bubble.append(el("div", "meta-line", text));
}
async function loadConversations() {
  try {
    const chats = await apiFetch("/chat/conversations");
    convList.replaceChildren();
    for (const chat of chats) {
      const li = el("li", "conv-item" + (chat.conversation_id === currentConversationId ? " active" : ""));
      const title = el("button", "title", chat.title);
      title.type = "button";
      title.title = chat.title;
      title.addEventListener("click", () => openConversation(chat.conversation_id));
      const del = el("button", "del", "×");
      del.type = "button";
      del.title = "Delete chat";
      del.addEventListener("click", () => deleteConversation(chat.conversation_id));
      li.append(title, del);
      convList.append(li);
    }
  } catch (err) {
    console.error(err);
  }
}
async function openConversation(id) {
  if (busy) return;
  try {
    const messages = await apiFetch(`/chat/conversations/${id}`);
    currentConversationId = id;
    messagesBox.replaceChildren();
    for (const m of messages) {
      addMessage("user", m.question);
      const { bubble } = addMessage("assistant", m.answer);
      renderSources(bubble, m.sources);
    }
    scrollToBottom();
    loadConversations();
  } catch (err) {
    alert(err.message);
  }
}
async function deleteConversation(id) {
  if (busy || !confirm("Delete this chat?")) return;
  try {
    await apiFetch(`/chat/conversations/${id}`, { method: "DELETE" });
    if (id === currentConversationId) newChat();
    loadConversations();
  } catch (err) {
    alert(err.message);
  }
}
function newChat() {
  if (busy) return;
  currentConversationId = null;
  showEmptyHint();
  loadConversations();
  questionInput.focus();
}
async function streamChat(question, handlers) {
  const res = await fetch("/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${getToken()}` },
    body: JSON.stringify({ question, conversation_id: currentConversationId }),
  });
  if (res.status === 401) {
    logout();
    return;
  }
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const data = await res.json();
      if (typeof data.detail === "string") detail = data.detail;
    } catch (_) {}
    throw new Error(detail);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split("\n\n");
    buffer = events.pop();
    for (const raw of events) {
      let event = "message";
      let data = "";
      for (const line of raw.split("\n")) {
        if (line.startsWith("event: ")) event = line.slice(7);
        else if (line.startsWith("data: ")) data += line.slice(6);
      }
      if (data && handlers[event]) handlers[event](JSON.parse(data));
    }
  }
}
async function sendQuestion(question) {
  busy = true;
  sendBtn.disabled = true;
  questionInput.disabled = true;
  if (messagesBox.querySelector(".empty-hint")) messagesBox.replaceChildren();
  addMessage("user", question);
  const { bubble, content } = addMessage("assistant", "");
  content.textContent = "Thinking...";
  let fullText = "";
  let renderQueued = false;
  const scheduleRender = () => {
    if (renderQueued) return;
    renderQueued = true;
    requestAnimationFrame(() => {
      renderQueued = false;
      content.innerHTML = renderMarkdown(fullText);
      scrollToBottom();
    });
  };
  try {
    await streamChat(question, {
      meta: (d) => { currentConversationId = d.conversation_id; },
      token: (d) => { fullText += d.text; scheduleRender(); },
      done: (d) => {
        content.innerHTML = renderMarkdown(fullText);
        renderSources(bubble, d.sources);
        renderMeta(bubble, d);
        scrollToBottom();
      },
      error: (d) => { content.textContent = `Error: ${d.detail}`; },
    });
  } catch (err) {
    content.textContent = `Error: ${err.message}`;
  } finally {
    busy = false;
    sendBtn.disabled = false;
    questionInput.disabled = false;
    questionInput.focus();
    loadConversations();
  }
}
form.addEventListener("submit", (e) => {
  e.preventDefault();
  const question = questionInput.value.trim();
  if (!question || busy) return;
  questionInput.value = "";
  questionInput.style.height = "auto";
  sendQuestion(question);
});
questionInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    form.requestSubmit();
  }
});
questionInput.addEventListener("input", () => {
  questionInput.style.height = "auto";
  questionInput.style.height = Math.min(questionInput.scrollHeight, 140) + "px";
});
document.querySelector("#new-chat").addEventListener("click", newChat);
(async () => {
  const user = await requireAuth();
  if (!user) return;
  renderNav(user, "chat");
  showEmptyHint();
  loadConversations();
})();