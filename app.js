/* Layer 6 - Presentation logic. Talks to the JSON API only. */
const CSRF = document.querySelector('meta[name=csrf]').content;
const CUR = document.body.dataset.currency;
const $ = (s, r = document) => r.querySelector(s);

async function api(path, { method = "GET", json, body } = {}) {
  const headers = { "X-CSRF-Token": CSRF };
  if (json !== undefined) { headers["Content-Type"] = "application/json"; body = JSON.stringify(json); }
  const res = await fetch(path, { method, headers, body, credentials: "same-origin" });
  let data = null;
  try { data = await res.json(); } catch (_) {}
  if (!res.ok) throw new Error((data && data.error) || "Something went wrong");
  return data;
}
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const getPos = () => new Promise((ok, no) => {
  if (!navigator.geolocation) return no(new Error("Geolocation not supported"));
  navigator.geolocation.getCurrentPosition((p) => ok({ lat: p.coords.latitude, lng: p.coords.longitude }), no, { timeout: 10000, enableHighAccuracy: true });
});
const LABEL = { PENDING_PAYMENT: "Awaiting payment", ESCROW_HELD: "Paid - held in escrow", SHIPPED: "Shipped", DISPUTED: "In dispute (funds frozen)", COMPLETED: "Completed - funds released", REFUNDED: "Refunded", CANCELLED: "Cancelled" };

/* ---- shared ---- */
const lo = $("#logout");
if (lo) lo.addEventListener("click", async (e) => { e.preventDefault(); await api("/api/auth/logout", { method: "POST" }); location.href = "/"; });

/* ---- login / signup ---- */
function authForm(id, url) {
  const f = $(id); if (!f) return;
  f.addEventListener("submit", async (e) => {
    e.preventDefault(); $("#msg").textContent = "";
    try {
      await api(url, { method: "POST", json: Object.fromEntries(new FormData(f)) });
      const next = new URLSearchParams(location.search).get("next");
      location.href = next && next.startsWith("/") && !next.startsWith("//") ? next : "/";
    } catch (err) { $("#msg").textContent = err.message; }
  });
}
authForm("#login-form", "/api/auth/login");
authForm("#signup-form", "/api/auth/signup");

/* ---- explore ---- */
function tile(i) {
  const dist = i.distance_km !== undefined ? ` · ${i.distance_km} km away` : "";
  const img = i.image ? `<img src="${esc(i.image)}" alt="">` : `<div class="ph">No photo</div>`;
  return `<a class="tile" href="/items/${esc(i.id)}">${img}<div class="b"><div>${esc(i.title)}</div>
    <div class="price">${esc(i.currency)} ${esc(i.price)}</div>
    <div class="muted">${esc(i.category)}${dist}</div><div class="muted">ID ${esc(i.id)}</div></div></a>`;
}
if (document.body.dataset.page === "explore") {
  let coords = null;
  const grid = $("#grid"), note = $("#geo-note");
  async function load() {
    const p = new URLSearchParams();
    if (coords) { p.set("lat", coords.lat); p.set("lng", coords.lng); if ($("#radius").value) p.set("radius", $("#radius").value); }
    if ($("#q").value.trim()) p.set("q", $("#q").value.trim());
    if ($("#category").value) p.set("category", $("#category").value);
    try {
      const items = await api("/api/items?" + p);
      grid.innerHTML = items.length ? items.map(tile).join("") : `<p class="muted">No items found. Try a wider radius.</p>`;
    } catch (err) { grid.innerHTML = `<p class="error">${esc(err.message)}</p>`; }
  }
  async function locate() {
    note.textContent = "Finding your location…";
    try { coords = await getPos(); note.textContent = "Showing items closest to you first."; }
    catch (_) { coords = null; note.textContent = "Location unavailable (allow location access in your browser). Showing all items."; }
    load();
  }
  $("#search").addEventListener("click", load);
  $("#locate").addEventListener("click", locate);
  $("#radius").addEventListener("change", load);
  $("#q").addEventListener("keydown", (e) => e.key === "Enter" && load());
  locate();
}

/* ---- sell ---- */
if (document.body.dataset.page === "sell") {
  const f = $("#sell-form");
  async function setLoc() {
    $("#loc-status").textContent = "Getting location…";
    try {
      const c = await getPos();
      f.lat.value = c.lat; f.lng.value = c.lng;
      $("#loc-status").textContent = `Location set (${c.lat.toFixed(4)}, ${c.lng.toFixed(4)})`;
    } catch (_) { $("#loc-status").textContent = "Could not get location. Allow location access and try again."; }
  }
  $("#get-loc").addEventListener("click", setLoc);
  setLoc();
  f.addEventListener("submit", async (e) => {
    e.preventDefault(); $("#msg").textContent = "";
    try {
      const item = await api("/api/items", { method: "POST", body: new FormData(f) });
      location.href = "/items/" + item.id;
    } catch (err) { $("#msg").textContent = err.message; }
  });
}

