"use strict";

/* ===== helpers ===== */
const $ = s => document.querySelector(s);
const pad = n => String(n).padStart(2, "0");
const keyOf = d => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
const fromKey = k => { const [a, b, c] = k.split("-").map(Number); return new Date(a, b - 1, c); };
const today = () => { const d = new Date(); d.setHours(0, 0, 0, 0); return d; };
const addDays = (d, n) => { const x = new Date(d); x.setDate(x.getDate() + n); return x; };
const mondayOf = d => addDays(d, -((d.getDay() + 6) % 7));
const MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"];
const JOURS = ["dimanche", "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi"];
const JR = ["LUN", "MAR", "MER", "JEU", "VEN", "SAM", "DIM"];
const cap = s => s[0].toUpperCase() + s.slice(1);
const fmtTime = t => t ? t.replace(":", "h").replace(/h00$/, "h") : "";
const esc = s => String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const uid = () => Math.random().toString(36).slice(2, 10);

/* ===== état ===== */
const STORE_KEY = "petit-agenda-v1";
const state = (() => {
  const base = { name: "sœurette", tasks: {}, events: [], birthdays: [], shifts: {}, notes: [], photos: {} };
  try { return Object.assign(base, JSON.parse(localStorage.getItem(STORE_KEY) || "{}")); }
  catch (e) { return base; }
})();
let saveT;
function save() {
  clearTimeout(saveT);
  saveT = setTimeout(() => {
    try { localStorage.setItem(STORE_KEY, JSON.stringify(state)); }
    catch (e) { alert("Le stockage du téléphone est plein — pense à exporter une sauvegarde depuis les réglages."); }
  }, 150);
}

const tasksOf = k => state.tasks[k] || [];
const eventsOf = k => state.events.filter(e => e.date === k).sort((a, b) => (a.time || "99") < (b.time || "99") ? -1 : 1);
const birthdaysOf = d => state.birthdays.filter(b => b.day === d.getDate() && b.month === d.getMonth() + 1);

/* ===== navigation ===== */
let curView = "jour";
let curDate = today();
let weekStart = mondayOf(today());
let mCur = { y: today().getFullYear(), m: today().getMonth() };
let gardeEdit = false;

function show(v) {
  curView = v;
  document.body.className = "bg-" + v;
  document.querySelectorAll(".view").forEach(s => s.hidden = true);
  $("#view-" + v).hidden = false;
  document.querySelectorAll(".tab").forEach(t => t.classList.toggle("on", t.dataset.view === v));
  $("#fab").hidden = (v === "semaine");
  render();
  $("#main").scrollTop = 0;
}
function render() {
  if (curView === "jour") renderJour();
  else if (curView === "semaine") renderSemaine();
  else if (curView === "mois") renderMois();
  else renderNotes();
}

/* ===== illustrations du mois ===== */
const spark = (x, y, s, c) => `<path transform="translate(${x} ${y}) scale(${s})" d="M10 1Q11.4 8.6 19 10Q11.4 11.4 10 19Q8.6 11.4 1 10Q8.6 8.6 10 1Z" fill="${c}"/>`;
const fleur = (x, y, c) => `<g transform="translate(${x} ${y})">${[0, 60, 120, 180, 240, 300].map(r => `<ellipse rx="5" ry="8.5" transform="rotate(${r}) translate(0 -7.5)" fill="${c}"/>`).join("")}<circle r="4.2" fill="#f5d442"/></g>`;
const feuille = (x, y, c, r) => `<ellipse cx="${x}" cy="${y}" rx="11" ry="4.6" transform="rotate(${r} ${x} ${y})" fill="${c}" opacity=".95"/>`;
const neige = c => [[60, 34], [150, 22], [258, 46], [330, 24], [104, 78], [296, 92]].map(([x, y], i) => spark(x, y, i % 2 ? .55 : .8, c)).join("");
const pluie = () => `<path d="M60 30l-6 14M150 20l-6 14M260 44l-6 14M330 26l-6 14M100 70l-5 12M210 12l-5 12" stroke="#eef6f0" stroke-width="2" stroke-linecap="round" opacity=".55"/>`;

