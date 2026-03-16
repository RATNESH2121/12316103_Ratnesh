/* ─────────────────────────────────────────────────────────────
   WealthBalance — Portfolio Rebalancing App
   app.js — All frontend logic
   ───────────────────────────────────────────────────────────── */

let currentClientId = 'C001';
let rebalanceData = null;  // latest rebalance result
let modelFundsOriginal = [];  // for reset

// ─── Init ─────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  loadClients();
  setupNav();
  document.getElementById('clientSelect').addEventListener('change', (e) => {
    currentClientId = e.target.value;
    loadCurrentScreen();
  });
});

function setupNav() {
  document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', function (e) {
      e.preventDefault();
      document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
      this.classList.add('active');
      const screen = this.dataset.screen;
      showScreen(screen);
    });
  });
}

function showScreen(name) {
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  document.getElementById('screen-' + name).classList.add('active');
  if (name === 'dashboard') loadRebalance();
  if (name === 'holdings') loadHoldings();
  if (name === 'history') loadHistory();
  if (name === 'edit-plan') loadEditPlan();
}

function loadCurrentScreen() {
  const active = document.querySelector('.nav-item.active');
  if (active) showScreen(active.dataset.screen);
}

// ─── Helpers ──────────────────────────────────────────────────────────────

function fmt(n) {
  if (n === null || n === undefined) return '—';
  return '₹ ' + Math.abs(Math.round(n)).toLocaleString('en-IN');
}

function fmtPct(n) {
  if (n === null || n === undefined) return '—';
  return n.toFixed(1) + '%';
}

function showToast(msg, type = 'success') {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = 'toast ' + type;
  setTimeout(() => { t.className = 'toast hidden'; }, 3500);
}

// ─── Load Clients ──────────────────────────────────────────────────────────

async function loadClients() {
  const res = await fetch('/api/clients/');
  const data = await res.json();
  const sel = document.getElementById('clientSelect');
  sel.innerHTML = '';
  data.clients.forEach(c => {
    const opt = document.createElement('option');
    opt.value = c.client_id;
    opt.textContent = c.client_name;
    if (c.client_id === 'C001') opt.selected = true;
    sel.appendChild(opt);
  });
  currentClientId = sel.value;
  loadRebalance();
}

// ─── Screen 1: Rebalancing Dashboard ──────────────────────────────────────

async function loadRebalance() {
  const tbody = document.getElementById('rebalanceTbody');
  tbody.innerHTML = '<tr><td colspan="7" class="loading-cell">Computing recommendations...</td></tr>';

  const res = await fetch(`/api/rebalance/?client_id=${currentClientId}`);
  rebalanceData = await res.json();

  // Update summary cards
  document.getElementById('cardTotal').textContent = fmt(rebalanceData.total_portfolio);
  document.getElementById('cardBuy').textContent = fmt(rebalanceData.total_to_buy);
  document.getElementById('cardSell').textContent = fmt(rebalanceData.total_to_sell);

  const fresh = rebalanceData.net_cash_needed;
  const freshEl = document.getElementById('cardFresh');
  freshEl.textContent = fresh >= 0 ? fmt(fresh) : ('- ' + fmt(Math.abs(fresh)));
  freshEl.style.color = fresh >= 0 ? 'var(--review-color)' : 'var(--buy-color)';

  // Build table
  tbody.innerHTML = '';
  rebalanceData.funds.forEach(f => {
    const action = f.action;
    const rowClass = { BUY: 'row-buy', SELL: 'row-sell', REVIEW: 'row-review', HOLD: 'row-hold' }[action] || '';
    const badgeClass = { BUY: 'badge-buy', SELL: 'badge-sell', REVIEW: 'badge-review', HOLD: 'badge-hold' }[action] || '';
    const icon = { BUY: '▲', SELL: '▼', REVIEW: '⚠', HOLD: '━' }[action] || '';

    let driftHtml = '—';
    if (f.drift !== null) {
      const driftClass = f.drift > 0 ? 'drift-positive' : (f.drift < 0 ? 'drift-negative' : 'drift-zero');
      const driftSign = f.drift > 0 ? '+' : '';
      driftHtml = `<span class="${driftClass}">${driftSign}${f.drift.toFixed(1)}%</span>`;
    }

    let amountHtml = '—';
    if (action === 'BUY') amountHtml = `<span class="amount-buy">+ ${fmt(f.amount)}</span>`;
    if (action === 'SELL') amountHtml = `<span class="amount-sell">- ${fmt(f.amount)}</span>`;
    if (action === 'REVIEW') amountHtml = `<span class="amount-review">${fmt(f.current_value)}</span>`;
    if (action === 'HOLD') amountHtml = `<span style="color:var(--text-muted)">${fmt(f.amount)}</span>`;

    const assetClass = f.asset_class || 'N/A';

    const tr = document.createElement('tr');
    tr.className = rowClass;
    tr.innerHTML = `
      <td style="font-weight:600">${f.fund_name}</td>
      <td><span class="asset-tag">${assetClass}</span></td>
      <td>${f.target_pct !== null ? fmtPct(f.target_pct) : '<span style="color:var(--text-muted)">—</span>'}</td>
      <td>${fmtPct(f.current_pct)}</td>
      <td>${driftHtml}</td>
      <td><span class="badge ${badgeClass}">${icon} ${action}</span></td>
      <td>${amountHtml}</td>
    `;
    tbody.appendChild(tr);
  });
}

