// Tab switching
document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById('panel-' + tab.dataset.tab).classList.add('active');
  });
});

const $ = id => document.getElementById(id);

function verdictClass(v) {
  if (['AUTO_VERIFIED', 'LIKELY_INSURABLE'].includes(v)) return 'v-good';
  if (['FLAGGED', 'RECAPTURE_NEEDED'].includes(v)) return 'v-bad';
  return 'v-warn';
}
function verdictLabel(v) {
  return ({
    AUTO_VERIFIED: 'Auto-verified',
    NEEDS_REVIEW: 'Needs human review',
    FLAGGED: 'Flagged — manual check',
    LIKELY_INSURABLE: 'Likely insurable',
    NEEDS_HUMAN_REVIEW: 'Needs human review',
    RECAPTURE_NEEDED: 'Recapture needed',
  })[v] || v;
}
function statusPill(s) {
  if (s === 'MATCH') return '<span class="pill p-good">Match</span>';
  if (s === 'MISMATCH') return '<span class="pill p-bad">Mismatch</span>';
  return '<span class="pill p-warn">Not found</span>';
}

// --- Document verification ---
$('verifyBtn').addEventListener('click', async () => {
  const file = $('doc_file').files[0];
  const out = $('docResult');
  if (!file) { out.innerHTML = '<div class="empty">Please choose a document image first.</div>'; return; }

  const btn = $('verifyBtn');
  btn.disabled = true; btn.innerHTML = '<span class="spinner"></span>Reading document…';

  const fd = new FormData();
  fd.append('document', file);
  ['registration_number','chassis_number','engine_number','owner_name','fuel_type']
    .forEach(k => fd.append(k, $(k).value));

  try {
    const res = await fetch('/api/verify-document', { method: 'POST', body: fd });
    const data = await res.json();
    if (data.error) { out.innerHTML = `<div class="empty">${data.error}</div>`; return; }

    const v = data.verification;
    const rows = v.fields.map(f => `
      <tr><td>${f.field.replace(/_/g,' ')}</td>
      <td>${f.entered || '—'}</td>
      <td>${f.extracted || '—'}</td>
      <td>${statusPill(f.status)}</td></tr>`).join('');

    out.innerHTML = `
      <span class="verdict ${verdictClass(v.verdict)}">${verdictLabel(v.verdict)}</span>
      <div class="score-bar"><div class="score-fill" style="width:${v.confidence}%"></div></div>
      <div class="score-label">${v.confidence}% field match · ${v.matched}/${v.comparable} fields</div>
      <div class="block-title">Detected document type: ${data.document_type.type} (${data.document_type.confidence}%)</div>
      <div class="block-title">Field comparison</div>
      <table><thead><tr><th>Field</th><th>Entered</th><th>From document</th><th>Result</th></tr></thead>
      <tbody>${rows}</tbody></table>`;
  } catch (e) {
    out.innerHTML = `<div class="empty">Something went wrong. Try again.</div>`;
  } finally {
    btn.disabled = false; btn.textContent = 'Run verification';
  }
});

// --- Video analysis ---
$('analyzeBtn').addEventListener('click', async () => {
  const file = $('video_file').files[0];
  const out = $('videoResult');
  if (!file) { out.innerHTML = '<div class="empty">Please choose a video file first.</div>'; return; }

  const btn = $('analyzeBtn');
  btn.disabled = true; btn.innerHTML = '<span class="spinner"></span>Analyzing frames…';

  const fd = new FormData();
  fd.append('video', file);

  try {
    const res = await fetch('/api/analyze-video', { method: 'POST', body: fd });
    const data = await res.json();
    if (data.error) { out.innerHTML = `<div class="empty">${data.error}</div>`; return; }

    const rows = data.frame_reports.map(f => `
      <tr><td>#${f.frame}</td>
      <td>${f.sharpness}</td>
      <td>${f.brightness}</td>
      <td>${f.usable ? '<span class="pill p-good">Usable</span>' : '<span class="pill p-warn">Low quality</span>'}</td>
      <td>${f.damage_signal}</td></tr>`).join('');

    out.innerHTML = `
      <span class="verdict ${verdictClass(data.recommendation)}">${verdictLabel(data.recommendation)}</span>
      <div class="block-title">Capture quality: ${data.usable_frames}/${data.frames_analyzed} usable frames</div>
      <div class="block-title">Worst damage signal: ${data.worst_damage_signal}</div>
      <div class="block-title">Per-frame analysis</div>
      <table><thead><tr><th>Frame</th><th>Sharpness</th><th>Brightness</th><th>Quality</th><th>Damage</th></tr></thead>
      <tbody>${rows}</tbody></table>`;
  } catch (e) {
    out.innerHTML = `<div class="empty">Something went wrong. Try again.</div>`;
  } finally {
    btn.disabled = false; btn.textContent = 'Analyze video';
  }
});
