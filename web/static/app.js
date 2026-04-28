function $(id) {
  return document.getElementById(id);
}

const LS_KEY = "day12_chat_ui_settings_v1";

function getBaseUrl() {
  const v = $("baseUrl").value.trim();
  if (v) return v.replace(/\/+$/, "");
  return window.location.origin;
}

function getHeaders() {
  const apiKey = $("apiKey").value.trim();
  const openaiKey = $("openaiKey")?.value?.trim?.() || "";
  const headers = { "Content-Type": "application/json" };
  if (apiKey) headers["X-API-Key"] = apiKey;
  if (openaiKey) headers["X-OpenAI-Key"] = openaiKey;
  return headers;
}

function setStatus(text) {
  $("statusLine").textContent = text;
}

function appendOutput(obj) {
  const out = $("output");
  const chunk = typeof obj === "string" ? obj : JSON.stringify(obj, null, 2);
  out.textContent = (out.textContent ? out.textContent + "\n\n" : "") + chunk;
  out.scrollTop = out.scrollHeight;
}

function appendChat(role, text) {
  const log = $("chatLog");
  const wrap = document.createElement("div");
  wrap.className = "msg " + (role === "user" ? "user" : "assistant");
  const meta = document.createElement("div");
  meta.className = "meta";
  meta.textContent = role === "user" ? "You" : "Assistant";
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;
  wrap.appendChild(meta);
  wrap.appendChild(bubble);
  log.appendChild(wrap);
  log.scrollTop = log.scrollHeight;
}

async function callJson(method, path, body) {
  const base = getBaseUrl();
  const url = base + path;
  setStatus(`${method} ${url} ...`);

  const opts = { method, headers: getHeaders() };
  if (body) opts.body = JSON.stringify(body);

  const res = await fetch(url, opts);
  const text = await res.text();
  let parsed = null;
  try {
    parsed = text ? JSON.parse(text) : null;
  } catch {
    parsed = text;
  }
  appendOutput({
    request: { method, url, body: body || null },
    response: { status: res.status, body: parsed },
  });
  setStatus(`Done: ${res.status}`);
  return { status: res.status, body: parsed };
}

async function doHealth() {
  try {
    await callJson("GET", "/health");
  } catch (e) {
    appendOutput(String(e));
    setStatus("Error");
  }
}

async function doReady() {
  try {
    await callJson("GET", "/ready");
  } catch (e) {
    appendOutput(String(e));
    setStatus("Error");
  }
}

async function doAsk() {
  const user_id = $("userId").value.trim();
  const question = $("question").value.trim();
  if (!user_id || !question) {
    setStatus("Missing user_id or question");
    return;
  }
  appendChat("user", question);
  $("question").value = "";
  try {
    const { status, body } = await callJson("POST", "/ask", { user_id, question });
    if (status >= 200 && status < 300 && body?.answer) {
      appendChat("assistant", body.answer);
    } else {
      appendChat("assistant", `Error (${status}): ${typeof body === "string" ? body : JSON.stringify(body)}`);
    }
  } catch (e) {
    appendOutput(String(e));
    appendChat("assistant", String(e));
    setStatus("Error");
  }
}

function toggleSettings(open) {
  const panel = $("settingsPanel");
  panel.classList.toggle("open", open);
}

function saveSettings() {
  const data = {
    baseUrl: $("baseUrl").value.trim(),
    apiKey: $("apiKey").value.trim(),
    openaiKey: $("openaiKey").value.trim(),
    userId: $("userId").value.trim(),
  };
  localStorage.setItem(LS_KEY, JSON.stringify(data));
  setStatus("Saved settings.");
}

function loadSettings() {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return;
    const data = JSON.parse(raw);
    if (typeof data.baseUrl === "string") $("baseUrl").value = data.baseUrl;
    if (typeof data.apiKey === "string") $("apiKey").value = data.apiKey;
    if (typeof data.openaiKey === "string") $("openaiKey").value = data.openaiKey;
    if (typeof data.userId === "string") $("userId").value = data.userId || "test";
  } catch {
    // ignore
  }
}

function resetSettings() {
  localStorage.removeItem(LS_KEY);
  $("baseUrl").value = "";
  $("apiKey").value = "";
  $("openaiKey").value = "";
  $("userId").value = "test";
  setStatus("Reset settings.");
}

function init() {
  loadSettings();
  toggleSettings(false);

  $("btnHealth").addEventListener("click", doHealth);
  $("btnReady").addEventListener("click", doReady);
  $("btnAsk").addEventListener("click", doAsk);
  $("btnClear").addEventListener("click", () => {
    $("output").textContent = "";
    $("chatLog").textContent = "";
    setStatus("Cleared chat.");
  });

  $("btnSettings").addEventListener("click", () => toggleSettings(true));
  $("btnCloseSettings").addEventListener("click", () => toggleSettings(false));
  $("btnSave").addEventListener("click", () => {
    saveSettings();
    toggleSettings(false);
  });
  $("btnReset").addEventListener("click", resetSettings);

  $("question").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      doAsk();
    }
  });
}

init();

