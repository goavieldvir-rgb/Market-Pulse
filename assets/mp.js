// Market Pulse — shared page behaviour: the language (English / Hebrew), the day/night edition,
// the dateline date, the section jump bar and the direction marks.
// Loaded in <head> without defer so the language and edition apply before first paint.
(function () {
  var root = document.documentElement;

  // ---------- Language ----------
  // A ?lang= link wins (and is remembered), then the reader's saved choice, then the browser's
  // first language. Hebrew pages run right to left. Until the Hebrew text is in place the body
  // stays hidden; mp.css reveals it anyway after a moment in case a script fails.
  var LANG_KEY = "mp-lang";
  var urlLang = null, lang = null, storageOk = true;
  try {
    var q = new URLSearchParams(location.search).get("lang");
    if (q === "he" || q === "en") urlLang = q;
  } catch (e) { /* very old browser: no ?lang links */ }
  try {
    if (urlLang) localStorage.setItem(LANG_KEY, urlLang);
    else {
      var s = localStorage.getItem(LANG_KEY);
      if (s === "he" || s === "en") lang = s;
    }
  } catch (e) { storageOk = false; }
  if (urlLang) lang = urlLang;
  if (!lang) {
    var first = (navigator.languages && navigator.languages[0]) || navigator.language || "";
    lang = /^(he|iw)\b/i.test(first) ? "he" : "en";
  }
  var HE = lang === "he";
  root.setAttribute("lang", lang);
  root.setAttribute("dir", HE ? "rtl" : "ltr");
  if (HE) root.classList.add("i18n-pending");

  window.MP_LANG = lang;
  window.MP_HE = HE;
  // L("English", "עברית"): the text for the page's language.
  var L = window.MP_L = function (en, he) { return HE && he !== undefined && he !== null ? he : en; };

  // Hebrew text fixes, applied to the Hebrew strings the pages print:
  // - signed numbers: a left-to-right mark before the sign keeps "−1.2%" in one piece;
  //   without it the sign drifts to the far side of the number. Hyphens inside ranges or
  //   codes ("10b5-1") are left alone.
  // - a Hebrew prefix and its hyphen stay on the same line as the number or Latin word they
  //   join ("ב-2.7%", "ה-S&P 500"): a word joiner after the hyphen forbids the break.
  // - index names keep their number on the same line ("S&P 500", "נאסד״ק 100").
  var SIGNED = /(^|[^\w\u0590-\u05FF.,\u200E])([+\-\u2212\u00B1~\u2248]+)(?=[$\u20AC\u00A3\u20AA]?\d)/g;
  var PREFIX = /([\u05D0-\u05EA])-(?=[A-Za-z0-9$\u2212])/g;
  var INDEX_NAME = /(S&(?:amp;)?P|Nasdaq|Russell|\u05E0\u05D0\u05E1\u05D3\u05F4\u05E7|\u05E8\u05D0\u05E1\u05DC) (?=\d)/g;
  window.MP_BIDI = function (s) {
    return HE && s !== null && s !== undefined
      ? String(s).replace(SIGNED, "$1\u200E$2").replace(PREFIX, "$1-\u2060")
        .replace(INDEX_NAME, "$1\u00A0") : s;
  };

  // "2026-09-29" -> "Sep 29" / "29 בספט׳": a calendar date, so no time-zone shifting.
  var LOCALE = HE ? "he-IL" : "en-US";
  window.MP_LOCALE = LOCALE;
  window.MP_DAY = function (iso, opts) {
    if (!iso || !/^\d{4}-\d{2}-\d{2}/.test(iso)) return "—";
    var p = iso.slice(0, 10).split("-");
    var o = Object.assign({ month: "short", day: "numeric" }, opts || {}, { timeZone: "UTC" });
    return new Date(Date.UTC(+p[0], +p[1] - 1, +p[2])).toLocaleDateString(LOCALE, o);
  };

  // How long ago an ISO timestamp was: "5m ago" / "לפני 5 דק׳".
  window.MP_AGO = function (iso) {
    var t = iso ? Date.parse(iso) : NaN;
    if (!isFinite(t)) return L("no data yet", "אין עדיין נתונים");
    var min = Math.round((Date.now() - t) / 60000);
    var h = Math.floor(min / 60), d = Math.floor(h / 24);
    if (!HE) {
      if (min < 1) return "just now";
      if (min < 60) return min + "m ago";
      if (h < 24) return h + "h " + (min % 60) + "m ago";
      return d + "d ago";
    }
    if (min < 1) return "ממש עכשיו";
    if (min < 60) return min === 1 ? "לפני דקה" : "לפני " + min + " דק׳";
    if (h < 24) {
      var hs = h === 1 ? "שעה" : h === 2 ? "שעתיים" : h + " שע׳";
      return "לפני " + hs + (min % 60 === 1 ? " ודקה" : min % 60 ? " ו-" + (min % 60) + " דק׳" : "");
    }
    return d === 1 ? "לפני יום" : d === 2 ? "לפני יומיים" : "לפני " + d + " ימים";
  };

  // A weekly edition's Monday-to-Friday label in the page language ("9–13 בנובמבר 2026"), from the
  // Monday it is filed under. Empty when the browser can't format date ranges.
  window.MP_WEEK = function (weekOf) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(weekOf || "")) return "";
    var p = weekOf.split("-"), y = +p[0], m = +p[1] - 1, d = +p[2];
    var f = new Intl.DateTimeFormat(LOCALE, { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });
    return f.formatRange ? f.formatRange(new Date(Date.UTC(y, m, d)), new Date(Date.UTC(y, m, d + 4))) : "";
  };

  // SPDR sector funds by symbol (names in docs/hebrew.md).
  var SECTORS_HE = {
    XLK: "טכנולוגיה", XLF: "פיננסים", XLY: "צריכה מחזורית", XLC: "שירותי תקשורת", XLV: "בריאות",
    XLI: "תעשייה", XLP: "צריכה בסיסית", XLE: "אנרגיה", XLU: "תשתיות", XLRE: "נדל״ן", XLB: "חומרי גלם",
    SOXX: "שבבים"
  };
  window.MP_SECTOR = function (symbol, name) { return HE && SECTORS_HE[symbol] ? SECTORS_HE[symbol] : name; };

  // CNN Fear & Greed ratings arrive in lower case ("extreme fear").
  var RATINGS_HE = { "extreme fear": "פחד קיצוני", "fear": "פחד", "neutral": "ניטרלי", "greed": "חמדנות", "extreme greed": "חמדנות קיצונית" };
  window.MP_RATING = function (r) {
    r = String(r || "").trim();
    if (!r) return "";
    return HE ? RATINGS_HE[r.toLowerCase()] || r : r.replace(/^./, function (c) { return c.toUpperCase(); });
  };

  // Insider titles from SEC filings ("President and CEO", "EVP, Chief Financial Officer").
  // Each part is translated; a vice-president rank is dropped when a real title follows it.
  // A title with any part we don't know stays in English rather than half-translated.
  var ROLE_PARTS = {
    "director": "דירקטור", "10% owner": "בעל 10% מהמניות", "ten percent owner": "בעל 10% מהמניות",
    "ceo": "מנכ״ל", "chief executive officer": "מנכ״ל", "cfo": "סמנכ״ל כספים", "chief financial officer": "סמנכ״ל כספים",
    "coo": "סמנכ״ל תפעול", "chief operating officer": "סמנכ״ל תפעול", "cto": "סמנכ״ל טכנולוגיות", "chief technology officer": "סמנכ״ל טכנולוגיות",
    "president": "נשיא", "group president": "נשיא חטיבה", "chairman": "יו״ר", "chair": "יו״ר", "chairperson": "יו״ר", "chairwoman": "יו״ר",
    "chairman of the board": "יו״ר הדירקטוריון", "chair of the board": "יו״ר הדירקטוריון", "executive chairman": "יו״ר פעיל",
    "executive chair": "יו״ר פעיל", "executive chair of the board": "יו״ר פעיל", "co-chairman": "יו״ר משותף", "vice chairman": "סגן יו״ר",
    "evp": "סמנכ״ל בכיר", "executive vice president": "סמנכ״ל בכיר", "svp": "סמנכ״ל בכיר", "senior vice president": "סמנכ״ל בכיר",
    "vp": "סמנכ״ל", "vice president": "סמנכ״ל", "chief legal officer": "יועץ משפטי ראשי", "general counsel": "יועץ משפטי", "gc": "יועץ משפטי",
    "secretary": "מזכיר החברה", "corporate secretary": "מזכיר החברה", "chief risk officer": "מנהל סיכונים ראשי",
    "chief investment officer": "מנהל השקעות ראשי", "chief people officer": "סמנכ״ל משאבי אנוש", "chief human resources officer": "סמנכ״ל משאבי אנוש",
    "chief product officer": "סמנכ״ל מוצר", "chief accounting officer": "חשב ראשי", "principal accounting officer": "חשב ראשי",
    "chief marketing officer": "סמנכ״ל שיווק", "chief commercial officer": "סמנכ״ל מסחרי", "chief information officer": "סמנכ״ל מערכות מידע",
    "chief strategy officer": "סמנכ״ל אסטרטגיה", "chief revenue officer": "סמנכ״ל הכנסות", "chief scientific officer": "מדען ראשי",
    "chief medical officer": "מנהל רפואי ראשי", "officer": "נושא משרה", "founder": "מייסד", "co-founder": "מייסד שותף"
  };
  var VP_RANKS = { "evp": 1, "executive vice president": 1, "svp": 1, "senior vice president": 1, "vp": 1, "vice president": 1 };
  window.MP_ROLE = function (role) {
    role = String(role || "").trim();
    if (!HE || !role) return role;
    var parts = role.replace(/&/g, " and ").split(/\s*(?:,|;|\/|\s-\s|\band\b)\s*/i)
      .map(function (p) { return p.trim().toLowerCase().replace(/\.$/, ""); })
      .filter(Boolean);
    var core = parts.filter(function (p) { return !VP_RANKS[p]; });
    if (core.length && core.length < parts.length) parts = core;
    var out = [];
    for (var i = 0; i < parts.length; i++) {
      var t = ROLE_PARTS[parts[i]];
      if (!t) return role;
      if (out.indexOf(t) < 0) out.push(t);
    }
    return out.length === 1 ? out[0] : out.slice(0, -1).join(", ") + " ו" + out[out.length - 1];
  };

  // ---------- Day / night edition ----------
  var KEY = "mp-theme";
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
    btn.innerHTML = ICONS[t] + "<span>" + (t === "night" ? L("Night edition", "מהדורת לילה") : L("Day edition", "מהדורת יום")) + "</span>";
    btn.setAttribute("aria-label", t === "night" ? L("Switch to the day edition", "מעבר למהדורת היום") : L("Switch to the night edition", "מעבר למהדורת הלילה"));
  }

  // ---------- Page text ----------
  // Fixed Hebrew text sits next to the English in the page: data-he (text), data-he-html (markup),
  // data-he-label (aria-label), data-he-title (title). Pages call MP_APPLY() at the top of their
  // script so their own code finds the Hebrew elements; DOMContentLoaded calls it otherwise.
  var applied = false;
  window.MP_APPLY = function () {
    if (applied) return;
    applied = true;
    if (HE) {
      var els = document.querySelectorAll("[data-he],[data-he-html],[data-he-label],[data-he-title]");
      for (var i = 0; i < els.length; i++) {
        var el = els[i];
        if (el.hasAttribute("data-he-html")) el.innerHTML = window.MP_BIDI(el.getAttribute("data-he-html"));
        else if (el.hasAttribute("data-he")) {
          if (el.tagName === "META") el.setAttribute("content", el.getAttribute("data-he"));
          else if (el.tagName === "TITLE") el.textContent = el.getAttribute("data-he");
          else el.textContent = window.MP_BIDI(el.getAttribute("data-he"));
        }
        if (el.hasAttribute("data-he-label")) el.setAttribute("aria-label", el.getAttribute("data-he-label"));
        if (el.hasAttribute("data-he-title")) el.setAttribute("title", el.getAttribute("data-he-title"));
      }
    }

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

    // The language button names the other language in that language.
    var lb = document.getElementById("lang-btn");
    if (lb) {
      var other = HE ? "en" : "he";
      lb.innerHTML = '<span lang="' + other + '">' + (HE ? "English" : "עברית") + '</span><span class="visually-hidden">' + (HE ? " (אנגלית)" : " (Hebrew)") + "</span>";
      lb.addEventListener("click", function () {
        var ok = true;
        try { localStorage.setItem(LANG_KEY, other); } catch (e) { ok = false; }
        var u = new URL(location.href);
        if (ok) u.searchParams.delete("lang"); else u.searchParams.set("lang", other);
        if (u.href === location.href) location.reload(); else location.replace(u.href);
      });
    }

    // Without storage the language only travels in the address, so carry it to the other pages.
    if (!storageOk && urlLang) {
      var links = document.querySelectorAll('a[href]');
      for (var j = 0; j < links.length; j++) {
        var href = links[j].getAttribute("href");
        if (!/^[\w-]+\.html(\?[^#]*)?(#.*)?$/.test(href)) continue;
        var u2 = new URL(href, location.href);
        u2.searchParams.set("lang", urlLang);
        links[j].setAttribute("href", u2.pathname.split("/").pop() + u2.search + u2.hash);
      }
    }

    var d = document.getElementById("today-date");
    if (d && !d.textContent) {
      d.textContent = new Date().toLocaleDateString(LOCALE, { weekday: "long", month: "long", day: "numeric", year: "numeric" });
    }
    root.classList.remove("i18n-pending");
  };
  document.addEventListener("DOMContentLoaded", window.MP_APPLY);
})();

// Section jump bar: ink the chip for the section in view and keep it visible in the
// swipeable bar on phones. Pages call MP_JUMP(nav) once the sections exist. Works in both
// directions: the bar scrolls by the chip's measured overflow, not by scrollLeft positions.
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
      var n = nav.getBoundingClientRect(), a = active.getBoundingClientRect();
      if (a.left < n.left + 16) nav.scrollLeft -= n.left + 16 - a.left;
      else if (a.right > n.right - 16) nav.scrollLeft += a.right - (n.right - 16);
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