/* ---- item detail ---- */
if (document.body.dataset.page === "item") {
  const box = $("#item");
  (async () => {
    let q = "";
    try { const c = await getPos(); q = `?lat=${c.lat}&lng=${c.lng}`; } catch (_) {}
    try {
      const i = await api(`/api/items/${encodeURIComponent(box.dataset.itemId)}${q}`);
      const dist = i.distance_km !== undefined ? `<p>${i.distance_km} km from you</p>` : "";
      const map = `https://www.openstreetmap.org/?mlat=${i.lat}&mlon=${i.lng}#map=16/${i.lat}/${i.lng}`;
      box.innerHTML = `<div class="detail">
        <div>${i.image ? `<img src="${esc(i.image)}" alt="">` : `<div class="ph">No photo</div>`}</div>
        <div><h1>${esc(i.title)}</h1><p class="price">${esc(i.currency)} ${esc(i.price)}</p>
          <p>${esc(i.description)}</p>${dist}
          <p class="muted">Item ID: ${esc(i.id)}<br>Seller: ${esc(i.seller_name)}<br>Pickup: ${esc(i.address || "see map")} · <a href="${map}" target="_blank" rel="noopener">map</a></p>
          <p class="muted">Pay now - your money is held in escrow and only released to the seller after you confirm you received the item.</p>
          <p class="error" id="msg"></p>
          ${i.status === "ACTIVE" ? `<button class="btn" id="buy">Buy with escrow</button>` : `<span class="badge">${esc(i.status)}</span>`}
        </div></div>`;
      const buy = $("#buy");
      if (buy) buy.addEventListener("click", async () => {
        buy.disabled = true; $("#msg").textContent = "";
        try {
          const r = await api("/api/orders/checkout", { method: "POST", json: { item_id: i.id } });
          location.href = r.checkout_url;
        } catch (err) {
          buy.disabled = false;
          if (err.message === "Please log in") location.href = "/login?next=" + encodeURIComponent(location.pathname);
          else $("#msg").textContent = err.message;
        }
      });
    } catch (err) { box.innerHTML = `<p class="error">${esc(err.message)}</p>`; }
  })();
}

/* ---- orders ---- */
function orderCard(o, role) {
  const acts = [];
  if (role === "buying") {
    if (o.status === "PENDING_PAYMENT") acts.push(["cancel", "Cancel", "ghost"]);
    if (o.status === "ESCROW_HELD" || o.status === "SHIPPED") acts.push(["confirm-received", "I received the item - release payment", ""]);
    if (o.status === "ESCROW_HELD") acts.push(["refund", "Cancel & refund", "ghost"]);
    if (o.status === "SHIPPED") acts.push(["dispute", "Report a problem", "danger"]);
  } else {
    if (o.status === "ESCROW_HELD") acts.push(["ship", "Mark as shipped", ""]);
    if (o.status === "ESCROW_HELD" || o.status === "SHIPPED") acts.push(["refund", "Cancel & refund buyer", "ghost"]);
  }
  const who = role === "buying" ? `Seller: ${esc(o.seller_name)}` : `Buyer: ${esc(o.buyer_name)}`;
  const amt = role === "selling" ? ` (you receive ${o.currency} ${esc(o.seller_receives)})` : "";
  return `<div class="card row" data-id="${esc(o.id)}" data-role="${role}">
    ${o.item_image ? `<img src="${esc(o.item_image)}" alt="">` : ""}
    <div style="flex:1"><strong>${esc(o.item_title)}</strong>
      <div class="muted">Order ${esc(o.id)} · ${who}</div>
      <div>${o.currency} ${esc(o.amount)}${amt}</div>
      <span class="badge ${o.status}">${LABEL[o.status] || o.status}</span>
      <div class="error"></div>
      <div>${acts.map(([a, t, c]) => `<button class="btn ${c}" data-act="${a}">${t}</button>`).join(" ")}</div>
    </div></div>`;
}
if (document.body.dataset.page === "orders") {
  async function render() {
    const [w, buy, sell, mine] = await Promise.all([api("/api/wallet"), api("/api/orders?role=buying"), api("/api/orders?role=selling"), api("/api/items/mine")]);
    $("#wallet").innerHTML = `<strong>Seller balance:</strong> ${esc(w.currency)} ${esc(w.balance)} <span class="muted">(released from completed sales)</span>`;
    $("#buying").innerHTML = buy.map((o) => orderCard(o, "buying")).join("") || `<p class="muted">No purchases yet.</p>`;
    $("#selling").innerHTML = sell.map((o) => orderCard(o, "selling")).join("") || `<p class="muted">No sales yet.</p>`;
    $("#listings").innerHTML = mine.map((i) => `<div class="card row" data-item="${esc(i.id)}"><div style="flex:1"><strong>${esc(i.title)}</strong>
      <div class="muted">${esc(i.id)} · ${esc(i.currency)} ${esc(i.price)} · ${esc(i.status)}</div><div class="error"></div></div>
      ${i.status === "ACTIVE" ? `<button class="btn ghost" data-remove="1">Remove</button>` : ""}</div>`).join("") || `<p class="muted">You have no listings.</p>`;
  }
  document.addEventListener("click", async (e) => {
    const b = e.target.closest("button[data-act],button[data-remove]"); if (!b) return;
    const card = b.closest(".card"), err = $(".error", card);
    err.textContent = ""; b.disabled = true;
    try {
      if (b.dataset.remove) await api(`/api/items/${card.dataset.item}`, { method: "DELETE" });
      else {
        if (b.dataset.act === "confirm-received" && !confirm("Only confirm if you have the item in hand. This releases the money to the seller and cannot be undone.")) { b.disabled = false; return; }
        await api(`/api/orders/${card.dataset.id}/${b.dataset.act}`, { method: "POST" });
      }
      render();
    } catch (ex) { err.textContent = ex.message; b.disabled = false; }
  });
  render();
}
