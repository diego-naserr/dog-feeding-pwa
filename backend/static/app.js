const API = "/api";
const FALLBACK_COLORS = ["#4f46e5", "#f59e0b", "#16a34a", "#e11d48", "#0891b2", "#9333ea"];
const COLOR_PALETTE = [
  "#4f46e5", "#7c6cf6", "#f59e0b", "#f97316", "#16a34a", "#10b981",
  "#e11d48", "#f43f5e", "#0891b2", "#0ea5e9", "#9333ea", "#ec4899",
];
const WEEKDAY_LABELS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"];

let people = [];        // personas activas (para elegir "quien le dio de comer")
let allPeople = [];      // activas + inactivas (para Ajustes)
let schedule = [];       // [{weekday, person}]
let pendingSchedule = {}; // ediciones sin guardar {weekday: person_id}
let appSettings = { notify_hour: 20, notify_minute: 0 };

let openColorPickerFor = null; // id de persona con el selector de color abierto
let renamingPersonId = null;   // id de persona en edicion de nombre
let selectedNewColor = COLOR_PALETTE[0];

function colorForPerson(person) {
  if (!person) return "#9497ab";
  return person.color || FALLBACK_COLORS[(person.id - 1) % FALLBACK_COLORS.length];
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
  if (!res.ok) {
    let message = res.statusText || "Error de red";
    try {
      const data = await res.json();
      if (data && data.detail) message = data.detail;
    } catch {
      /* respuesta sin JSON, nos quedamos con statusText */
    }
    throw new Error(message);
  }
  if (res.status === 204) return null;
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

function pad2(n) {
  return String(n).padStart(2, "0");
}

let toastTimer = null;
function toast(message, isError) {
  let el = document.getElementById("toast");
  if (!el) {
    el = document.createElement("div");
    el.id = "toast";
    el.className = "toast";
    document.body.appendChild(el);
  }
  el.textContent = message;
  el.className = "toast show" + (isError ? " error" : "");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("show"), 2800);
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

async function checkPushStatus() {
  const badge = document.getElementById("push-status-badge");
  if (!badge) return;

  if (!("Notification" in window) || !("serviceWorker" in window.navigator)) {
    badge.textContent = "No soportado en este navegador";
    badge.className = "push-status unsupported";
    return;
  }
  if (Notification.permission === "denied") {
    badge.textContent = "Bloqueadas — revisá los permisos del navegador";
    badge.className = "push-status blocked";
    return;
  }
  if (Notification.permission !== "granted") {
    badge.textContent = "No activadas todavía";
    badge.className = "push-status inactive";
    return;
  }
  try {
    const reg = await navigator.serviceWorker.getRegistration();
    const sub = reg && (await reg.pushManager.getSubscription());
    if (sub) {
      badge.textContent = "Activadas en este dispositivo ✅";
      badge.className = "push-status active";
    } else {
      badge.textContent = "Permiso dado, falta suscribirse";
      badge.className = "push-status inactive";
    }
  } catch {
    badge.textContent = "No se pudo verificar";
    badge.className = "push-status unsupported";
  }
}

function renderAvatarButtons(container, onClick) {
  container.innerHTML = "";
  people.forEach((p) => {
    const btn = document.createElement("button");
    btn.className = "avatar-chip";
    btn.innerHTML = `
      <span class="avatar-circle" style="background:${colorForPerson(p)}">${initialFor(p.name)}</span>
      <span class="avatar-name">${p.name}</span>
    `;
    btn.onclick = () => onClick(p.name);
    container.appendChild(btn);
  });
}

/**
 * La identidad ("quien soy") se guarda por ID, no por nombre — así sigue
 * siendo válida aunque esa persona se renombre después. `myName` (el
 * nombre) se mantiene siempre actualizado a partir del ID, resuelto
 * contra la lista fresca de personas cada vez que hace falta.
 */
function getMyPersonId() {
  const raw = localStorage.getItem("myPersonId");
  return raw ? parseInt(raw, 10) : null;
}

function getMyPerson() {
  const id = getMyPersonId();
  if (id === null) return null;
  return people.find((p) => p.id === id) || null;
}

/** Migra desde el esquema viejo (solo nombre) la primera vez que carga
 * esta versión en un dispositivo que ya había elegido "quien soy". */
function migrateLegacyIdentity() {
  if (localStorage.getItem("myPersonId")) return;
  const legacyName = localStorage.getItem("myName");
  if (!legacyName) return;
  const match = people.find((p) => p.name === legacyName);
  if (match) localStorage.setItem("myPersonId", String(match.id));
}

function renderWhoAmIRow() {
  const container = document.getElementById("whoami-row");
  if (!container) return;
  const myId = getMyPersonId();
  container.innerHTML = "";
  people.forEach((p) => {
    const btn = document.createElement("button");
    btn.className = "avatar-chip" + (p.id === myId ? " avatar-chip-selected" : "");
    btn.innerHTML = `
      <span class="avatar-circle" style="background:${colorForPerson(p)}">${initialFor(p.name)}</span>
      <span class="avatar-name">${p.name}</span>
    `;
    btn.onclick = () => switchWhoAmI(p);
    container.appendChild(btn);
  });
}

async function switchWhoAmI(person) {
  localStorage.setItem("myPersonId", String(person.id));
  localStorage.setItem("myName", person.name);
  renderWhoAmIRow();
  try {
    await subscribeToPush(person.name);
  } catch (e) {
    toast("No se pudo activar notificaciones: " + e.message, true);
  }
  await checkPushStatus();
  toast(`Ahora sos ${person.name}`);
}

async function loadPeople() {
  people = await fetchJSON(`${API}/people`);
  migrateLegacyIdentity();
  const me = getMyPerson();
  if (me) localStorage.setItem("myName", me.name); // mantiene myName al dia si hubo un rename
  renderAvatarButtons(document.getElementById("person-buttons"), markFed);
  renderWhoAmIRow();
}

async function loadToday() {
  const today = await fetchJSON(`${API}/today`);
  const ring = document.getElementById("status-ring");
  const undoBtn = document.getElementById("undo-btn");

  document.getElementById("assigned-name").textContent = today.assigned_person.name;
  document.getElementById("status-initial").textContent = initialFor(today.assigned_person.name);

  if (today.fed) {
    ring.className = "status-ring fed";
    document.getElementById("status-badge").textContent = "✅";
    document.getElementById("status-text").textContent =
      `${today.fed_by.name} marcó a las ${formatTime(today.fed_at)}`;
    undoBtn.style.display = "inline-block";
  } else {
    ring.className = "status-ring pending";
    document.getElementById("status-badge").textContent = "⏳";
    document.getElementById("status-text").textContent = "Todavía no le han dado comida";
    undoBtn.style.display = "none";
  }
}

async function markFed(personName) {
  try {
    await fetchJSON(`${API}/feed`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ person_name: personName }),
    });
    await loadToday();
    await loadHistory();
  } catch (e) {
    toast(e.message, true);
  }
}