const ART = {
  1: { a: "#9fbfc2", b: "#557f8a", pad: "#b9cdb9", pad2: "#a3bfa8", x: neige("#f4fbfb") },
  2: { a: "#a3b7a5", b: "#587368", pad: "#b5cbb2", pad2: "#9dbba0", x: `<path d="M112 40c4-7 14-6 14 2 0 6-8 10-14 14-6-4-14-8-14-14 0-8 10-9 14-2z" fill="#e9b6b2"/><path d="M300 112c3-5 10-4 10 1.5 0 4-6 7-10 10-4-3-10-6-10-10 0-5.5 7-6.5 10-1.5z" fill="#f0cbc8"/>` },
  3: { a: "#8fbb95", b: "#4a7a63", x: pluie() },
  4: { a: "#8bbd8f", b: "#478361", x: fleur(56, 132, "#f3cdd8") + fleur(318, 146, "#f7e6ef") + fleur(210, 36, "#f3cdd8") },
  5: { a: "#83bb85", b: "#3f7f57", x: fleur(56, 132, "#f0c1d4") + fleur(318, 146, "#f3cdd8") + `<g transform="translate(160 44)"><ellipse cx="-6" cy="0" rx="7" ry="10" fill="#f0c1d4" transform="rotate(-20)"/><ellipse cx="6" cy="0" rx="7" ry="10" fill="#e8a9c4" transform="rotate(20)"/><rect x="-1.2" y="-9" width="2.4" height="18" rx="1.2" fill="#7a5c48"/></g>` },
  6: { a: "#7fb887", b: "#3f7a5a", x: `<circle cx="330" cy="38" r="30" fill="#f7dd6b" opacity=".25"/><circle cx="330" cy="38" r="21" fill="#f7dd6b" opacity=".95"/>` },
  7: { a: "#76b184", b: "#33705c", x: `<g transform="translate(130 48)"><rect x="-1.5" y="-4" width="3" height="26" rx="1.5" fill="#4a6e5e"/><ellipse cx="-10" cy="2" rx="11" ry="3.6" fill="#d8ecdf" opacity=".85" transform="rotate(-16)"/><ellipse cx="10" cy="2" rx="11" ry="3.6" fill="#d8ecdf" opacity=".85" transform="rotate(16)"/><circle cy="-6" r="3.2" fill="#3d5c4e"/></g>` },
  8: { a: "#79a686", b: "#46745f", x: `<circle cx="56" cy="132" r="5" fill="#f5d442"/><circle cx="320" cy="146" r="4" fill="#f5d442"/><path d="M150 122q34 6 68 0" stroke="#f5d442" stroke-width="2" fill="none" opacity=".4" stroke-linecap="round"/>` },
  9: { a: "#97ab77", b: "#5a7a52", x: feuille(120, 36, "#d8a355", -20) + feuille(250, 66, "#c98d3f", 15) + feuille(320, 28, "#d8b665", 40) },
  10: { a: "#a3a06c", b: "#5f7050", x: feuille(90, 44, "#c98d3f", -30) + feuille(200, 24, "#b8762e", 20) + feuille(300, 70, "#d8a355", 50) + feuille(160, 128, "#c98d3f", 8) + feuille(340, 150, "#b8762e", -14) },
  11: { a: "#8da095", b: "#4e6560", x: `<rect x="-10" y="44" width="210" height="12" rx="6" fill="#eef2ee" opacity=".18"/><rect x="180" y="82" width="230" height="12" rx="6" fill="#eef2ee" opacity=".14"/>` + pluie() },
  12: { a: "#6f96a0", b: "#3a5c6b", pad: "#b9cdb9", pad2: "#a3bfa8", x: neige("#f4fbfb") + spark(332, 20, 1.1, "#f5d442") }
};

