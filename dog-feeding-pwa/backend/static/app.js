const API = "/api";
const AVATAR_COLORS = ["#4f46e5", "#f59e0b", "#16a34a", "#e11d48", "#0891b2", "#9333ea"];

let people = [];

function colorFor(personId) {
  return AVATAR_COLORS[(personId - 1) % AVATAR_COLORS.length];
}

function initialFor(name) {
  return name.trim().charAt(0).toUpperCase();
}

function urlBase64ToUint8Array(base64String) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const rawData = atob(base64);
  return Uint8Array.from([...rawData].map((c) => c.charCodeAt(0)));
}

async function fetchJSON(url, opts) {
  const res = await fetch(url, opts);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

function formatTime(iso) {
  const d = new Date(iso);
  return d.toLocaleTimeString("es-CL", { hour: "2-digit", minute: "2-digit" });
}

function formatDate(dateStr) {
  const d = new Date(`${dateStr}T00:00:00`);
  return d.toLocaleDateString("es-CL", { weekday: "short", day: "numeric", month: "short" });
}

async function registerServiceWorker() {
  if (!("serviceWorker" in navigator)) return null;
  return navigator.serviceWorker.register("/sw.js");
}

async function subscribeToPush(personName) {
  if (!("Notification" in window) || !("PushManager" in window)) return;

  const permission = await Notification.requestPermission();
  if (permission !== "granted") return;

  const reg = await registerServiceWorker();
  if (!reg) return;

  const { publicKey } = await fetchJSON(`${API}/vapid-public-key`);
  let sub = await reg.pushManager.getSubscription();
  if (!sub) {
    sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(publicKey),
    });
  }

  const json = sub.toJSON();
  await fetchJSON(`${API}/subscribe`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      person_name: personName,
      endpoint: json.endpoint,
      keys: json.keys,
    }),
  });
}

function renderAvatarButtons(container, onClick) {
  container.innerHTML = "";
  people.forEach((p) => {
    const btn = document.createElement("button");
    btn.className = "avatar-chip";
    btn.innerHTML = `
      <span class="avatar-circle" style="background:${colorFor(p.id)}">${initialFor(p.name)}</span>
      <span class="avatar-name">${p.name}</span>
    `;
    btn.onclick = () => onClick(p.name);
    container.appendChild(btn);
  });
}

async function loadPeople() {
  people = await fetchJSON(`${API}/people`);
  renderAvatarButtons(document.getElementById("person-buttons"), markFed);
  renderAvatarButtons(document.getElementById("who-modal-buttons"), chooseWhoAmI);
}

async function loadToday() {
  const today = await fetchJSON(`${API}/today`);
  const ring = document.getElementById("status-ring");

  document.getElementById("assigned-name").textContent = today.assigned_person.name;
  document.getElementById("status-initial").textContent = initialFor(today.assigned_person.name);

  if (today.fed) {
    ring.className = "status-ring fed";
    document.getElementById("status-badge").textContent = "✅";
    document.getElementById("status-text").textContent =
      `${today.fed_by.name} marcó a las ${formatTime(today.fed_at)}`;
  } else {
    ring.className = "status-ring pending";
    document.getElementById("status-badge").textContent = "⏳";
    document.getElementById("status-text").textContent = "Todavía no le han dado comida";
  }
}

async function markFed(personName) {
  await fetchJSON(`${API}/feed`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ person_name: personName }),
  });
  await loadToday();
  await loadHistory();
}

function personByName(name) {
  return people.find((p) => p.name === name);
}

async function loadHistory() {
  const history = await fetchJSON(`${API}/history?days=30`);
  const list = document.getElementById("history-list");
  const todayStr = new Date().toISOString().slice(0, 10);
  list.innerHTML = "";

  history.forEach((item) => {
    const li = document.createElement("li");
    li.className = "history-item";

    const avatarName = item.fed ? item.fed_by : item.assigned_person;
    const person = personByName(avatarName);
    const color = person ? colorFor(person.id) : "#9497ab";

    let pillClass = "missed";
    let pillText = "Sin marcar";
    let secondLine = "";

    if (item.fed) {
      pillClass = item.on_time ? "on-time" : "late";
      pillText = item.on_time ? "A tiempo" : "Tarde";
      secondLine = `<p class="history-sub">Dio de comer: ${item.fed_by} · ${formatTime(item.fed_at)}</p>`;
    } else if (item.date >= todayStr) {
      pillClass = "late";
      pillText = "Pendiente";
    }

    li.innerHTML = `
      <span class="history-avatar" style="background:${color}">${initialFor(avatarName)}</span>
      <span class="history-body">
        <p class="history-title">${formatDate(item.date)}</p>
        <p class="history-sub">Le tocaba: ${item.assigned_person}</p>
        ${secondLine}
      </span>
      <span class="history-pill ${pillClass}">${pillText}</span>
    `;
    list.appendChild(li);
  });
}

function showTab(tab) {
  document.getElementById("view-today").style.display = tab === "today" ? "block" : "none";
  document.getElementById("view-history").style.display = tab === "history" ? "block" : "none";
  document.getElementById("tab-today").classList.toggle("active", tab === "today");
  document.getElementById("tab-history").classList.toggle("active", tab === "history");
}

function chooseWhoAmI(name) {
  localStorage.setItem("myName", name);
  document.getElementById("who-modal").style.display = "none";
  subscribeToPush(name);
}

function initTabs() {
  document.getElementById("tab-today").onclick = () => showTab("today");
  document.getElementById("tab-history").onclick = () => showTab("history");
}

function initWhoModal() {
  document.getElementById("who-modal-skip").onclick = () => {
    document.getElementById("who-modal").style.display = "none";
  };
}

async function init() {
  initTabs();
  initWhoModal();
  showTab("today");

  await loadPeople();
  await loadToday();
  await loadHistory();

  const myName = localStorage.getItem("myName");
  if (!myName) {
    setTimeout(() => {
      document.getElementById("who-modal").style.display = "flex";
    }, 600);
  } else {
    subscribeToPush(myName);
  }
}

document.addEventListener("DOMContentLoaded", init);
