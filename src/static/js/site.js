/* IRM — site script: navigation, language menu, inquiry form, hero animation. */
(function () {
  "use strict";
  var doc = document;

  /* Legacy links from the old single-page site: /?lang=ja → /ja/, /#faq → /faq/ */
  try {
    if (location.pathname === "/") {
      var legacy = new URLSearchParams(location.search).get("lang");
      if (legacy && /^(de|fr|it|es|pt|zh|ja|ko)$/.test(legacy)) {
        location.replace("/" + legacy + "/");
        return;
      }
      var oldHash = {
        "#about": "/about/", "#capabilities": "/capabilities/", "#contact": "/contact/",
        "#faq": "/faq/", "#fibres": "/carbon-fiber/", "#fibers": "/carbon-fiber/",
        "#global": "/global-network/", "#polymers": "/materials/", "#recycling": "/sell-scrap/",
        "#trading": "/trading/"
      }[location.hash];
      if (oldHash) { location.replace(oldHash); return; }
    }
  } catch (e) { /* ignore */ }

  /* ── Dropdown menus (nav + language) ───────────────────────────── */
  var triggers = Array.prototype.slice.call(doc.querySelectorAll(".nav-trigger, .lang-btn"));
  function closeAll(except) {
    triggers.forEach(function (b) {
      if (b === except) return;
      b.setAttribute("aria-expanded", "false");
      var m = doc.getElementById(b.getAttribute("aria-controls"));
      if (m) m.hidden = true;
    });
  }
  triggers.forEach(function (btn) {
    var menu = doc.getElementById(btn.getAttribute("aria-controls"));
    if (!menu) return;
    btn.addEventListener("click", function (e) {
      e.stopPropagation();
      var open = btn.getAttribute("aria-expanded") === "true";
      closeAll(btn);
      btn.setAttribute("aria-expanded", String(!open));
      menu.hidden = open;
      if (!open) {
        var first = menu.querySelector("a");
        if (first && e.detail === 0) first.focus(); /* keyboard activation */
      }
    });
    menu.addEventListener("keydown", function (e) {
      if (e.key === "Escape") { btn.setAttribute("aria-expanded", "false"); menu.hidden = true; btn.focus(); }
    });
  });
  doc.addEventListener("click", function (e) {
    if (!e.target.closest(".nav-menu, .lang-menu")) closeAll(null);
  });
  doc.addEventListener("keydown", function (e) { if (e.key === "Escape") closeAll(null); });
  doc.addEventListener("focusin", function (e) {
    if (!e.target.closest(".nav-list > li, .lang")) closeAll(null);
  });

  /* ── Mobile panel ──────────────────────────────────────────────── */
  var toggle = doc.querySelector(".menu-toggle");
  var panel = doc.getElementById("mobile-panel");
  if (toggle && panel) {
    var setOpen = function (open) {
      toggle.setAttribute("aria-expanded", String(open));
      panel.classList.toggle("is-open", open);
      doc.body.classList.toggle("menu-open", open);
      toggle.querySelector(".i-open").toggleAttribute("hidden", open);
      toggle.querySelector(".i-close").toggleAttribute("hidden", !open);
      toggle.setAttribute("aria-label", open ? (toggle.dataset.close || "Close menu") : (toggle.dataset.open || "Menu"));
    };
    toggle.addEventListener("click", function () { setOpen(toggle.getAttribute("aria-expanded") !== "true"); });
    panel.addEventListener("click", function (e) { if (e.target.closest("a")) setOpen(false); });
    doc.addEventListener("keydown", function (e) { if (e.key === "Escape" && panel.classList.contains("is-open")) { setOpen(false); toggle.focus(); } });
    window.addEventListener("resize", function () { if (window.innerWidth > 1120) setOpen(false); });
  }

  /* ── Inquiry form ──────────────────────────────────────────────── */
  var form = doc.getElementById("inquiry-form");
  if (form && window.fetch && window.FormData) {
    var status = form.querySelector(".form-status");
    var submit = form.querySelector('button[type="submit"]');
    var label = submit ? submit.textContent : "";
    var MAX_BYTES = 10 * 1024 * 1024, MAX_FILES = 5;
    var show = function (msg, ok) { status.textContent = msg; status.className = "form-status " + (ok ? "is-ok" : "is-err"); };

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var invalid = [];
      Array.prototype.forEach.call(form.querySelectorAll("[required]"), function (el) {
        var bad = el.type === "checkbox" ? !el.checked : !el.value.trim() || (el.type === "email" && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(el.value.trim()));
        el.setAttribute("aria-invalid", bad ? "true" : "false");
        if (bad) invalid.push(el);
      });
      if (invalid.length) { show(form.dataset.errRequired, false); invalid[0].focus(); return; }

      var files = form.querySelector('input[type="file"]');
      if (files && files.files.length) {
        var total = 0;
        Array.prototype.forEach.call(files.files, function (f) { total += f.size; });
        if (files.files.length > MAX_FILES || total > MAX_BYTES) { show(form.dataset.errFiles, false); files.focus(); return; }
      }

      submit.disabled = true; submit.textContent = form.dataset.sending;
      status.textContent = ""; status.className = "form-status";
      fetch(form.action, { method: "POST", body: new FormData(form), headers: { Accept: "application/json" } })
        .then(function (r) { return r.json().catch(function () { return { ok: false }; }).then(function (j) { return { status: r.status, body: j }; }); })
        .then(function (res) {
          if (res.body && res.body.ok) {
            form.reset();
            show(form.dataset.ok, true);
            if (window.turnstile) { try { window.turnstile.reset(); } catch (e2) { /* ignore */ } }
          } else if (res.body && res.body.error === "files") {
            show(form.dataset.errFiles, false);
          } else {
            show(form.dataset.err, false);
          }
        })
        .catch(function () { show(form.dataset.err, false); })
        .then(function () { submit.disabled = false; submit.textContent = label; });
    });
  }

  /* ── Hero network animation ────────────────────────────────────── */
  var canvas = doc.querySelector(".hero-canvas");
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (canvas && canvas.getContext && !reduce) {
    var ctx = canvas.getContext("2d");
    var nodes = [], W = 0, H = 0, dpr = 1, running = false, raf = 0;
    var resize = function () {
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      W = canvas.offsetWidth; H = canvas.offsetHeight;
      canvas.width = Math.round(W * dpr); canvas.height = Math.round(H * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      var count = Math.round(Math.min(64, Math.max(24, (W * H) / 22000)));
      nodes = [];
      for (var i = 0; i < count; i++) {
        nodes.push({ x: Math.random() * W, y: Math.random() * H, vx: (Math.random() - 0.5) * 0.28, vy: (Math.random() - 0.5) * 0.28, r: Math.random() * 1.6 + 0.6, a: Math.random() * 0.6 + 0.25 });
      }
    };
    var draw = function () {
      ctx.clearRect(0, 0, W, H);
      var D = 130, i, j, n, m, dx, dy, d;
      for (i = 0; i < nodes.length; i++) {
        n = nodes[i]; n.x += n.vx; n.y += n.vy;
        if (n.x < 0 || n.x > W) n.vx *= -1;
        if (n.y < 0 || n.y > H) n.vy *= -1;
      }
      ctx.lineWidth = 0.6;
      for (i = 0; i < nodes.length; i++) {
        for (j = i + 1; j < nodes.length; j++) {
          n = nodes[i]; m = nodes[j]; dx = n.x - m.x; dy = n.y - m.y; d = Math.sqrt(dx * dx + dy * dy);
          if (d < D) { ctx.strokeStyle = "rgba(91,158,230," + ((1 - d / D) * 0.16).toFixed(3) + ")"; ctx.beginPath(); ctx.moveTo(n.x, n.y); ctx.lineTo(m.x, m.y); ctx.stroke(); }
        }
      }
      for (i = 0; i < nodes.length; i++) {
        n = nodes[i]; ctx.fillStyle = "rgba(91,158,230," + n.a.toFixed(2) + ")";
        ctx.beginPath(); ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2); ctx.fill();
      }
      if (running) raf = requestAnimationFrame(draw);
    };
    var start = function () { if (!running) { running = true; raf = requestAnimationFrame(draw); } };
    var stop = function () { running = false; cancelAnimationFrame(raf); };
    resize();
    window.addEventListener("resize", function () { resize(); });
    if ("IntersectionObserver" in window) {
      new IntersectionObserver(function (entries) { entries[0].isIntersecting ? start() : stop(); }).observe(canvas);
    } else { start(); }
    doc.addEventListener("visibilitychange", function () { doc.hidden ? stop() : start(); });
  }
})();
