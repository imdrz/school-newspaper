// Flipbook viewer.
//
// This is the ONLY file tied to StPageFlip. It reads the generic manifest the
// Python service produced and hands the page-image URLs to the library. If you
// ever switch flipbook libraries, this is the file you rewrite — nothing on the
// server changes, because the manifest is library-agnostic.

(function () {
  // The page URL is /<school>/<editionId> — grab both segments from the path.
  const [school, editionId] = window.location.pathname.split("/").filter(Boolean);
  const base = `/data/schools/${school}/issues/${editionId}`;

  const stageEl = document.getElementById("stage");
  let flipbookEl = document.getElementById("flipbook");
  const pageLabel = document.getElementById("page-label");
  let pageFlip = null;

  // The toolbar's "home" link was rendered generically; point it at this
  // edition's school (which is where the upload form now lives).
  const homeLink = document.querySelector(".home");
  if (homeLink) {
    homeLink.href = `/${school}`;
    homeLink.textContent = "← Back to school";
  }

  // Fit a page into the stage with both dimensions
  // `aspect` is page_height / page_width. `availH / aspect` expresses the height limit as a width, so all three limits meet inside one Math.min.
  function fitPageSize(aspect) {
    const availW = stageEl.clientWidth - 24;
    const availH = stageEl.clientHeight - 24;
    const single = availW < 700;               // phones: ONE page, not a spread
    const perPageW = single ? availW : availW / 2;
    const width = Math.floor(Math.min(perPageW, availH / aspect, 1000));
    return { width, height: Math.floor(width * aspect), single };
  }

  function buildBook(manifest, imageUrls, startPage = 0) {
    const aspect = manifest.page_height / manifest.page_width;
    const { width, height, single } = fitPageSize(aspect);

    // StPageFlip.destroy() removes the whole #flipbook div from the page,
    // so on a rebuild it recreate a fresh one before building into it.
    if (pageFlip) {
      pageFlip.destroy();
      flipbookEl = document.createElement("div");
      flipbookEl.id = "flipbook";
      stageEl.appendChild(flipbookEl);
    }

    flipbookEl.style.width = (single ? width : 2 * width) + "px";
    flipbookEl.style.height = height + "px";

    pageFlip = new St.PageFlip(flipbookEl, {
      width,
      height,
      size: "fixed",
      usePortrait: single,
      maxShadowOpacity: 0.5,
      showCover: true,
      mobileScrollSupport: false,
    });

    const pageEls = imageUrls.map((url) => {
      const pageDiv = document.createElement("div");
      const img = document.createElement("img");
      img.src = url;
      pageDiv.appendChild(img);
      flipbookEl.appendChild(pageDiv);
      return pageDiv;
    });
    pageFlip.loadFromHTML(pageEls);

    const total = pageFlip.getPageCount();
    const setLabel = (i) => { pageLabel.textContent = `Page ${i + 1} of ${total}`; };
    setLabel(startPage);
    pageFlip.on("flip", (e) => setLabel(e.data));

    if (startPage > 0) pageFlip.turnToPage(startPage);
  }

  // Pinch-to-zoom overlay. Reads the current page(s) from the live pageFlip
  // and shows them fit-to-screen; every gesture edits (tx, ty, s) and re-applies
  // one transform. Pointer Events unify mouse/touch/pen: each finger is a
  // pointerId we keep in a Map — 1 down = pan, 2 down = pinch.
  function setupZoom(manifest, imageUrls) {
    const overlayEl = document.getElementById("zoom-overlay");
    const contentEl = document.getElementById("zoom-content");
    const pageW = manifest.page_width;
    const pageH = manifest.page_height;

    let open = false;
    let s = 1, tx = 0, ty = 0, minS = 1;   // the three numbers (+ fit floor)
    let contentW = 0, contentH = 0;
    const pointers = new Map();            // pointerId -> {x, y}
    let pinchPrev = 0;                     // finger gap on the previous move

    const apply = () => {
      contentEl.style.transform = `translate(${tx}px, ${ty}px) scale(${s})`;
    };

    // Anchored zoom: the point (px,py) stays fixed on screen as everything
    // scales around it. Its distance from the content's corner grows by the
    // same factor as the scale, so shift the content to compensate.
    function zoomAt(px, py, newScale) {
      newScale = Math.min(newScale, minS * 8);   // cap the zoom-in
      tx = px - (px - tx) * (newScale / s);
      ty = py - (py - ty) * (newScale / s);
      s = newScale;
    }

    // Keep the view sane: content bigger than the screen can't drift its edge
    // inward; content smaller than the screen stays centred.
    function clampPan() {
      const vw = innerWidth, vh = innerHeight;
      const cw = contentW * s, ch = contentH * s;
      tx = cw <= vw ? (vw - cw) / 2 : Math.min(0, Math.max(vw - cw, tx));
      ty = ch <= vh ? (vh - ch) / 2 : Math.min(0, Math.max(vh - ch, ty));
    }

    // Which page(s) to show: single-page → the current one; spread → the
    // current index is the LEFT page, so add its right partner — except the
    // cover, which always sits alone.
    function visiblePages() {
      const i = pageFlip.getCurrentPageIndex();
      const total = pageFlip.getPageCount();
      if (pageFlip.getOrientation() === "portrait" || i === 0) return [i];
      return i + 1 < total ? [i, i + 1] : [i];
    }

    function openZoom() {
      const pages = visiblePages();
      contentEl.innerHTML = "";
      pages.forEach((idx) => {
        const img = document.createElement("img");
        img.src = imageUrls[idx];
        img.width = pageW;
        img.height = pageH;
        contentEl.appendChild(img);
      });
      contentW = pageW * pages.length;
      contentH = pageH;
      minS = Math.min(innerWidth / contentW, innerHeight / contentH); // fit
      s = minS;
      tx = (innerWidth - contentW * s) / 2;
      ty = (innerHeight - contentH * s) / 2;
      apply();
      overlayEl.hidden = false;
      open = true;
    }

    function closeZoom() {
      overlayEl.hidden = true;
      open = false;
      pointers.clear();
      pinchPrev = 0;
    }

    const pts = () => [...pointers.values()];
    const dist = () => { const [a, b] = pts(); return Math.hypot(a.x - b.x, a.y - b.y); };
    const mid = () => { const [a, b] = pts(); return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 }; };

    addEventListener("pointerdown", (e) => {
      pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
      if (pointers.size === 2) {
        if (!open) openZoom();     // 2nd finger on the book → enter zoom mid-gesture
        pinchPrev = dist();
      }
    });

    addEventListener("pointermove", (e) => {
      const p = pointers.get(e.pointerId);
      if (!p) return;
      const dx = e.clientX - p.x, dy = e.clientY - p.y;
      p.x = e.clientX; p.y = e.clientY;
      if (!open) return;
      if (pointers.size === 1) {              // pan
        tx += dx; ty += dy;
        clampPan(); apply();
      } else if (pointers.size === 2 && pinchPrev > 0) {   // pinch
        const d = dist(), m = mid();
        zoomAt(m.x, m.y, s * (d / pinchPrev));
        clampPan(); apply();
        pinchPrev = d;
      }
    });

    function endPointer(e) {
      pointers.delete(e.pointerId);
      if (pointers.size < 2) pinchPrev = 0;
      if (open && pointers.size === 0 && s < minS * 0.98) closeZoom(); // pinched below fit → leave
    }
    addEventListener("pointerup", endPointer);
    addEventListener("pointercancel", endPointer);

    // Desktop: wheel zooms at the cursor, double-click toggles fit ↔ 2.5×.
    overlayEl.addEventListener("wheel", (e) => {
      if (!open) return;
      e.preventDefault();
      zoomAt(e.clientX, e.clientY, Math.max(minS, s * Math.exp(-e.deltaY * 0.0015)));
      clampPan(); apply();
    }, { passive: false });
    overlayEl.addEventListener("dblclick", (e) => {
      zoomAt(e.clientX, e.clientY, s > minS * 1.2 ? minS : minS * 2.5);
      clampPan(); apply();
    });

    document.getElementById("zoom").onclick = openZoom;
    document.getElementById("zoom-close").onclick = closeZoom;
    addEventListener("keydown", (e) => { if (e.key === "Escape" && open) closeZoom(); });
  }


  async function start() {
    const manifest = await fetch(`${base}/manifest.json`).then((r) => r.json());
    const imageUrls = manifest.pages.map((p) => `${base}/${p.image}`);

    buildBook(manifest, imageUrls);

    document.getElementById("prev").onclick = () => pageFlip.flipPrev();
    document.getElementById("next").onclick = () => pageFlip.flipNext();
    window.addEventListener("keydown", (e) => {
      if (e.key === "ArrowLeft") pageFlip.flipPrev();
      if (e.key === "ArrowRight") pageFlip.flipNext();
    });

    // rebuild book on window resize, but only after the user stops resizing for 150ms
    let resizeTimer = null;
    window.addEventListener("resize", () => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(() => {
        buildBook(manifest, imageUrls, pageFlip.getCurrentPageIndex());
      }, 150);
    });

    setupZoom(manifest, imageUrls);
  }

  start().catch((err) => {
    pageLabel.textContent = "Could not load this issue.";
    console.error(err);
  });
})();