function duck(x, y, s) {
  return `<g transform="translate(${x} ${y}) scale(${s})"><g class="drift">
 <ellipse cx="36" cy="29" rx="26" ry="3" fill="none" stroke="#fdf6d8" stroke-width="1.4" opacity=".45"/>
 <ellipse cx="33" cy="19" rx="16" ry="9" fill="#fdfaef" stroke="#c9c2a2" stroke-width="1.4"/>
 <circle cx="47" cy="10" r="6.5" fill="#fdfaef" stroke="#c9c2a2" stroke-width="1.4"/>
 <path d="M53 9.5l7.5 2-7.5 2.4z" fill="#e19a5e"/>
 <circle cx="48.5" cy="8.5" r="1.2" fill="#4a4636"/>
 <path d="M22 19q6 4.5 15 3.5" fill="none" stroke="#c9c2a2" stroke-width="1.3" stroke-linecap="round"/></g></g>`;
}
function monthArt(m) {
  const A = ART[m];
  return `<svg class="art" viewBox="0 0 390 190" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
   <defs><linearGradient id="eau${m}" x1="0" y1="0" x2="0" y2="1">
     <stop offset="0" stop-color="${A.a}"/><stop offset="1" stop-color="${A.b}"/></linearGradient></defs>
   <rect width="390" height="190" fill="url(#eau${m})"/>
   <ellipse cx="52" cy="138" rx="30" ry="12" fill="${A.pad || "#a5c785"}" opacity=".9"/>
   <ellipse cx="100" cy="162" rx="20" ry="8" fill="${A.pad2 || "#8ab578"}" opacity=".85"/>
   <ellipse cx="316" cy="150" rx="26" ry="10" fill="${A.pad || "#a5c785"}" opacity=".9"/>
   <ellipse cx="342" cy="58" rx="17" ry="7" fill="${A.pad2 || "#8ab578"}" opacity=".7"/>
   <path d="M0 34q60 8 120 0M210 52q52 8 104 0M24 92q44 6 88 0" stroke="#fdf6d8" stroke-width="2" fill="none" opacity=".26" stroke-linecap="round"/>
   ${duck(70, 30, 1.15)}${duck(220, 95, .9)}
   ${A.x || ""}
  </svg>`;
}

/* ===== vue Jour ===== */
function blobWave() {
  return `<svg class="blob bob" viewBox="0 0 62 72" aria-hidden="true">
  <rect x="17" y="34" width="28" height="32" rx="14" fill="#dcedb2" stroke="#4c8b33" stroke-width="2.6"/>
  <circle cx="31" cy="21" r="16" fill="#dcedb2" stroke="#4c8b33" stroke-width="2.6"/>
  <g class="arm"><rect x="44" y="14" width="7.5" height="17" rx="3.7" transform="rotate(-38 47 18)" fill="#dcedb2" stroke="#4c8b33" stroke-width="2.4"/></g>
  <circle cx="25.5" cy="20" r="1.8" fill="#3d5c2a"/><circle cx="36.5" cy="20" r="1.8" fill="#3d5c2a"/>
  <path d="M28 26q3 2.6 6 0" fill="none" stroke="#3d5c2a" stroke-width="1.7" stroke-linecap="round"/></svg>`;
}