async function undoFed() {
  try {
    await fetchJSON(`${API}/feed`, { method: "DELETE" });
    await loadToday();
    await loadHistory();
    toast("Deshecho");
  } catch (e) {
    toast(e.message, true);
  }
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
    const color = colorForPerson(person);

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
  document.getElementById("view-settings").style.display = tab === "settings" ? "block" : "none";
  document.getElementById("tab-today").classList.toggle("active", tab === "today");
  document.getElementById("tab-history").classList.toggle("active", tab === "history");
  document.getElementById("tab-settings").classList.toggle("active", tab === "settings");

  if (tab === "settings") {
    loadSettingsTab();
  }
}

function initTabs() {
  document.getElementById("tab-today").onclick = () => showTab("today");
  document.getElementById("tab-history").onclick = () => showTab("history");
  document.getElementById("tab-settings").onclick = () => showTab("settings");
}

// ==================== AJUSTES: Personas ====================

function renderColorSwatches(container, selected, onPick) {
  container.innerHTML = "";
  COLOR_PALETTE.forEach((color) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "color-swatch" + (color === selected ? " color-swatch-selected" : "");
    btn.style.background = color;
    btn.onclick = () => onPick(color);
    container.appendChild(btn);
  });
}

function renderPeopleList() {
  const list = document.getElementById("people-list");
  if (!list) return;
  list.innerHTML = "";

  allPeople.forEach((p) => {
    const li = document.createElement("li");
    li.className = "person-row" + (p.active ? "" : " person-inactive");

    const isRenaming = renamingPersonId === p.id;
    const nameHtml = isRenaming
      ? `<input type="text" class="text-input person-rename-input" id="rename-input-${p.id}" value="${p.name}" maxlength="40" />`
      : `<span class="person-name">${p.name}${p.active ? "" : " (inactiva)"}</span>`;

    li.innerHTML = `
      <button class="avatar-circle small person-color-btn" style="background:${colorForPerson(p)}">${initialFor(p.name)}</button>
      ${nameHtml}
      <span class="person-actions">
        ${isRenaming
          ? `<button class="icon-btn confirm-rename" title="Guardar">✓</button>`
          : `<button class="icon-btn rename-btn" title="Renombrar">✏️</button>`}
        ${p.active
          ? `<button class="icon-btn deactivate-btn" title="Desactivar">🗑️</button>`
          : `<button class="icon-btn reactivate-btn" title="Reactivar">↩️</button>`}
      </span>
    `;

    li.querySelector(".person-color-btn").onclick = () => {
      openColorPickerFor = openColorPickerFor === p.id ? null : p.id;
      renderPeopleList();
    };

    if (isRenaming) {
      li.querySelector(".confirm-rename").onclick = () => {
        const input = document.getElementById(`rename-input-${p.id}`);
        confirmRename(p.id, input.value);
      };
    } else {
      li.querySelector(".rename-btn").onclick = () => {
        renamingPersonId = p.id;
        renderPeopleList();
      };
    }

    if (p.active) {
      li.querySelector(".deactivate-btn").onclick = () => deactivatePerson(p);
    } else {
      li.querySelector(".reactivate-btn").onclick = () => reactivatePerson(p);
    }

    list.appendChild(li);

    if (openColorPickerFor === p.id) {
      const swatchLi = document.createElement("li");
      swatchLi.className = "person-color-picker-row";
      list.appendChild(swatchLi);
      renderColorSwatches(swatchLi, p.color, (color) => setPersonColor(p, color));
    }
  });
}

