// Tab switching
document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById('panel-' + tab.dataset.tab).classList.add('active');
  });
});

function switchTab(name) {
  document.querySelectorAll('.tab').forEach(t => {
    t.classList.toggle('active', t.dataset.tab === name);
  });
  document.querySelectorAll('.panel').forEach(p => {
    p.classList.toggle('active', p.id === 'panel-' + name);
  });
}

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

// Helper to render a field in the vehicle card
function vf(label, value) {
  return `<div class="v-field"><div class="v-label">${label}</div><div class="v-value">${value || '—'}</div></div>`;
}

// Store last lookup globally so "Proceed" can use it
let lastLookup = null;

// --- Vehicle Lookup (PolicyBazaar-style) ---
$('lookupBtn').addEventListener('click', async () => {
  const reg = $('lookup_reg').value.trim();
  const out = $('lookupResult');
  const src = $('lookupSource');
  if (!reg || reg.length < 6) { out.innerHTML = '<div class="empty">Enter a valid registration number (e.g. MH04AB1234).</div>'; return; }

  const btn = $('lookupBtn');
  btn.disabled = true; btn.innerHTML = '<span class="spinner"></span>Fetching from registry…';
  src.textContent = '';

  try {
    const res = await fetch(`/api/rc-lookup?reg=${encodeURIComponent(reg)}`);
    const data = await res.json();
    if (!data.success) { out.innerHTML = `<div class="empty">${data.error || 'Vehicle not found.'}</div>`; return; }

    lastLookup = data.data;
    const d = data.data;
    const icon = (d.vehicle_class || '').toLowerCase().includes('car') || (d.vehicle_class || '').toLowerCase().includes('motor car')
      ? '🚗' : (d.vehicle_class || '').toLowerCase().includes('scooter') ? '🛵' : '🏍️';

    src.innerHTML = data.source === 'mock'
      ? 'Demo mode — showing realistic mock data. Connect a live API to fetch real records.'
      : `Live data from <strong>${data.source}</strong>`;

    out.innerHTML = `
      <div class="v-card">
        <div class="v-card-header">
          <div class="v-card-icon">${icon}</div>
          <div>
            <div class="v-card-title">${d.maker_model || d.maker + ' ' + d.model}</div>
            <div class="v-card-subtitle">${d.registration_number} · ${d.vehicle_class || ''} · ${d.color || ''}</div>
          </div>
        </div>
        <div class="v-grid">
          ${vf('Owner', d.owner_name)}
          ${vf("Father's name", d.father_name)}
          ${vf('Registration date', d.registration_date)}
          ${vf('Manufacturing year', d.manufacturing_year)}
          ${vf('Fuel type', d.fuel_type)}
          ${vf('Seating capacity', d.seating_capacity)}
          ${vf('Chassis number', d.chassis_number)}
          ${vf('Engine number', d.engine_number)}
          ${vf('RTO', d.rto_name)}
          ${vf('State', d.state)}
          ${vf('Insurance company', d.insurance_company)}
          ${vf('Insurance valid till', d.insurance_valid_upto)}
          ${vf('Financer', d.financer)}
          ${vf('Vehicle age', d.vehicle_age_years ? d.vehicle_age_years + ' years' : '—')}
          ${vf('Fitness valid till', d.fitness_upto)}
        </div>
        <div class="v-actions">
          <button class="go" id="proceedBtn">Proceed to document verification →</button>
        </div>
      </div>`;

    // Bind proceed button
    $('proceedBtn').addEventListener('click', () => {
      if (lastLookup) {
        $('registration_number').value = lastLookup.registration_number || '';
        $('owner_name').value = lastLookup.owner_name || '';
        $('chassis_number').value = lastLookup.chassis_number || '';
        $('engine_number').value = lastLookup.engine_number || '';
        $('fuel_type').value = lastLookup.fuel_type || '';
      }
      switchTab('doc');
    });

  } catch (e) {
    out.innerHTML = '<div class="empty">Something went wrong. Try again.</div>';
  } finally {
    btn.disabled = false; btn.textContent = 'Fetch vehicle details';
  }
});

// Allow Enter key to trigger lookup
$('lookup_reg').addEventListener('keydown', e => {
  if (e.key === 'Enter') { e.preventDefault(); $('lookupBtn').click(); }
});

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

// --- Photo inspection ---
// Thumbnail preview
$('photo_files').addEventListener('change', () => {
  const preview = $('photoPreview');
  const files = $('photo_files').files;
  preview.innerHTML = '';
  for (let i = 0; i < Math.min(files.length, 10); i++) {
    const url = URL.createObjectURL(files[i]);
    preview.innerHTML += `<img class="photo-thumb" src="${url}" alt="Photo ${i+1}" />`;
  }
  if (files.length > 10) preview.innerHTML += `<span class="note">+${files.length - 10} more (only first 10 will be analyzed)</span>`;
});

function dmgPill(sev) {
  if (sev === 'none') return '<span class="pill p-good">None</span>';
  if (sev === 'minor') return '<span class="pill p-warn">Minor</span>';
  if (sev === 'moderate') return '<span class="pill p-bad">Moderate</span>';
  if (sev === 'severe') return '<span class="pill p-bad">Severe</span>';
  return '<span class="pill p-warn">Unknown</span>';
}