function renderJour() {
  const d = curDate, k = keyOf(d), isToday = k === keyOf(today());
  const sh = state.shifts[k];
  const tasks = tasksOf(k), evs = eventsOf(k), bds = birthdaysOf(d);
  let h = `<svg class="etoile-fixe st-y tw" style="top:calc(64px + env(safe-area-inset-top));right:112px;width:16px;height:16px"><use href="#i-spark"/></svg>
  <svg class="etoile-fixe st-g tw2" style="top:calc(148px + env(safe-area-inset-top));right:26px;width:11px;height:11px"><use href="#i-spark"/></svg>
  <div class="head-row"><div>`;
  if (isToday) h += `<p class="hello">Coucou ${esc(state.name)} ✿</p>`;
  h += `<p class="bigdate">${cap(JOURS[d.getDay()])} ${d.getDate()}<small>${MOIS[d.getMonth()]} ${d.getFullYear()}</small></p>
  </div>${blobWave()}</div>
  <div class="daynav">
    <button class="nav-btn" data-act="day-prev" aria-label="jour précédent"><svg><use href="#i-chev"/></svg></button>
    <button class="nav-btn next" data-act="day-next" aria-label="jour suivant"><svg><use href="#i-chev"/></svg></button>
    ${isToday ? "" : `<button class="to-today" data-act="day-today">revenir à aujourd'hui</button>`}
  </div>`;
  if (sh === "jour") h += `<div class="garde-banner jour"><svg><use href="#i-sun"/></svg>Garde de jour · 7h – 19h</div>`;
  if (sh === "nuit") h += `<div class="garde-banner nuit"><svg><use href="#i-moon"/></svg>Garde de nuit · 19h – 7h</div>`;
  h += `<div class="carte"><h3>${isToday ? "À FAIRE AUJOURD'HUI" : "À FAIRE CE JOUR"}</h3>`;
  h += tasks.length ? tasks.map(t => `
    <div class="t-item ${t.done ? "done" : ""}" data-id="${t.id}">
      <button class="dot" data-act="task-toggle" aria-label="cocher"></button>
      <span class="txt">${esc(t.text)}</span>
      <button class="del" data-act="task-del" aria-label="supprimer"><svg><use href="#i-x"/></svg></button>
    </div>`).join("") : `<p class="vide">rien à faire ce jour ✿</p>`;
  h += `</div><div class="carte jaune"><h3>RENDEZ-VOUS</h3>`;
  const rows = [];
  bds.forEach(b => rows.push(`<button class="e-item" data-act="bd-open" data-id="${b.id}">
    <svg class="ic"><use href="#i-cake"/></svg><span>Anniversaire de ${esc(b.name)}</span></button>`));
  evs.forEach(e => rows.push(`<button class="e-item" data-act="ev-open" data-id="${e.id}">
    ${e.type === "rappel" ? `<svg class="ic"><use href="#i-bell"/></svg>` : (e.time ? `<time>${fmtTime(e.time)}</time>` : `<span class="pt-dot"></span>`)}
    <span>${e.type === "rappel" ? "Rappel : " : ""}${esc(e.text)}${e.type === "rappel" && e.time ? ` (${fmtTime(e.time)})` : ""}</span></button>`));
  h += rows.length ? rows.join("") : `<p class="vide">journée libre ~</p>`;
  h += `</div>`;
  $("#view-jour").innerHTML = h;
}

/* ===== vue Semaine ===== */
function fmtRange(a, b) {
  if (a.getMonth() === b.getMonth()) return `${a.getDate()} – ${b.getDate()} ${MOIS[a.getMonth()]}`;
  return `${a.getDate()} ${MOIS[a.getMonth()]} – ${b.getDate()} ${MOIS[b.getMonth()]}`;
}
function renderSemaine() {
  const days = [...Array(7)].map((_, i) => addDays(weekStart, i));
  const tk = keyOf(today());
  const nG = days.filter(d => state.shifts[keyOf(d)]).length;
  let h = `<div class="head-row"><p class="w-title"><span class="g">✦</span> MA SEMAINE</p>
    <svg class="blob bob" viewBox="0 0 62 72" style="width:64px"><use href="#b-nurse"/></svg></div>
  <div class="w-nav">
    <button class="nav-btn" data-act="w-prev" aria-label="semaine précédente"><svg><use href="#i-chev"/></svg></button>
    <span class="w-range">${fmtRange(days[0], days[6])}</span>
    <button class="nav-btn next" data-act="w-next" aria-label="semaine suivante"><svg><use href="#i-chev"/></svg></button>
  </div>
  <div class="w-sum">
    <span><svg><use href="#i-cross"/></svg>${nG} garde${nG > 1 ? "s" : ""}</span>
    <span>${nG * 12} h</span>
    <span>${7 - nG} repos</span>
  </div>
  <div class="w-days">`;
  h += days.map(d => {
    const k = keyOf(d), sh = state.shifts[k];
    const evs = eventsOf(k).map(e => e.text).concat(birthdaysOf(d).map(b => "anniv " + b.name));
    const evTxt = evs.length ? `<span class="w-perso">${esc(evs.slice(0, 2).join(" · "))}</span>` : "";
    const mid = sh === "jour" ? `<span class="shift jour"><svg><use href="#i-sun"/></svg>7h – 19h</span>`
      : sh === "nuit" ? `<span class="shift nuit"><svg><use href="#i-moon"/></svg>19h – 7h</span>`
      : `<span class="w-repos">repos ✿</span>`;
    return `<button class="w-day ${k === tk ? "today" : ""}" data-key="${k}" data-act="w-day">
      <b>${JR[(d.getDay() + 6) % 7]} <span>${d.getDate()}</span></b>${mid}${evTxt}</button>`;
  }).join("");
  h += `</div>
  <button class="w-btn ${gardeEdit ? "actif" : ""}" data-act="w-edit"><svg><use href="#i-pen"/></svg>${gardeEdit ? "terminé !" : "saisir mes gardes"}</button>`;
  if (gardeEdit) h += `<p class="w-hint">touche un jour : repos → garde jour → garde nuit → repos</p>`;
  $("#view-semaine").innerHTML = h;
}

/* ===== vue Mois ===== */
function renderMois(slide) {
  const y = mCur.y, m = mCur.m;
  const startOffset = (new Date(y, m, 1).getDay() + 6) % 7;
  const nDays = new Date(y, m + 1, 0).getDate();
  const tk = keyOf(today());
  const photo = state.photos[String(m + 1)];
  let h = `<div class="m-photo ${slide ? "slide" : ""}">
    ${photo ? `<img class="art" src="${photo}" alt="photo du mois">` : monthArt(m + 1)}
    <svg class="vague" viewBox="0 0 390 26" preserveAspectRatio="none" aria-hidden="true"><path d="M0 26V15q65-13 130-5t130 3q65-4 130 5v8z"/></svg>
    <button class="m-cam" data-act="m-photo" aria-label="changer la photo du mois"><svg><use href="#i-cam"/></svg></button>
  </div>
  <div class="m-nav">
    <button class="nav-btn" data-act="m-prev" aria-label="mois précédent"><svg><use href="#i-chev"/></svg></button>
    <span class="m-mois">${MOIS[m].toUpperCase()}<small>${y}</small></span>
    <button class="nav-btn next" data-act="m-next" aria-label="mois suivant"><svg><use href="#i-chev"/></svg></button>
  </div>
  <div class="m-grid">`;
  ["L", "M", "M", "J", "V", "S", "D"].forEach(x => h += `<span class="m-gh">${x}</span>`);
  let ci = 0;
  for (let i = 0; i < startOffset; i++, ci++) h += `<span class="m-cell off"></span>`;
  for (let day = 1; day <= nDays; day++, ci++) {
    const d = new Date(y, m, day), k = keyOf(d);
    const evs = eventsOf(k);
    const sh = state.shifts[k];
    let inner = String(day);
    if (sh) inner += `<svg class="sh ${sh === "nuit" ? "snuit" : "sjour"}"><use href="#i-${sh === "nuit" ? "moon" : "sun"}"/></svg>`;
    if (evs.some(e => e.type === "rdv")) inner += `<span class="pt"></span>`;
    if (birthdaysOf(d).length) inner += `<svg class="ev"><use href="#i-cake"/></svg>`;
    if (evs.some(e => e.type === "rappel")) inner += `<svg class="ev"><use href="#i-bell"/></svg>`;
    h += `<button class="m-cell ${ci % 2 ? "alt" : ""} ${k === tk ? "today" : ""} anim" style="animation-delay:${Math.min(ci * 8, 290)}ms" data-act="m-day" data-key="${k}">${inner}</button>`;
  }
  while (ci % 7 !== 0) { h += `<span class="m-cell off"></span>`; ci++; }
  h += `</div>
  <div class="m-leg">
    <span><span class="pt"></span>rdv</span>
    <span><svg><use href="#i-cake"/></svg>anniv</span>
    <span><svg><use href="#i-bell"/></svg>rappel</span>
    <span><svg class="lj"><use href="#i-sun"/></svg>garde jour</span>
    <span><svg class="ln"><use href="#i-moon"/></svg>garde nuit</span>
  </div>
  <p class="m-touch">touche un jour → sa page s'ouvre</p>`;
  $("#view-mois").innerHTML = h;
}
function stepMonth(n) {
  mCur.m += n;
  if (mCur.m < 0) { mCur.m = 11; mCur.y--; }
  if (mCur.m > 11) { mCur.m = 0; mCur.y++; }
  renderMois(true);
}

