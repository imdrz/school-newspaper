// School page behaviour: the upload form and edition deletion.
// The school slug arrives through the DOM (<body data-school="…">), already
// escaped by Jinja — so there is no server-injected JavaScript in this file.
const school = document.body.dataset.school;

// --- Upload form -----------------------------------------------------------
const form = document.getElementById('upload-form');
if (form) {
  const statusEl = document.getElementById('status');
  const submitBtn = document.getElementById('submit');

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const fileInput = document.getElementById('file');
    if (!fileInput.files.length) return;

    submitBtn.disabled = true;
    statusEl.className = 'status';
    statusEl.textContent = 'Uploading and rendering…';

    const data = new FormData();
    data.append('file', fileInput.files[0]);
    data.append('title', document.getElementById('title').value);
    data.append('date', document.getElementById('date').value);

    try {
      const res = await fetch(`/api/schools/${school}/issues`, { method: 'POST', body: data });
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail || 'Upload failed');
      statusEl.textContent = `Done — ${body.page_count} pages. Opening…`;
      window.location.href = body.view_url;
    } catch (err) {
      statusEl.className = 'status status--error';
      statusEl.textContent = err.message;
      submitBtn.disabled = false;
    }
  });
}

// --- Delete edition (one delegated listener, not one per button) -----------
document.addEventListener('click', async (event) => {
  const btn = event.target.closest('[data-delete-id]');
  if (!btn) return;

  const { deleteId: id, deleteTitle: title } = btn.dataset;
  const typed = prompt(`Type the edition title to delete it permanently:\n\n${title}`);
  if (typed !== title) return;              // also covers Cancel (null)

  btn.disabled = true;
  const res = await fetch(`/api/schools/${school}/issues/${id}`, { method: 'DELETE' });
  if (res.ok) {
    location.reload();
  } else {
    btn.disabled = false;
    const body = await res.json().catch(() => ({}));
    alert(body.detail || 'Delete failed');
  }
});
