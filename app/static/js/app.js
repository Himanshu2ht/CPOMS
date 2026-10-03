// Client helpers: alerts, double-submit guard, live polling (real-time updates).
document.addEventListener("DOMContentLoaded", () => {
  // auto-dismiss flash alerts, but NEVER countdown banners (role=timer / data-keep).
  setTimeout(() => document.querySelectorAll(".alert").forEach(a => {
    if (a.hasAttribute("data-keep") || a.querySelector("[data-countdown-to]")) return;
    if (window.bootstrap) bootstrap.Alert.getOrCreateInstance(a).close();
  }), 6000);
  document.querySelectorAll("form").forEach(f => f.addEventListener("submit", () => {
    const b = f.querySelector("button:not([type=button])");
    if (b) setTimeout(() => (b.disabled = true), 0);
  }));
  // menu live search (if present)
  const search = document.getElementById("menu-search");
  if (search) {
    search.addEventListener("input", () => {
      const q = search.value.toLowerCase();
      document.querySelectorAll("[data-dish]").forEach(card => {
        card.style.display = card.dataset.dish.includes(q) ? "" : "none";
      });
    });
  }
  // "＋ add category": reveal the inline input next to the dropdown.
  document.querySelectorAll("[data-add-category]").forEach(btn => {
    btn.addEventListener("click", () => {
      const scope = btn.closest("[data-category-form]") || btn.closest("tr") || document;
      const input = scope.querySelector("[data-new-category]");
      if (input) { input.classList.toggle("d-none"); input.focus(); }
    });
  });
  // On submit, a filled new-category input becomes the selected option.
  document.addEventListener("submit", (e) => {
    const form = e.target;
    const scope = form.hasAttribute("data-category-form") ? form
      : (form.closest("[data-category-form]") || (form.id && form.id.startsWith("edit-") ? form.closest("tr") : null));
    if (!scope) return;
    const sel = scope.querySelector("[data-category-select]");
    const ni = scope.querySelector("[data-new-category]");
    if (sel && ni && ni.value.trim()) {
      const v = ni.value.trim();
      if (![...sel.options].some(o => o.value === v)) sel.add(new Option(v, v));
      sel.value = v;
    }
  });
  // "Slot starts in 12:34" -> "Slot started — mark READY / pickup now".
  // With data-grace-minutes (READY orders) it counts the pickup window instead.
  const fmt = (ms) => {
    const s = Math.max(0, Math.floor(ms / 1000));
    const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
    return h > 0 ? `${h}h ${m}m` : m > 0 ? `${m}m ${String(sec).padStart(2, "0")}s` : `${sec}s`;
  };
  const refreshCountdowns = () => {
    document.querySelectorAll("[data-countdown-to]").forEach(el => {
      const slot = new Date(el.dataset.countdownTo).getTime();
      if (isNaN(slot)) return;
      const graceMin = parseFloat(el.dataset.graceMinutes || "0");
      const now = Date.now();
      if (graceMin > 0 && now >= slot) {
        const left = slot + graceMin * 60000 - now;
        el.textContent = left > 0 ? `pickup window: ${fmt(left)} left` : "pickup window over";
      } else if (now >= slot) {
        el.textContent = `slot started ${fmt(now - slot)} ago — mark READY`;
      } else {
        el.textContent = `slot starts in ${fmt(slot - now)}`;
      }
    });
  };
  refreshCountdowns();
  setInterval(refreshCountdowns, 1000);
});

// --- order tracking page: poll /orders/<id>/status every 8s ---
function pollOrderStatus(orderId) {
  const badge = document.getElementById("order-status-badge");
  const note = document.getElementById("order-live-note");
  if (!badge) return;
  const tick = async () => {
    try {
      const r = await fetch(`/orders/${orderId}/status`, {headers: {"Accept": "application/json"}});
      if (!r.ok) return;
      const d = await r.json();
      const pretty = d.status.replace(/_/g, " ");
      badge.textContent = pretty;
      badge.className = `badge fs-6 status-${d.status} px-3 py-2`;
      document.querySelectorAll(".timeline .step").forEach(s => {
        const seq = ["PAID", "PREPARING", "READY", "COLLECTED"];
        const idx = seq.indexOf(d.status);
        const mine = seq.indexOf(s.dataset.step);
        s.classList.toggle("done", mine !== -1 && mine <= idx);
      });
      if (note) note.textContent = `live · updated ${new Date().toLocaleTimeString()}`;
      if (["COLLECTED", "CANCELLED", "FAILED", "NO_SHOW"].includes(d.status)) clearInterval(timer);
    } catch (e) { /* offline: keep last state */ }
  };
  const timer = setInterval(tick, 8000);
}

// --- staff kitchen: poll /staff/queue-data every 10s, update counts + rows ---
function pollQueueJSON() {
  const wrap = document.getElementById("queue-live");
  const updated = document.getElementById("queue-updated");
  const url = "/staff/queue-data";
  const tick = async () => {
    try {
      const r = await fetch(url, {headers: {"Accept": "application/json"}});
      if (!r.ok) return;
      const rows = await r.json();
      const counts = {PAID: 0, PREPARING: 0, READY: 0};
      rows.forEach(o => { if (counts[o.status] !== undefined) counts[o.status]++; });
      Object.entries(counts).forEach(([k, v]) => {
        document.querySelectorAll(`[data-count="${k.toLowerCase()}"]`).forEach(el => (el.textContent = v));
      });
      if (wrap && wrap.querySelector("tbody")) {
        const tb = wrap.querySelector("tbody");
        tb.innerHTML = rows.length ? rows.map(o => {
          const when = o.slot ? new Date(o.slot) : null;
          const slotTxt = when ? when.toLocaleString([], {hour: "numeric", minute: "2-digit"}) : "";
          const cd = o.slot ? `<div><span class="badge bg-light text-dark border" data-countdown-to="${o.slot}">…</span></div>` : "";
          return `<tr>
          <td class="fw-bold text-dark">${o.token || "#" + o.id}</td>
          <td class="fw-medium">${o.customer}${o.overdue ? ' <span class="badge bg-warning-subtle text-warning-emphasis border border-warning-subtle ms-1">overdue</span>' : ""}</td>
          <td class="small text-secondary">${slotTxt}${cd}</td>
          <td class="small">${o.items.join(", ")}</td>
          <td><span class="badge status-${o.status} px-2 py-1">${o.status}</span></td>
          <td class="text-end"></td>
        </tr>`;}).join("") : `<tr><td colspan="6" class="text-center text-muted py-4">No active orders.</td></tr>`;
      }
      if (updated) updated.textContent = `live · ${rows.length} active · ${new Date().toLocaleTimeString()}`;
    } catch (e) { /* ignore transient errors */ }
  };
  setInterval(tick, 10000);
}
