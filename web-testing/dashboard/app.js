/**
 * app.js -- ArchiTinder E2E Test Dashboard SPA
 * Vanilla JS, no build step.
 * Supports multi-persona viewing via data/runs.json manifest.
 */

(function () {
  'use strict';

  // -- State --
  let report = null;
  let feedback = null;
  let activeTab = 'steps';
  let expandedSteps = new Set();
  let perfSortKey = 'duration_ms';
  let perfSortAsc = false;

  // Multi-persona state
  let runs = [];           // Array from runs.json
  let activeRunId = null;  // Currently displayed run
  let reportsCache = {};   // { run_id: { report, feedback } }
  let selectorOpen = false;

  // -- Data Loading --

  async function loadData() {
    // Try multi-persona manifest first
    try {
      const manifestRes = await fetch('data/runs.json');
      if (manifestRes.ok) {
        const manifest = await manifestRes.json();
        runs = manifest.runs || [];
        if (runs.length > 0) {
          activeRunId = runs[runs.length - 1].run_id;
          await loadRun(activeRunId);
          return;
        }
      }
    } catch (_) { /* no manifest, fall back to single mode */ }

    // Fallback: load from data/latest/ (single persona mode)
    try {
      const [reportRes, feedbackRes] = await Promise.all([
        fetch('data/latest/report.json'),
        fetch('data/latest/feedback.json'),
      ]);
      if (reportRes.ok) report = await reportRes.json();
      if (feedbackRes.ok) feedback = await feedbackRes.json();
    } catch (_) { /* data not available */ }
    render();
  }

  async function loadRun(runId) {
    // Return cached data if available
    if (reportsCache[runId]) {
      report = reportsCache[runId].report;
      feedback = reportsCache[runId].feedback;
      activeRunId = runId;
      expandedSteps = new Set();
      render();
      return;
    }

    const basePath = runs.length ? `data/${runId}` : 'data/latest';
    try {
      const [rRes, fRes] = await Promise.all([
        fetch(`${basePath}/report.json`),
        fetch(`${basePath}/feedback.json`),
      ]);
      if (rRes.ok) report = await rRes.json();
      if (fRes.ok) feedback = await fRes.json();
      reportsCache[runId] = { report, feedback };
      activeRunId = runId;
      expandedSteps = new Set();
    } catch (_) { /* data not available */ }
    render();
  }

  // -- Data Path Helper --

  function dataPath() {
    if (runs.length && activeRunId) return `data/${activeRunId}`;
    return 'data/latest';
  }

  // -- Render --

  function render() {
    const app = document.getElementById('app');

    if (!report) {
      app.innerHTML = `
        <div class="no-data">
          <h3>No test data found</h3>
          <p>Run a test first: python web-testing/run.py</p>
          <p style="margin-top:8px;font-size:12px;color:#555">
            Looking for: data/runs.json or data/latest/report.json
          </p>
        </div>
      `;
      return;
    }

    app.innerHTML = `
      ${renderHeader()}
      ${renderSidebar()}
      <div class="main">
        ${renderTabNav()}
        <div class="tab-content">
          ${renderActiveTab()}
        </div>
      </div>
    `;

    attachEvents();
  }

  // -- Header --

  function renderHeader() {
    const status = feedback ? feedback.status : 'unknown';
    const runId = report.run_id || 'unknown';
    const duration = report.summary ? report.summary.total_duration_ms : 0;
    const personaIndex = runs.findIndex(r => r.run_id === activeRunId);
    const counter = runs.length > 1
      ? `<span class="persona-counter">${personaIndex + 1} / ${runs.length}</span>`
      : '';

    return `
      <div class="header">
        <div>
          <h1>ArchiTinder E2E Test</h1>
          <span class="run-id">${runId} -- ${formatDuration(duration)}</span>
          ${counter}
        </div>
        <span class="status-badge ${status}">${status}</span>
      </div>
    `;
  }

  // -- Sidebar (Persona Panel) --

  function renderSidebar() {
    const p = report.persona || {};
    const prefs = p.taste_preferences || {};
    const summary = report.summary || {};

    // Persona selector (multi-persona mode)
    let selectorHtml = '';
    if (runs.length > 1) {
      selectorHtml = `
        <div class="persona-selector" data-action="toggle-selector">
          <div>
            <div class="persona-selector-name">${esc(p.name || 'Unknown')}</div>
            <div class="persona-selector-meta">${esc(p.occupation || '')} -- Age ${p.age || '?'}</div>
          </div>
          <span class="persona-chevron">${selectorOpen ? '\u25B2' : '\u25BC'}</span>
        </div>
        ${selectorOpen ? `
          <div class="persona-dropdown">
            ${runs.map((r, i) => `
              <div class="persona-option ${r.run_id === activeRunId ? 'active' : ''}"
                   data-run-id="${r.run_id}">
                <span class="persona-option-index">${i + 1}</span>
                <div class="persona-option-info">
                  <span class="persona-option-name">${esc(r.persona_name)}</span>
                  <span class="persona-option-meta">${esc(r.occupation)}</span>
                </div>
                <span class="status-dot ${r.status}"></span>
              </div>
            `).join('')}
          </div>
        ` : ''}
      `;
    } else {
      selectorHtml = `
        <div class="persona-name">${esc(p.name || 'Unknown')}</div>
        <div class="persona-detail">${esc(p.occupation || '')} -- Age ${p.age || '?'}</div>
      `;
    }

    return `
      <div class="sidebar">
        <div class="persona-section">
          <h2>Persona</h2>
          ${selectorHtml}
        </div>

        <div class="persona-section">
          <h2>Search Query</h2>
          <div class="persona-query">"${esc(p.search_query || '')}"</div>
        </div>

        <div class="persona-section">
          <h2>Preferred Styles</h2>
          <div class="preference-tags">
            ${(prefs.preferred_styles || []).map(s => `<span class="preference-tag">${esc(s)}</span>`).join('')}
          </div>
        </div>

        <div class="persona-section">
          <h2>Preferred Programs</h2>
          <div class="preference-tags">
            ${(prefs.preferred_programs || []).map(s => `<span class="preference-tag">${esc(s)}</span>`).join('')}
          </div>
        </div>

        <div class="persona-section">
          <h2>Preferred Materials</h2>
          <div class="preference-tags">
            ${(prefs.preferred_materials || []).map(s => `<span class="preference-tag">${esc(s)}</span>`).join('')}
          </div>
        </div>

        <div class="persona-section">
          <h2>Preferred Atmospheres</h2>
          <div class="preference-tags">
            ${(prefs.preferred_atmospheres || []).map(s => `<span class="preference-tag">${esc(s)}</span>`).join('')}
          </div>
        </div>

        <div class="persona-section">
          <h2>Summary</h2>
          <div class="stats-grid">
            <div class="stat-card">
              <div class="stat-value">${summary.total_swipes || 0}</div>
              <div class="stat-label">Swipes</div>
            </div>
            <div class="stat-card">
              <div class="stat-value">${summary.likes || 0}</div>
              <div class="stat-label">Likes</div>
            </div>
            <div class="stat-card">
              <div class="stat-value">${summary.dislikes || 0}</div>
              <div class="stat-label">Dislikes</div>
            </div>
            <div class="stat-card">
              <div class="stat-value">${summary.error_count || 0}</div>
              <div class="stat-label">Errors</div>
            </div>
          </div>
        </div>
      </div>
    `;
  }

  // -- Tab Navigation --

  function renderTabNav() {
    const tabs = [
      { key: 'steps', label: 'Steps' },
      { key: 'errors', label: `Errors (${countErrors()})` },
      { key: 'perf', label: 'Performance' },
    ];

    return `
      <div class="tab-nav">
        ${tabs.map(t => `
          <button class="tab-btn ${activeTab === t.key ? 'active' : ''}"
                  data-tab="${t.key}">
            ${t.label}
          </button>
        `).join('')}
      </div>
    `;
  }

  function renderActiveTab() {
    switch (activeTab) {
      case 'steps': return renderStepViewer();
      case 'errors': return renderErrorPanel();
      case 'perf': return renderPerfTable();
      default: return '';
    }
  }

  // -- Step Viewer --

  function renderStepViewer() {
    const steps = report.steps || [];
    if (!steps.length) {
      return '<div class="empty-state"><div class="icon">--</div>No steps recorded</div>';
    }

    return `
      <div class="step-timeline">
        ${steps.map((step, i) => renderStepCard(step, i)).join('')}
      </div>
    `;
  }

  function renderStepCard(step, index) {
    const isExpanded = expandedSteps.has(index);
    const timingClass = step.duration_ms > 3000 ? 'slow' : step.duration_ms > 1000 ? 'medium' : 'fast';
    const meta = step.metadata || {};
    const base = dataPath();

    let swipeInfo = '';
    if (meta.decision) {
      swipeInfo = `
        <span class="swipe-decision ${meta.decision}">${meta.decision}</span>
        ${meta.card_title ? `<span style="margin-left:8px;font-size:12px;color:#888">${esc(meta.card_title)}</span>` : ''}
        ${meta.card_program ? `<span style="margin-left:8px;font-size:11px;color:#555">${esc(meta.card_program)}</span>` : ''}
      `;
    }

    let apiTable = '';
    if (step.api_calls && step.api_calls.length > 0) {
      apiTable = `
        <table class="api-calls-table">
          <thead>
            <tr><th>Method</th><th>URL</th><th>Status</th><th>Latency</th><th>Size</th></tr>
          </thead>
          <tbody>
            ${step.api_calls.map(c => `
              <tr>
                <td>${c.method}</td>
                <td style="max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(c.url)}</td>
                <td class="${c.status < 400 ? 'status-ok' : 'status-err'}">${c.status}</td>
                <td>${c.latency_ms.toFixed(0)}ms</td>
                <td>${formatBytes(c.payload_size)}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      `;
    }

    // Timing breakdown (Issue 3): show gesture/api/card/image sub-step durations
    let timingHtml = '';
    if (meta.timing) {
      const t = meta.timing;
      timingHtml = `
        <div style="margin-top:8px;font-size:12px">
          <div style="display:flex;gap:12px;color:#888">
            <span>Gesture: ${t.gesture_ms}ms</span>
            <span>API: ${t.api_wait_ms}ms</span>
            <span>Card: ${t.card_transition_ms}ms</span>
            <span>Image: ${t.image_load_ms}ms</span>
          </div>
        </div>
      `;
    }

    let errorsHtml = '';
    if (step.errors && step.errors.length > 0) {
      errorsHtml = `
        <div style="margin-top:8px">
          ${step.errors.map(e => `
            <div style="background:#1a0000;border:1px solid #400;border-radius:4px;padding:8px;margin-bottom:4px;font-size:12px;color:#f88">
              [${e.source}] ${esc(e.message)}
            </div>
          `).join('')}
        </div>
      `;
    }

    return `
      <div class="step-card ${isExpanded ? 'expanded' : ''}" data-step-index="${index}">
        <div class="step-header">
          <div>
            <span class="step-name">${esc(step.step_name)}</span>
            ${swipeInfo}
          </div>
          <span class="step-timing ${timingClass}">${step.duration_ms.toFixed(0)}ms</span>
        </div>
        <div class="step-body">
          ${step.screenshot ? `<img class="step-screenshot" src="${base}/${esc(step.screenshot)}" alt="${esc(step.step_name)}" loading="lazy">` : ''}
          <div class="step-meta">
            <div class="step-meta-item">
              <span class="label">URL: </span>
              <span class="value">${esc(step.page_url || 'N/A')}</span>
            </div>
            <div class="step-meta-item">
              <span class="label">API Calls: </span>
              <span class="value">${step.api_calls ? step.api_calls.length : 0}</span>
            </div>
            ${meta.authenticated !== undefined ? `
              <div class="step-meta-item">
                <span class="label">Auth: </span>
                <span class="value">${meta.authenticated ? 'Yes' : 'No'}</span>
              </div>
            ` : ''}
            ${meta.query ? `
              <div class="step-meta-item">
                <span class="label">Query: </span>
                <span class="value">${esc(meta.query)}</span>
              </div>
            ` : ''}
          </div>
          ${apiTable}
          ${timingHtml}
          ${errorsHtml}
        </div>
      </div>
    `;
  }

  // -- Error Panel --

  function renderErrorPanel() {
    const allErrors = collectAllErrors();
    if (!allErrors.length) {
      return '<div class="empty-state"><div class="icon">--</div>No errors detected</div>';
    }

    return `
      <div class="error-list">
        ${allErrors.map(e => `
          <div class="error-card ${e.severity}">
            <div class="error-severity ${e.severity}">${e.severity}</div>
            <div class="error-message">${esc(e.message)}</div>
            <div class="error-meta">
              <span>Step: ${esc(e.step)}</span>
              <span>Source: ${esc(e.source)}</span>
              ${e.source_file ? `<span>File: ${esc(e.source_file)}</span>` : ''}
            </div>
            ${e.stack_trace ? `<div class="error-stack">${esc(e.stack_trace)}</div>` : ''}
          </div>
        `).join('')}
      </div>
    `;
  }

  // -- Performance Table --

  function renderPerfTable() {
    const steps = (report.steps || []).slice().sort((a, b) => {
      const aVal = a[perfSortKey] || 0;
      const bVal = b[perfSortKey] || 0;
      return perfSortAsc ? aVal - bVal : bVal - aVal;
    });

    if (!steps.length) {
      return '<div class="empty-state"><div class="icon">--</div>No performance data</div>';
    }

    // Check if any step has timing breakdown data
    const hasTiming = steps.some(s => s.metadata && s.metadata.timing);

    return `
      <table class="perf-table">
        <thead>
          <tr>
            <th data-sort="step_name">Step ${sortArrow('step_name')}</th>
            <th data-sort="duration_ms">Duration ${sortArrow('duration_ms')}</th>
            ${hasTiming ? `
              <th>Gesture</th>
              <th>API Wait</th>
              <th>Card Trans.</th>
              <th>Image Load</th>
            ` : ''}
            <th>API Calls</th>
            <th>Errors</th>
            <th>Bottleneck</th>
          </tr>
        </thead>
        <tbody>
          ${steps.map(s => {
            const durClass = s.duration_ms > 3000 ? 'duration-slow' : s.duration_ms > 1000 ? 'duration-medium' : 'duration-fast';
            const bottleneck = classifyBottleneck(s);
            const t = (s.metadata && s.metadata.timing) ? s.metadata.timing : null;
            return `
              <tr>
                <td>${esc(s.step_name)}</td>
                <td class="${durClass}">${s.duration_ms.toFixed(0)}ms</td>
                ${hasTiming ? `
                  <td>${t ? t.gesture_ms + 'ms' : '--'}</td>
                  <td>${t ? t.api_wait_ms + 'ms' : '--'}</td>
                  <td>${t ? t.card_transition_ms + 'ms' : '--'}</td>
                  <td>${t ? t.image_load_ms + 'ms' : '--'}</td>
                ` : ''}
                <td>${s.api_calls ? s.api_calls.length : 0}</td>
                <td>${s.errors ? s.errors.length : 0}</td>
                <td><span class="bottleneck-badge">${bottleneck}</span></td>
              </tr>
            `;
          }).join('')}
        </tbody>
      </table>
    `;
  }

  // -- Helpers --

  function esc(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  function formatDuration(ms) {
    if (ms < 1000) return ms.toFixed(0) + 'ms';
    return (ms / 1000).toFixed(1) + 's';
  }

  function formatBytes(bytes) {
    if (!bytes) return '0B';
    if (bytes < 1024) return bytes + 'B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + 'KB';
    return (bytes / (1024 * 1024)).toFixed(1) + 'MB';
  }

  function countErrors() {
    if (!report || !report.steps) return 0;
    return report.steps.reduce((sum, s) => sum + (s.errors ? s.errors.length : 0), 0);
  }

  function collectAllErrors() {
    if (!report || !report.steps) return [];
    const errors = [];
    for (const step of report.steps) {
      for (const err of (step.errors || [])) {
        errors.push({
          step: step.step_name,
          message: err.message,
          source: err.source,
          stack_trace: err.stack_trace,
          severity: err.source === 'exception' ? 'critical' : err.source === 'network' ? 'error' : 'warning',
          source_file: feedback ? findSourceFile(err, step) : null,
        });
      }
    }
    return errors;
  }

  function findSourceFile(err, step) {
    if (!feedback || !feedback.errors) return null;
    const match = feedback.errors.find(e => e.message === err.message && e.step === step.step_name);
    return match ? match.source_file : null;
  }

  function classifyBottleneck(step) {
    // Use detailed timing data when available for more accurate classification
    const meta = step.metadata || {};
    if (meta.timing) {
      const t = meta.timing;
      const max = Math.max(t.gesture_ms, t.api_wait_ms, t.card_transition_ms, t.image_load_ms);
      if (max === t.api_wait_ms) return 'api_call';
      if (max === t.image_load_ms) return 'image_loading';
      if (max === t.card_transition_ms) return 'rendering';
      if (max === t.gesture_ms) return 'gesture';
    }

    if (!step.api_calls || step.api_calls.length === 0) return 'rendering';
    const hasImageCalls = step.api_calls.some(c => c.url.includes('/images/'));
    const hasReportCalls = step.api_calls.some(c => c.url.includes('/report/'));
    const hasSwipeCalls = step.api_calls.some(c => c.url.includes('/swipes/'));
    if (hasReportCalls) return 'llm_api';
    if (hasSwipeCalls) return 'algorithm';
    if (hasImageCalls) return 'image_loading';
    return 'network';
  }

  function sortArrow(key) {
    if (perfSortKey !== key) return '';
    return `<span class="sort-arrow">${perfSortAsc ? '\u25BC' : '\u25B2'}</span>`;
  }

  // -- Events --

  function attachEvents() {
    // Tab clicks
    document.querySelectorAll('.tab-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        activeTab = btn.dataset.tab;
        render();
      });
    });

    // Step expand/collapse
    document.querySelectorAll('.step-header').forEach(header => {
      header.addEventListener('click', () => {
        const card = header.closest('.step-card');
        const index = parseInt(card.dataset.stepIndex);
        if (expandedSteps.has(index)) {
          expandedSteps.delete(index);
        } else {
          expandedSteps.add(index);
        }
        card.classList.toggle('expanded');
        const body = card.querySelector('.step-body');
        if (body) {
          body.style.display = card.classList.contains('expanded') ? 'block' : 'none';
        }
      });
    });

    // Perf table sorting
    document.querySelectorAll('.perf-table th[data-sort]').forEach(th => {
      th.addEventListener('click', () => {
        const key = th.dataset.sort;
        if (perfSortKey === key) {
          perfSortAsc = !perfSortAsc;
        } else {
          perfSortKey = key;
          perfSortAsc = false;
        }
        render();
      });
    });

    // Persona selector toggle
    const selectorEl = document.querySelector('[data-action="toggle-selector"]');
    if (selectorEl) {
      selectorEl.addEventListener('click', () => {
        selectorOpen = !selectorOpen;
        render();
      });
    }

    // Persona option clicks
    document.querySelectorAll('.persona-option').forEach(opt => {
      opt.addEventListener('click', () => {
        const runId = opt.dataset.runId;
        if (runId && runId !== activeRunId) {
          selectorOpen = false;
          loadRun(runId);
        }
      });
    });
  }

  // -- Init --
  loadData();

})();