$('photoBtn').addEventListener('click', async () => {
  const files = $('photo_files').files;
  const out = $('photoResult');
  if (!files.length) { out.innerHTML = '<div class="empty">Please select at least one vehicle photo.</div>'; return; }

  const btn = $('photoBtn');
  btn.disabled = true; btn.innerHTML = '<span class="spinner"></span>Assessing condition…';

  const fd = new FormData();
  for (let i = 0; i < Math.min(files.length, 10); i++) fd.append('photos', files[i]);

  try {
    const res = await fetch('/api/analyze-photos', { method: 'POST', body: fd });
    const data = await res.json();
    if (data.error) { out.innerHTML = `<div class="empty">${data.error}</div>`; return; }

    const cards = data.photo_reports.map(p => {
      if (p.error) return `<div class="photo-item"><strong>Photo ${p.photo}</strong> — ${p.error}</div>`;
      const issues = p.quality_issues.length
        ? `<div class="note" style="margin-top:6px">${p.quality_issues.join(' · ')}</div>` : '';
      return `<div class="photo-item">
        <div class="photo-item-head">
          <strong>Photo ${p.photo}</strong>
          <span class="photo-angle">${p.estimated_angle}</span>
          ${p.usable ? '<span class="pill p-good">Usable</span>' : '<span class="pill p-warn">Low quality</span>'}
        </div>
        <div style="display:flex;gap:16px;font-size:12.5px;color:var(--ink-soft);">
          <span>Sharpness: ${p.sharpness}</span>
          <span>Brightness: ${p.brightness}</span>
          <span>Resolution: ${p.resolution}</span>
        </div>
        <div style="margin-top:8px;font-size:13px;">
          Damage: ${dmgPill(p.damage.severity)}
          <span style="margin-left:8px;color:var(--ink-soft);">${p.damage.details || ''}</span>
        </div>
        ${issues}
      </div>`;
    }).join('');

    out.innerHTML = `
      <span class="verdict ${verdictClass(data.recommendation)}">${verdictLabel(data.recommendation)}</span>
      <div style="margin:14px 0 6px;font-size:14px;color:var(--ink);font-weight:500;">${data.summary}</div>
      <div class="block-title">Quality: ${data.usable_photos}/${data.photos_analyzed} usable · Worst signal: ${data.worst_damage_signal}</div>
      <div class="block-title">Per-photo analysis</div>
      <div class="photo-row">${cards}</div>`;
  } catch (e) {
    out.innerHTML = '<div class="empty">Something went wrong. Try again.</div>';
  } finally {
    btn.disabled = false; btn.textContent = 'Assess vehicle condition';
  }
});

// --- Records ---
function fmtDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso + 'Z');
  return isNaN(d) ? iso : d.toLocaleString();
}

async function loadRecords() {
  const docOut = $('docRecords');
  const photoOut = $('photoRecords');
  docOut.innerHTML = '<div class="empty">Loading…</div>';
  photoOut.innerHTML = '<div class="empty">Loading…</div>';
  try {
    const res = await fetch('/api/records');
    const data = await res.json();
    if (data.error) { docOut.innerHTML = `<div class="empty">${data.error}</div>`; photoOut.innerHTML = ''; return; }

    if (!data.documents.length) {
      docOut.innerHTML = '<div class="empty">No document records yet.</div>';
    } else {
      docOut.innerHTML = `<table><thead><tr><th>ID</th><th>When</th><th>Reg. no.</th><th>Owner</th><th>Type</th><th>Confidence</th><th>Verdict</th></tr></thead><tbody>` +
        data.documents.map(d => `<tr>
          <td>${d.id}</td><td>${fmtDate(d.created_at)}</td>
          <td>${d.registration_number || '—'}</td><td>${d.owner_name || '—'}</td>
          <td>${d.document_type || '—'}</td><td>${d.confidence ?? '—'}%</td>
          <td>${verdictLabel(d.verdict)}</td></tr>`).join('') + `</tbody></table>`;
    }

    if (!data.photos || !data.photos.length) {
      photoOut.innerHTML = '<div class="empty">No photo inspection records yet.</div>';
    } else {
      photoOut.innerHTML = `<table><thead><tr><th>ID</th><th>When</th><th>Photos</th><th>Usable</th><th>Damage</th><th>Recommendation</th><th>Summary</th></tr></thead><tbody>` +
        data.photos.map(p => `<tr>
          <td>${p.id}</td><td>${fmtDate(p.created_at)}</td>
          <td>${p.photos_analyzed ?? '—'}</td><td>${p.usable_photos ?? '—'}</td>
          <td>${p.worst_damage_signal || '—'}</td>
          <td>${verdictLabel(p.recommendation)}</td>
          <td style="font-size:12px;max-width:200px;">${p.summary || '—'}</td></tr>`).join('') + `</tbody></table>`;
    }
  } catch (e) {
    docOut.innerHTML = '<div class="empty">Could not load records.</div>';
    photoOut.innerHTML = '';
  }
}

$('refreshBtn').addEventListener('click', loadRecords);
document.querySelector('[data-tab="records"]').addEventListener('click', loadRecords);
