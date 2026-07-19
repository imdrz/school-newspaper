// Flipbook viewer.
//
// This is the ONLY file tied to StPageFlip. It reads the generic manifest the
// Python service produced and hands the page-image URLs to the library. If you
// ever switch flipbook libraries, this is the file you rewrite — nothing on the
// server changes, because the manifest is library-agnostic.

(function () {
  // The page URL is /view/<issueId> — grab the id from the path.
  const issueId = window.location.pathname.split("/").pop();
  const base = `/data/issues/${issueId}`;

  const flipbookEl = document.getElementById("flipbook");
  const pageLabel = document.getElementById("page-label");

  async function start() {
    // 1. Load the manifest the server wrote.
    const manifest = await fetch(`${base}/manifest.json`).then((r) => r.json());

    // 2. Turn each page's relative image path into a full URL.
    const imageUrls = manifest.pages.map((p) => `${base}/${p.image}`);

    // 3. Work out a page size that fits the screen while keeping the PDF's
    //    aspect ratio (manifest gives us the rendered pixel size).
    const aspect = manifest.page_height / manifest.page_width;
    const targetWidth = Math.min(480, window.innerWidth / 2 - 40);
    const targetHeight = targetWidth * aspect;

    // 4. Build the flipbook. `St` is the global exposed by page-flip.browser.js.
    const pageFlip = new St.PageFlip(flipbookEl, {
      width: targetWidth,
      height: targetHeight,
      size: "stretch",
      minWidth: 200,
      maxWidth: 1000,
      minHeight: 300,
      maxHeight: 1500,
      maxShadowOpacity: 0.5,
      showCover: true,           // treat page 1 as a single cover
      mobileScrollSupport: false,
    });

    pageFlip.loadFromImages(imageUrls);

    // 5. Keep the "page X of N" label in sync.
    //
    // A flip is animated, so reading the page index right after calling
    // flipNext() gives a stale value. Instead we listen to the library's
    // "flip" event, whose `e.data` is the page index AFTER the flip settles.
    // On wide screens StPageFlip shows two pages at once (a spread), so the
    // number is the left-hand page of the spread you're looking at.
    const total = pageFlip.getPageCount();
    function setLabel(pageIndex) {
      pageLabel.textContent = `Page ${pageIndex + 1} of ${total}`;
    }
    setLabel(0); // the book always opens on the first page
    pageFlip.on("flip", (e) => setLabel(e.data));

    // 6. Wire up the toolbar buttons and arrow keys.
    document.getElementById("prev").onclick = () => pageFlip.flipPrev();
    document.getElementById("next").onclick = () => pageFlip.flipNext();
    window.addEventListener("keydown", (e) => {
      if (e.key === "ArrowLeft") pageFlip.flipPrev();
      if (e.key === "ArrowRight") pageFlip.flipNext();
    });
  }

  start().catch((err) => {
    pageLabel.textContent = "Could not load this issue.";
    console.error(err);
  });
})();