/* ===== vue Notes ===== */
function renderNotes() {
  let h = `<div class="n-head"><p class="n-title">Notes ✎</p>
    <button class="n-gear" data-act="settings" aria-label="réglages"><svg><use href="#i-gear"/></svg></button></div>
  <div class="n-paper">`;
  h += state.notes.length ? state.notes.map(n => `
    <div class="n-item" data-id="${n.id}">
      <button class="txt" data-act="note-open">${esc(n.text)}</button>
      <button class="del" data-act="note-del" aria-label="supprimer"><svg><use href="#i-x"/></svg></button>
    </div>`).join("") : `<p class="n-vide">touche le + pour écrire ta première note ✿</p>`;
  h += `<svg class="n-blob bob" viewBox="0 0 62 72" aria-hidden="true"><use href="#b-party"/></svg></div>`;
  $("#view-notes").innerHTML = h;
}

/* ===== feuilles (sheets) ===== */
function openSheet(html) { $("#overlay").hidden = false; const s = $("#sheet"); s.innerHTML = html; s.hidden = false; }
function closeSheet() { $("#overlay").hidden = true; $("#sheet").hidden = true; $("#sheet").innerHTML = ""; }

let addType = "tache";
function openAdd() {
  addType = curView === "notes" ? "note" : "tache";
  renderAdd();
}
function renderAdd() {
  const k = keyOf(curView === "jour" ? curDate : today());
  const segs = [["tache", "Tâche"], ["rdv", "Rendez-vous"], ["rappel", "Rappel"], ["anniv", "Anniversaire"], ["note", "Note"]];
  let h = `<p class="s-title">Ajouter</p><div class="seg">` +
    segs.map(([v, l]) => `<button type="button" data-seg="${v}" class="${addType === v ? "on" : ""}">${l}</button>`).join("") +
    `</div><form id="addForm">`;
  if (addType === "note") {
    h += `<div class="champ"><label>ta note</label><textarea name="text" required></textarea></div>`;
  } else if (addType === "anniv") {
    h += `<div class="champ"><label>l'anniversaire de qui ?</label><input name="text" required placeholder="maman"></div>
      <div class="champ"><label>sa date (l'année n'a pas d'importance)</label><input type="date" name="date" required value="${k}"></div>`;
  } else {
    h += `<div class="champ"><label>quoi ?</label><input name="text" required placeholder="${addType === "tache" ? "arroser les plantes" : addType === "rdv" ? "rdv coiffeur" : "acheter le gâteau"}"></div>`;
    h += addType === "tache"
      ? `<div class="champ"><label>pour quel jour ?</label><input type="date" name="date" value="${k}" required></div>`
      : `<div class="s-row"><div class="champ"><label>date</label><input type="date" name="date" value="${k}" required></div>
         <div class="champ"><label>heure</label><input type="time" name="time"></div></div>`;
  }
  h += `<button class="btn-main">ajouter</button></form>`;
  openSheet(h);
  $("#sheet .seg").addEventListener("click", e => {
    const b = e.target.closest("[data-seg]");
    if (b) { addType = b.dataset.seg; renderAdd(); }
  });
  $("#addForm").addEventListener("submit", e => {
    e.preventDefault();
    const f = new FormData(e.target);
    const text = (f.get("text") || "").trim();
    if (!text) return;
    if (addType === "note") state.notes.unshift({ id: uid(), text, updated: Date.now() });
    else if (addType === "anniv") { const d = fromKey(f.get("date")); state.birthdays.push({ id: uid(), day: d.getDate(), month: d.getMonth() + 1, name: text }); }
    else if (addType === "tache") { const kk = f.get("date"); (state.tasks[kk] = state.tasks[kk] || []).push({ id: uid(), text, done: false }); }
    else state.events.push({ id: uid(), date: f.get("date"), time: f.get("time") || "", text, type: addType });
    save(); closeSheet(); render();
  });
}