async function refreshPeopleData() {
  allPeople = await fetchJSON(`${API}/people?include_inactive=true`);
  await loadPeople(); // recarga la lista de activos usada en el resto de la app
  renderPeopleList();
}

async function setPersonColor(person, color) {
  try {
    await fetchJSON(`${API}/people/${person.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ color }),
    });
    openColorPickerFor = null;
    await refreshPeopleData();
    toast("Color actualizado");
  } catch (e) {
    toast(e.message, true);
  }
}

async function confirmRename(personId, newName) {
  const trimmed = newName.trim();
  if (!trimmed) {
    toast("El nombre no puede estar vacío", true);
    return;
  }
  try {
    await fetchJSON(`${API}/people/${personId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: trimmed }),
    });
    renamingPersonId = null;
    await refreshPeopleData();
    toast("Nombre actualizado");
  } catch (e) {
    toast(e.message, true);
  }
}

async function deactivatePerson(person) {
  if (!confirm(`¿Desactivar a ${person.name}? Su historial se conserva.`)) return;
  try {
    await fetchJSON(`${API}/people/${person.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ active: false }),
    });
    await refreshPeopleData();
    toast(`${person.name} desactivada`);
  } catch (e) {
    toast(e.message, true);
  }
}

async function reactivatePerson(person) {
  try {
    await fetchJSON(`${API}/people/${person.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ active: true }),
    });
    await refreshPeopleData();
    toast(`${person.name} reactivada`);
  } catch (e) {
    toast(e.message, true);
  }
}

async function addPerson() {
  const input = document.getElementById("new-person-name");
  const name = input.value.trim();
  if (!name) {
    toast("Escribí un nombre", true);
    return;
  }
  try {
    await fetchJSON(`${API}/people`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, color: selectedNewColor }),
    });
    input.value = "";
    await refreshPeopleData();
    toast(`${name} agregada`);
  } catch (e) {
    toast(e.message, true);
  }
}

// ==================== AJUSTES: Rotación semanal ====================

