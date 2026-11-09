/*
  Galleries: previous / next, thumbnails, swipe on phones,
  and the fullscreen viewer (arrow keys, Esc to close).
*/
(function () {
  "use strict";

  var viewer = document.getElementById("viewer");
  if (!viewer) return;

  var vImg = viewer.querySelector(".viewer-img img");
  var vInfo = viewer.querySelector(".viewer-info");
  var vClose = viewer.querySelector(".viewer-close");
  var vPrev = viewer.querySelector("[data-viewer-prev]");
  var vNext = viewer.querySelector("[data-viewer-next]");

  var active = null;       // the gallery currently shown in the viewer
  var lastFocus = null;

  function pad(n) { return (n < 10 ? "0" : "") + n; }

  function preload(src) { var i = new Image(); i.src = src; }

  function swipe(el, onLeft, onRight) {
    var x0 = null, y0 = null;
    el.addEventListener("touchstart", function (e) {
      x0 = e.changedTouches[0].clientX; y0 = e.changedTouches[0].clientY;
    }, { passive: true });
    el.addEventListener("touchend", function (e) {
      if (x0 === null) return;
      var dx = e.changedTouches[0].clientX - x0;
      var dy = e.changedTouches[0].clientY - y0;
      x0 = null;
      if (Math.abs(dx) > 40 && Math.abs(dx) > Math.abs(dy)) { (dx < 0 ? onLeft : onRight)(); }
    }, { passive: true });
  }

  function Gallery(root) {
    this.root = root;
    this.items = JSON.parse(root.querySelector("script.gallery-data").textContent);
    this.title = root.getAttribute("data-title") || "";
    this.i = 0;
    this.img = root.querySelector(".stage img");
    this.num = root.querySelector(".counter b");
    this.thumbs = Array.prototype.slice.call(root.querySelectorAll(".thumb"));
    var self = this;

    var prev = root.querySelector("[data-prev]");
    var next = root.querySelector("[data-next]");
    if (prev) prev.addEventListener("click", function () { self.show(self.i - 1); });
    if (next) next.addEventListener("click", function () { self.show(self.i + 1); });
    root.querySelector(".fs-btn").addEventListener("click", function () { openViewer(self); });
    this.thumbs.forEach(function (t, k) {
      t.addEventListener("click", function (e) { e.preventDefault(); self.show(k); });
    });
    swipe(root.querySelector(".stage-wrap"), function () { self.show(self.i + 1); }, function () { self.show(self.i - 1); });
  }

  Gallery.prototype.show = function (k) {
    var n = this.items.length;
    this.i = ((k % n) + n) % n;
    var it = this.items[this.i];
    this.img.src = it.m;
    this.img.alt = it.alt;
    this.img.removeAttribute("width");
    this.img.removeAttribute("height");
    if (this.num) this.num.textContent = pad(this.i + 1);
    this.thumbs.forEach(function (t, j) { t.setAttribute("aria-current", j === this.i ? "true" : "false"); }, this);
    if (n > 1) preload(this.items[(this.i + 1) % n].m);
    if (active === this) renderViewer();
  };

  function renderViewer() {
    var it = active.items[active.i];
    vImg.src = it.f;
    vImg.alt = it.alt;
    vInfo.innerHTML = "";
    var b = document.createElement("b");
    b.textContent = pad(active.i + 1) + "/" + pad(active.items.length);
    vInfo.appendChild(b);
    vInfo.appendChild(document.createTextNode(active.title));
    var n = active.items.length;
    if (n > 1) preload(active.items[(active.i + 1) % n].f);
  }

  function openViewer(g) {
    active = g;
    lastFocus = document.activeElement;
    renderViewer();
    viewer.hidden = false;
    document.body.classList.add("viewer-open");
    vClose.focus();
    try {
      if (viewer.requestFullscreen) {
        var p = viewer.requestFullscreen();
        if (p && p.catch) p.catch(function () {});
      }
    } catch (e) { /* some phones (iPhone) don't allow it: the viewer still fills the window */ }
  }

  function closeViewer() {
    if (!active) return;
    active = null;
    viewer.hidden = true;
    vImg.removeAttribute("src");
    document.body.classList.remove("viewer-open");
    try {
      if (document.fullscreenElement && document.exitFullscreen) {
        var p = document.exitFullscreen();
        if (p && p.catch) p.catch(function () {});
      }
    } catch (e) {}
    if (lastFocus && lastFocus.focus) lastFocus.focus();
  }

  vClose.addEventListener("click", closeViewer);
  vPrev.addEventListener("click", function () { if (active) active.show(active.i - 1); });
  vNext.addEventListener("click", function () { if (active) active.show(active.i + 1); });
  swipe(viewer.querySelector(".viewer-main"),
    function () { if (active) active.show(active.i + 1); },
    function () { if (active) active.show(active.i - 1); });

  document.addEventListener("fullscreenchange", function () {
    if (!document.fullscreenElement && active) closeViewer();
  });

  document.addEventListener("keydown", function (e) {
    if (!active) return;
    if (e.key === "Escape") { e.preventDefault(); closeViewer(); }
    else if (e.key === "ArrowLeft") { e.preventDefault(); active.show(active.i - 1); }
    else if (e.key === "ArrowRight") { e.preventDefault(); active.show(active.i + 1); }
    else if (e.key === "Tab") {
      // keep keyboard focus inside the viewer while it is open
      var f = [vClose, vPrev, vNext];
      var k = f.indexOf(document.activeElement);
      e.preventDefault();
      f[(k + (e.shiftKey ? f.length - 1 : 1) + f.length) % f.length].focus();
    }
  });

  Array.prototype.forEach.call(document.querySelectorAll(".project-gallery"), function (el) {
    new Gallery(el);
  });
})();