function openEvent(id) {
  const e = state.events.find(x => x.id === id);
  if (!e) return;
  const d = fromKey(e.date);
  openSheet(`<p class="s-title">${e.type === "rappel" ? "Rappel" : "Rendez-vous"}</p>
    <p style="font-weight:700;font-size:17px">${esc(e.text)}</p>
    <p class="s-note">${cap(JOURS[d.getDay()])} ${d.getDate()} ${MOIS[d.getMonth()]}${e.time ? " · " + fmtTime(e.time) : ""}</p>
    <button class="btn-sec" data-close>fermer</button>
    <button class="btn-danger" data-del-ev="${id}">supprimer</button>`);
}
function openBd(id) {
  const b = state.birthdays.find(x => x.id === id);
  if (!b) return;
  openSheet(`<p class="s-title">Anniversaire</p>
    <p style="font-weight:700;font-size:17px">${esc(b.name)} — le ${b.day} ${MOIS[b.month - 1]}, chaque année</p>
    <button class="btn-sec" data-close>fermer</button>
    <button class="btn-danger" data-del-bd="${id}">supprimer</button>`);
}
function openNote(id) {
  const n = state.notes.find(x => x.id === id);
  if (!n) return;
  openSheet(`<p class="s-title">Ma note</p>
    <form id="noteForm"><div class="champ"><textarea name="text" required>${esc(n.text)}</textarea></div>
    <button class="btn-main">enregistrer</button></form>
    <button class="btn-danger" data-del-note="${id}">supprimer</button>`);
  $("#noteForm").addEventListener("submit", e => {
    e.preventDefault();
    n.text = (new FormData(e.target).get("text") || "").trim();
    n.updated = Date.now();
    save(); closeSheet(); render();
  });
}
function openSettings() {
  const customs = Object.keys(state.photos);
  openSheet(`<p class="s-title">Réglages</p>
    <div class="champ"><label>ton prénom</label><input id="setName" value="${esc(state.name)}"></div>
    ${customs.length ? `<div class="champ"><label>photos personnalisées</label>${customs.map(mm => `<button class="btn-sec" data-del-photo="${mm}">retirer la photo de ${MOIS[mm - 1]}</button>`).join("")}</div>` : ""}
    <button class="btn-sec" data-export>exporter une sauvegarde</button>
    <button class="btn-sec" data-import>importer une sauvegarde</button>
    <p class="s-note">Tes données restent sur ce téléphone, rien ne part sur internet. Pense à exporter une sauvegarde de temps en temps — elle se range dans Fichiers.</p>
    <button class="btn-main" data-close>fermer</button>`);
  $("#setName").addEventListener("change", e => { state.name = e.target.value.trim() || "toi"; save(); });
}