function renderScheduleRows() {
  const container = document.getElementById("schedule-rows");
  if (!container) return;
  container.innerHTML = "";

  for (let weekday = 0; weekday < 7; weekday++) {
    const entry = schedule.find((s) => s.weekday === weekday);
    const currentPersonId = pendingSchedule[weekday] ?? entry?.person.id;

    const row = document.createElement("div");
    row.className = "schedule-row";
    const select = document.createElement("select");
    select.className = "schedule-select";
    people.forEach((p) => {
      const opt = document.createElement("option");
      opt.value = p.id;
      opt.textContent = p.name;
      opt.selected = p.id === currentPersonId;
      select.appendChild(opt);
    });
    select.onchange = () => {
      pendingSchedule[weekday] = parseInt(select.value, 10);
    };

    const label = document.createElement("span");
    label.className = "schedule-day-label";
    label.textContent = WEEKDAY_LABELS[weekday];

    row.appendChild(label);
    row.appendChild(select);
    container.appendChild(row);
  }
}

async function loadSchedule() {
  schedule = await fetchJSON(`${API}/schedule`);
  pendingSchedule = {};
  renderScheduleRows();
}

async function saveSchedule() {
  const items = [];
  for (let weekday = 0; weekday < 7; weekday++) {
    const entry = schedule.find((s) => s.weekday === weekday);
    const personId = pendingSchedule[weekday] ?? entry?.person.id;
    items.push({ weekday, person_id: personId });
  }
  try {
    schedule = await fetchJSON(`${API}/schedule`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(items),
    });
    pendingSchedule = {};
    renderScheduleRows();
    await loadToday();
    toast("Rotación guardada");
  } catch (e) {
    toast(e.message, true);
  }
}

// ==================== AJUSTES: Hora del aviso ====================

async function loadSettings() {
  appSettings = await fetchJSON(`${API}/settings`);
  const input = document.getElementById("notify-time-input");
  if (input) {
    input.value = `${pad2(appSettings.notify_hour)}:${pad2(appSettings.notify_minute)}`;
  }
}

async function saveSettings() {
  const input = document.getElementById("notify-time-input");
  const [hour, minute] = input.value.split(":").map((n) => parseInt(n, 10));
  if (Number.isNaN(hour) || Number.isNaN(minute)) {
    toast("Elegí una hora válida", true);
    return;
  }
  try {
    appSettings = await fetchJSON(`${API}/settings`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ notify_hour: hour, notify_minute: minute }),
    });
    toast("Hora del aviso guardada");
  } catch (e) {
    toast(e.message, true);
  }
}

async function testPush() {
  const me = getMyPerson();
  if (!me) {
    toast("Primero elegí quién sos", true);
    return;
  }
  try {
    const res = await fetchJSON(`${API}/test-push`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ person_name: me.name }),
    });
    toast(res.message, res.sent === 0);
  } catch (e) {
    toast(e.message, true);
  }
}

function renderNewPersonColorPicker() {
  renderColorSwatches(document.getElementById("new-person-colors"), selectedNewColor, (color) => {
    selectedNewColor = color;
    renderNewPersonColorPicker();
  });
}

async function loadSettingsTab() {
  renderNewPersonColorPicker();
  await checkPushStatus();
  try {
    await refreshPeopleData();
    await loadSchedule();
    await loadSettings();
  } catch (e) {
    toast(e.message, true);
  }
}

function initSettingsHandlers() {
  document.getElementById("undo-btn").onclick = undoFed;
  document.getElementById("add-person-btn").onclick = addPerson;
  document.getElementById("save-schedule-btn").onclick = saveSchedule;
  document.getElementById("save-time-btn").onclick = saveSettings;
  document.getElementById("test-push-btn").onclick = testPush;
}

function initWhoModal() {
  document.getElementById("who-modal-skip").onclick = () => {
    document.getElementById("who-modal").style.display = "none";
  };
}

async function init() {
  initTabs();
  initWhoModal();
  initSettingsHandlers();
  showTab("today");

  await loadPeople();
  await loadToday();
  await loadHistory();

  const me = getMyPerson();
  if (!me) {
    document.getElementById("who-modal-buttons").innerHTML = "";
    renderAvatarButtons(document.getElementById("who-modal-buttons"), (name) => {
      const person = personByName(name);
      if (person) {
        localStorage.setItem("myPersonId", String(person.id));
        localStorage.setItem("myName", person.name);
      }
      document.getElementById("who-modal").style.display = "none";
      subscribeToPush(name).catch((e) => console.error(e));
    });
    setTimeout(() => {
      document.getElementById("who-modal").style.display = "flex";
    }, 600);
  } else {
    subscribeToPush(me.name).catch((e) => console.error(e));
  }
}

document.addEventListener("DOMContentLoaded", init);
