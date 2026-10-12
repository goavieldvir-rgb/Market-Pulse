// Market Pulse — shared page behaviour: day/night edition toggle and the dateline date.
// Loaded in <head> without defer so the saved edition applies before first paint.
(function () {
  var KEY = "mp-theme";
  var root = document.documentElement;
  var saved = null;
  try { saved = localStorage.getItem(KEY); } catch (e) { /* storage blocked: follow the OS */ }
  if (saved === "day" || saved === "night") root.setAttribute("data-theme", saved);

  function current() {
    var t = root.getAttribute("data-theme");
    if (t) return t;
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "night" : "day";
  }

  var ICONS = {
    day: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><circle cx="8" cy="8" r="3"/><path d="M8 1.5v1.6M8 12.9v1.6M1.5 8h1.6M12.9 8h1.6M3.4 3.4l1.1 1.1M11.5 11.5l1.1 1.1M3.4 12.6l1.1-1.1M11.5 4.5l1.1-1.1" stroke-linecap="round"/></svg>',
    night: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="M13.5 9.6A5.6 5.6 0 0 1 6.4 2.5a5.6 5.6 0 1 0 7.1 7.1z" stroke-linejoin="round"/></svg>'
  };

  function paint(btn) {
    var t = current();
    btn.innerHTML = ICONS[t] + '<span>' + (t === "night" ? "Night edition" : "Day edition") + '</span>';
    btn.setAttribute("aria-label", "Switch to the " + (t === "night" ? "day" : "night") + " edition");
  }

  document.addEventListener("DOMContentLoaded", function () {
    var btn = document.getElementById("theme-btn");
    if (btn) {
      paint(btn);
      btn.addEventListener("click", function () {
        var next = current() === "night" ? "day" : "night";
        root.setAttribute("data-theme", next);
        try { localStorage.setItem(KEY, next); } catch (e) { /* not saved, still applied */ }
        paint(btn);
      });
    }
    var d = document.getElementById("today-date");
    if (d && !d.textContent) {
      d.textContent = new Date().toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric", year: "numeric" });
    }
  });
})();

// Section jump bar: ink the chip for the section in view and keep it visible in the
// swipeable bar on phones. Pages call MP_JUMP(nav) once the sections exist.
window.MP_JUMP = function (nav) {
  if (!nav || nav.dataset.tracked) return;
  nav.dataset.tracked = "1";
  var links = Array.prototype.slice.call(nav.querySelectorAll('a[href^="#"]'));
  var current = null, queued = false;
  function update() {
    queued = false;
    var line = nav.getBoundingClientRect().bottom + 24;
    var active = null;
    for (var i = 0; i < links.length; i++) {
      var sec = document.getElementById(links[i].getAttribute("href").slice(1));
      if (!sec || sec.offsetParent === null || links[i].hidden) continue;
      if (sec.getBoundingClientRect().top <= line) active = links[i];
    }
    if (active === current) return;
    if (current) current.removeAttribute("aria-current");
    current = active;
    if (!active) return;
    active.setAttribute("aria-current", "true");
    if (nav.scrollWidth > nav.clientWidth) {
      var l = active.offsetLeft - nav.offsetLeft, r = l + active.offsetWidth;
      if (l < nav.scrollLeft + 16 || r > nav.scrollLeft + nav.clientWidth - 16) nav.scrollLeft = Math.max(0, l - 16);
    }
  }
  function queue() { if (!queued) { queued = true; requestAnimationFrame(update); } }
  window.addEventListener("scroll", queue, { passive: true });
  window.addEventListener("resize", queue);
  update();
};

// Direction marks drawn as SVG (never colour alone): up = filled triangle, down = inverted, flat = dot.
window.MP_MARK = {
  up: '<svg class="mark" viewBox="0 0 10 10" aria-hidden="true"><path d="M5 1.2 9.2 8.6H.8z" fill="currentColor"/></svg>',
  down: '<svg class="mark" viewBox="0 0 10 10" aria-hidden="true"><path d="M5 8.8.8 1.4h8.4z" fill="currentColor"/></svg>',
  flat: '<svg class="mark" viewBox="0 0 10 10" aria-hidden="true"><circle cx="5" cy="5" r="2.6" fill="currentColor"/></svg>',
  hollowUp: '<svg class="mark" viewBox="0 0 10 10" aria-hidden="true"><path d="M5 1.9 8.4 8H1.6z" fill="none" stroke="currentColor" stroke-width="1.3"/></svg>',
  hollowDown: '<svg class="mark" viewBox="0 0 10 10" aria-hidden="true"><path d="M5 8.1 1.6 2h6.8z" fill="none" stroke="currentColor" stroke-width="1.3"/></svg>'
};