/* ===== photo du mois ===== */
function pickPhoto() {
  const inp = document.createElement("input");
  inp.type = "file"; inp.accept = "image/*";
  inp.onchange = () => {
    const f = inp.files[0];
    if (!f) return;
    const img = new Image();
    img.onload = () => {
      const w = Math.min(1000, img.width), hh = Math.round(img.height * w / img.width);
      const c = document.createElement("canvas");
      c.width = w; c.height = hh;
      c.getContext("2d").drawImage(img, 0, 0, w, hh);
      try { state.photos[String(mCur.m + 1)] = c.toDataURL("image/jpeg", .82); save(); renderMois(); }
      catch (err) { alert("Impossible d'enregistrer la photo (stockage plein ?)"); }
      URL.revokeObjectURL(img.src);
    };
    img.src = URL.createObjectURL(f);
  };
  inp.click();
}

/* ===== sauvegarde ===== */
function doExport() {
  const blob = new Blob([JSON.stringify(state, null, 1)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "petit-agenda-sauvegarde.json";
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 5000);
}
function doImport() {
  const inp = document.createElement("input");
  inp.type = "file"; inp.accept = ".json,application/json";
  inp.onchange = () => {
    const f = inp.files[0];
    if (!f) return;
    f.text().then(t => {
      try { Object.assign(state, JSON.parse(t)); save(); closeSheet(); render(); alert("Sauvegarde importée ✿"); }
      catch (e) { alert("Ce fichier n'est pas une sauvegarde valide."); }
    });
  };
  inp.click();
}

/* ===== éclat d'étoiles ===== */
function burst(x, y) {
  const b = document.createElement("div");
  b.className = "burst";
  b.style.left = x + "px"; b.style.top = y + "px";
  let s = "";
  for (let i = 0; i < 6; i++) {
    const a = Math.PI * 2 * i / 6 + Math.random() * .5, r = 26 + Math.random() * 16;
    s += `<svg style="--dx:${Math.cos(a) * r}px;--dy:${Math.sin(a) * r}px"><use href="#i-spark"/></svg>`;
  }
  b.innerHTML = s;
  document.body.appendChild(b);
  setTimeout(() => b.remove(), 700);
}

/* ===== interactions ===== */
document.addEventListener("click", e => {
  const el = e.target.closest("[data-act],[data-close],[data-del-ev],[data-del-bd],[data-del-note],[data-del-photo],[data-export],[data-import]");
  if (!el) return;
  if (el.hasAttribute("data-close")) return closeSheet();
  if (el.hasAttribute("data-export")) return doExport();
  if (el.hasAttribute("data-import")) return doImport();
  if (el.dataset.delEv) { state.events = state.events.filter(x => x.id !== el.dataset.delEv); save(); closeSheet(); return render(); }
  if (el.dataset.delBd) { state.birthdays = state.birthdays.filter(x => x.id !== el.dataset.delBd); save(); closeSheet(); return render(); }
  if (el.dataset.delNote) { state.notes = state.notes.filter(x => x.id !== el.dataset.delNote); save(); closeSheet(); return render(); }
  if (el.dataset.delPhoto) { delete state.photos[el.dataset.delPhoto]; save(); closeSheet(); return render(); }
  switch (el.dataset.act) {
    case "day-prev": curDate = addDays(curDate, -1); return renderJour();
    case "day-next": curDate = addDays(curDate, 1); return renderJour();
    case "day-today": curDate = today(); return renderJour();
    case "task-toggle": {
      const id = el.closest(".t-item").dataset.id, k = keyOf(curDate);
      const t = tasksOf(k).find(x => x.id === id);
      if (!t) return;
      t.done = !t.done; save();
      if (t.done) { const r = el.getBoundingClientRect(); burst(r.left + r.width / 2, r.top + r.height / 2); }
      return renderJour();
    }
    case "task-del": {
      const id = el.closest(".t-item").dataset.id, k = keyOf(curDate);
      state.tasks[k] = tasksOf(k).filter(x => x.id !== id);
      save(); return renderJour();
    }
    case "ev-open": return openEvent(el.dataset.id);
    case "bd-open": return openBd(el.dataset.id);
    case "w-prev": weekStart = addDays(weekStart, -7); return renderSemaine();
    case "w-next": weekStart = addDays(weekStart, 7); return renderSemaine();
    case "w-edit": gardeEdit = !gardeEdit; return renderSemaine();
    case "w-day": {
      const k = el.dataset.key;
      if (gardeEdit) {
        const cur = state.shifts[k];
        if (cur === "jour") state.shifts[k] = "nuit";
        else if (cur === "nuit") delete state.shifts[k];
        else state.shifts[k] = "jour";
        save(); renderSemaine();
        const nd = document.querySelector(`.w-day[data-key="${k}"]`);
        if (nd) nd.classList.add("pop");
        return;
      }
      curDate = fromKey(k);
      return show("jour");
    }
    case "m-prev": return stepMonth(-1);
    case "m-next": return stepMonth(1);
    case "m-day": curDate = fromKey(el.dataset.key); return show("jour");
    case "m-photo": return pickPhoto();
    case "settings": return openSettings();
    case "note-open": return openNote(el.closest(".n-item").dataset.id);
    case "note-del": {
      const id = el.closest(".n-item").dataset.id;
      state.notes = state.notes.filter(x => x.id !== id);
      save(); return renderNotes();
    }
  }
});

$("#overlay").addEventListener("click", closeSheet);
$("#tabbar").addEventListener("click", e => {
  const t = e.target.closest(".tab");
  if (!t) return;
  const v = t.dataset.view;
  if (v === "jour") curDate = today();
  if (v === "semaine") { weekStart = mondayOf(today()); gardeEdit = false; }
  if (v === "mois") mCur = { y: today().getFullYear(), m: today().getMonth() };
  show(v);
});
$("#fab").addEventListener("click", openAdd);

show("jour");
