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
      userPortrait: single,
      maxShadowOpacity: 0.5,
      showCover: true,
      mobileScrollSupport: false,
    });

    pageFlip.loadFromImages(imageUrls);

    const total = pageFlip.getPageCount();
    const setLabel = (i) => { pageLabel.textContent = `Page ${i + 1} of ${total}`; };
    setLabel(startPage);
    pageFlip.on("flip", (e) => setLabel(e.data));

    if (startPage > 0) pageFlip.turnToPage(startPage);
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
  }

  start().catch((err) => {
    pageLabel.textContent = "Could not load this issue.";
    console.error(err);
  });
})();
