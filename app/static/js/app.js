// Client-side helpers: auto-dismiss alerts and double-submit protection.
document.addEventListener("DOMContentLoaded", () => {
  setTimeout(() => document.querySelectorAll(".alert").forEach(a => {
    if (window.bootstrap) bootstrap.Alert.getOrCreateInstance(a).close();
  }), 5000);
  document.querySelectorAll("form").forEach(f => f.addEventListener("submit", () => {
    const b = f.querySelector("button:not([type=button])");
    if (b) setTimeout(() => (b.disabled = true), 0);
  }));
});
