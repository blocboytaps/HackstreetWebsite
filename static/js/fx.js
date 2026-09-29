/* =========================================================================
   Hackstreet — atmosphere & interaction layer
   Click sounds, door-transition sound + video, mouse-following compass,
   torchlight, and an ambient-music toggle. All motion/audio respects
   prefers-reduced-motion and degrades to plain navigation.
   ========================================================================= */
(function () {
  "use strict";

  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var STATIC = (document.currentScript && document.currentScript.dataset.static) || "/static/";
  if (STATIC.charAt(STATIC.length - 1) === "/") STATIC = STATIC.slice(0, -1);  // -> "/static"

  // ---- audio ----------------------------------------------------------
  function make(src, vol) {
    var a = new Audio(STATIC + src);
    a.volume = vol;
    a.preload = "auto";
    return a;
  }
  var sndClick = make("/audio/click.mp3", 0.5);
  var sndDoor  = make("/audio/door.mp3", 0.6);

  function play(a) {
    try { a.currentTime = 0; var p = a.play(); if (p) p.catch(function () {}); }
    catch (e) { /* autoplay blocked until a gesture — fine */ }
  }
  function click() { play(sndClick); }

  // ---- helpers --------------------------------------------------------
  function internalLink(el) {
    var a = el.closest && el.closest("a[href]");
    if (!a) return null;
    if (a.origin !== location.origin) return null;
    if (a.hasAttribute("download") || a.target === "_blank") return null;
    if (a.getAttribute("href").charAt(0) === "#") return null;
    return a;
  }

  // ---- click sound on every interactive control -----------------------
  document.addEventListener("pointerdown", function (e) {
    if (e.target.closest("button, a[href], input[type=submit], .marker")) click();
  }, { passive: true });

  // ---- door-sound + fade page transition for ordinary links -----------
  document.addEventListener("click", function (e) {
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey) return;
    var marker = e.target.closest(".marker");
    if (marker) return;                       // markers handled by the video below
    var a = internalLink(e.target);
    if (!a) return;
    if (reduce) return;                        // let it navigate immediately
    e.preventDefault();
    play(sndDoor);
    document.body.classList.add("page-exit");
    setTimeout(function () { window.location.href = a.href; }, 480);
  });

  // ---- door-sound on the "Speak" form submit --------------------------
  document.addEventListener("submit", function (e) {
    if (reduce) return;
    var form = e.target;
    if (form.dataset.fxDone) return;
    e.preventDefault();
    play(sndDoor);
    document.body.classList.add("page-exit");
    form.dataset.fxDone = "1";
    setTimeout(function () { form.submit(); }, 420);
  });

  // ---- DOOR VIDEO overlay when a map location is clicked --------------
  function doorVideoThen(href) {
    if (reduce) { window.location.href = href; return; }
    var ov = document.createElement("div");
    ov.className = "door-overlay";
    ov.innerHTML =
      '<video class="door-video" muted playsinline preload="auto">' +
      '<source src="' + STATIC + '/video/door.mp4" type="video/mp4"></video>';
    document.body.appendChild(ov);
    requestAnimationFrame(function () { ov.classList.add("show"); });
    var vid = ov.querySelector("video");
    var done = false;
    function go() { if (done) return; done = true; window.location.href = href; }
    play(sndDoor);
    var pr = vid.play(); if (pr) pr.catch(function () {});
    vid.addEventListener("ended", go);
    setTimeout(go, 3200);                       // safety net if the video stalls
  }

  var markers = document.querySelectorAll(".marker");
  markers.forEach(function (m) {
    m.addEventListener("click", function (e) {
      var href = m.getAttribute("href");
      if (!href) return;
      e.preventDefault();
      doorVideoThen(href);
    });
  });

  // ---- mouse-following compass (landing only) -------------------------
  var needle = document.getElementById("compass-needle");
  if (needle && !reduce) {
    var cx = 0, cy = 0, target = 0, cur = 0, raf = null;
    function measure() {
      var r = needle.getBoundingClientRect();
      cx = r.left + r.width / 2; cy = r.top + r.height / 2;
    }
    measure();
    window.addEventListener("resize", measure);
    window.addEventListener("scroll", measure, { passive: true });
    window.addEventListener("mousemove", function (e) {
      target = Math.atan2(e.clientY - cy, e.clientX - cx) * 180 / Math.PI + 90;
      if (!raf) raf = requestAnimationFrame(spin);
    });
    function spin() {
      raf = null;
      var d = ((target - cur + 540) % 360) - 180;  // shortest path
      cur += d * 0.18;
      needle.style.transform = "rotate(" + cur.toFixed(2) + "deg)";
      if (Math.abs(d) > 0.3) raf = requestAnimationFrame(spin);
    }
  }

  // ---- torchlight follows the cursor over the map ---------------------
  var frame = document.querySelector(".map-frame");
  if (frame && !reduce) {
    frame.addEventListener("pointermove", function (e) {
      var r = frame.getBoundingClientRect();
      frame.style.setProperty("--mx", ((e.clientX - r.left) / r.width * 100) + "%");
      frame.style.setProperty("--my", ((e.clientY - r.top) / r.height * 100) + "%");
      frame.classList.add("lit");
    });
    frame.addEventListener("pointerleave", function () { frame.classList.remove("lit"); });
  }

  // ---- ambient music toggle -------------------------------------------
  var toggle = document.getElementById("sound-toggle");
  if (toggle) {
    var theme = make("/audio/theme.mp3", 0.35);
    theme.loop = true;
    var on = false;
    try { on = localStorage.getItem("hs-ambient") === "1"; } catch (e) {}
    function paint() { toggle.setAttribute("aria-pressed", on ? "true" : "false");
      toggle.classList.toggle("on", on); }
    paint();
    toggle.addEventListener("click", function () {
      on = !on; paint();
      if (on) play(theme); else theme.pause();
      try { localStorage.setItem("hs-ambient", on ? "1" : "0"); } catch (e) {}
    });
  }
})();