// ─── Save Recommendation ───────────────────────────────────────────────────

async function saveRecommendation() {
  if (!rebalanceData) return;

  const btn = document.getElementById('btnSave');
  btn.disabled = true;
  btn.textContent = 'Saving...';

  try {
    const payload = {
      client_id: currentClientId,
      total_portfolio: rebalanceData.total_portfolio,
      total_to_buy: rebalanceData.total_to_buy,
      total_to_sell: rebalanceData.total_to_sell,
      net_cash_needed: rebalanceData.net_cash_needed,
      funds: rebalanceData.funds,
    };

    const res = await fetch('/api/save_session/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (res.ok) {
      showToast('✅ Recommendation saved to history!', 'success');
    } else {
      showToast('❌ Failed to save. Please try again.', 'error');
    }
  } catch (e) {
    showToast('❌ Network error. Please try again.', 'error');
  }

  btn.disabled = false;
  btn.innerHTML = '<span>💾</span> Save Recommendation';
}

// ─── Screen 2: Holdings ────────────────────────────────────────────────────

async function loadHoldings() {
  const tbody = document.getElementById('holdingsTbody');
  tbody.innerHTML = '<tr><td colspan="4" class="loading-cell">Loading holdings...</td></tr>';

  const res = await fetch(`/api/holdings/?client_id=${currentClientId}`);
  const data = await res.json();

  tbody.innerHTML = '';
  data.holdings.forEach(h => {
    const inPlanHtml = h.is_model_fund
      ? '<span class="in-plan-yes">✅ Yes</span>'
      : '<span class="in-plan-no">⚠ No — Needs Review</span>';

    const tr = document.createElement('tr');
    tr.className = h.is_model_fund ? '' : 'row-review';
    tr.innerHTML = `
      <td style="color:var(--text-muted);font-family:monospace">${h.fund_id}</td>
      <td style="font-weight:600">${h.fund_name}</td>
      <td style="font-weight:700;color:var(--accent-blue)">${fmt(h.current_value)}</td>
      <td>${inPlanHtml}</td>
    `;
    tbody.appendChild(tr);
  });

  document.getElementById('holdingsTotal').textContent = fmt(data.total);
}

// ─── Screen 3: History ────────────────────────────────────────────────────

async function loadHistory() {
  const container = document.getElementById('historyContainer');
  container.innerHTML = '<p class="empty-state">Loading history...</p>';

  const res = await fetch(`/api/history/?client_id=${currentClientId}`);
  const data = await res.json();

  if (data.sessions.length === 0) {
    container.innerHTML = '<p class="empty-state">No history yet. Save a recommendation from the Rebalancing screen first.</p>';
    return;
  }

  container.innerHTML = '';
  data.sessions.forEach(s => {
    const statusClass = {
      'PENDING': 'status-pending',
      'APPLIED': 'status-applied',
      'DISMISSED': 'status-dismissed',
    }[s.status] || 'status-pending';

    const actionsHtml = s.status === 'PENDING' ? `
      <button class="btn btn-sm btn-applied"   onclick="updateStatus(${s.session_id}, 'APPLIED')">✅ Mark Applied</button>
      <button class="btn btn-sm btn-dismissed" onclick="updateStatus(${s.session_id}, 'DISMISSED')">✖ Dismiss</button>
    ` : `
      <button class="btn btn-sm btn-secondary" onclick="updateStatus(${s.session_id}, 'PENDING')">↩ Reset to Pending</button>
    `;

    const card = document.createElement('div');
    card.className = 'history-card';
    card.id = `hist-card-${s.session_id}`;
    card.innerHTML = `
      <div class="history-card-header">
        <div>
          <div class="history-date">📅 ${s.created_at}</div>
          <div class="history-meta">Session #${s.session_id} · ${currentClientId}</div>
        </div>
        <span class="status-badge ${statusClass}">${s.status}</span>
      </div>
      <div class="history-stats">
        <div class="hist-stat">
          <div class="hist-stat-label">Portfolio Value</div>
          <div class="hist-stat-val" style="color:var(--accent-blue)">${fmt(s.portfolio_value)}</div>
        </div>
        <div class="hist-stat">
          <div class="hist-stat-label">Total BUY</div>
          <div class="hist-stat-val" style="color:var(--buy-color)">${fmt(s.total_to_buy)}</div>
        </div>
        <div class="hist-stat">
          <div class="hist-stat-label">Total SELL</div>
          <div class="hist-stat-val" style="color:var(--sell-color)">${fmt(s.total_to_sell)}</div>
        </div>
        <div class="hist-stat">
          <div class="hist-stat-label">Fresh Money</div>
          <div class="hist-stat-val" style="color:var(--review-color)">${fmt(s.net_cash_needed)}</div>
        </div>
      </div>
      <div class="history-actions">${actionsHtml}</div>
    `;
    container.appendChild(card);
  });
}

async function updateStatus(sessionId, status) {
  const res = await fetch('/api/update_status/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, status }),
  });

  if (res.ok) {
    showToast(`Session #${sessionId} marked as ${status}`, 'success');
    await loadHistory();
  } else {
    showToast('Failed to update status', 'error');
  }
}

// ─── Screen 4: Edit Plan ────────────────────────────────────────────────────

async function loadEditPlan() {
  const tbody = document.getElementById('editPlanTbody');
  tbody.innerHTML = '<tr><td colspan="4" class="loading-cell">Loading plan...</td></tr>';
  hidePlanMsg();

  const res = await fetch('/api/model_funds/');
  const data = await res.json();
  modelFundsOriginal = data.funds;

  renderEditPlanTable(data.funds);
}

function renderEditPlanTable(funds) {
  const tbody = document.getElementById('editPlanTbody');
  tbody.innerHTML = '';

  funds.forEach(f => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td style="color:var(--text-muted);font-family:monospace">${f.fund_id}</td>
      <td style="font-weight:600">${f.fund_name}</td>
      <td>${f.asset_class}</td>
      <td>
        <input class="plan-input" type="number" min="0" max="100" step="0.5"
               id="pct-${f.fund_id}" value="${f.allocation_pct}"
               oninput="updatePlanSum()" />
        <span style="color:var(--text-muted);margin-left:4px">%</span>
      </td>
    `;
    tbody.appendChild(tr);
  });

  updatePlanSum();
}

function updatePlanSum() {
  let total = 0;
  document.querySelectorAll('.plan-input').forEach(inp => {
    const v = parseFloat(inp.value) || 0;
    total += v;
  });

  const display = document.getElementById('planSumDisplay');
  display.textContent = total.toFixed(1) + '%';
  if (Math.abs(total - 100) < 0.05) {
    display.className = 'sum-ok';
  } else {
    display.className = 'sum-err';
  }
}

function resetPlanInputs() {
  renderEditPlanTable(modelFundsOriginal);
  hidePlanMsg();
}

async function savePlan() {
  hidePlanMsg();
  const updates = [];
  let total = 0;

  document.querySelectorAll('.plan-input').forEach(inp => {
    const fundId = inp.id.replace('pct-', '');
    const pct = parseFloat(inp.value) || 0;
    total += pct;
    updates.push({ fund_id: fundId, allocation_pct: pct });
  });

  if (Math.abs(total - 100) > 0.05) {
    showPlanMsg(`❌ Allocation sum is ${total.toFixed(1)}% — must be exactly 100%`, 'error');
    return;
  }

  const btn = document.getElementById('btnSavePlan');
  btn.disabled = true;
  btn.textContent = 'Saving...';

  try {
    const res = await fetch('/api/update_model_funds/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ funds: updates }),
    });

    const result = await res.json();

    if (res.ok) {
      showPlanMsg('Plan saved! Switching to Rebalancing screen with updated recommendations...', 'success');
      showToast('Model portfolio updated! Recalculating...', 'success');
      // Reload original so Reset works correctly
      modelFundsOriginal = updates.map(u => {
        const mf = modelFundsOriginal.find(f => f.fund_id === u.fund_id);
        return { ...mf, allocation_pct: u.allocation_pct };
      });
      rebalanceData = null;

      // ← KEY SPEC REQUIREMENT: auto-navigate to Screen 1 with updated recommendations
      setTimeout(() => {
        document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
        document.querySelector('[data-screen="dashboard"]').classList.add('active');
        showScreen('dashboard');
      }, 800);
    } else {
      showPlanMsg(`❌ ${result.error}`, 'error');
    }
  } catch (e) {
    showPlanMsg('❌ Network error. Please try again.', 'error');
  }

  btn.disabled = false;
  btn.innerHTML = '<span>💾</span> Save & Recalculate';
}

function showPlanMsg(msg, type) {
  const el = document.getElementById('planMsg');
  el.textContent = msg;
  el.className = 'plan-message ' + type;
}

function hidePlanMsg() {
  document.getElementById('planMsg').className = 'plan-message hidden';
}
