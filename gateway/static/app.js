const state = { datasets: [], runId: null, timer: null };
const $ = (id) => document.getElementById(id);
const money = (value) => value == null ? '--' : Number(value).toLocaleString('zh-CN', { maximumFractionDigits: 2 });
const percent = (value) => value == null ? '--' : `${(Number(value) * 100).toFixed(2)}%`;

async function getJson(url, options) {
  const response = await fetch(url, options);
  const body = await response.json();
  if (!response.ok) throw new Error(body.message || body.code || `HTTP ${response.status}`);
  return body;
}

function setRunStatus(status, runId = '') {
  const label = { idle: '尚未运行', queued: '排队中', running: '运行中', succeeded: '已完成', failed: '失败', cancelled: '已取消' }[status] || status;
  $('run-status').dataset.state = status || 'idle';
  $('run-status-text').textContent = label;
  $('run-id').textContent = runId ? `· ${runId}` : '';
  $('run-button').disabled = status === 'queued' || status === 'running';
  $('cancel-button').disabled = !(status === 'queued' || status === 'running');
}

function renderDatasets() {
  const select = $('dataset');
  select.replaceChildren(...state.datasets.map((item) => {
    const option = document.createElement('option');
    option.value = JSON.stringify(item);
    option.textContent = `${item.id} / ${item.version} · ${item.symbolCount} 个标的`;
    return option;
  }));
  updateDatasetNote();
}

function selectedDataset() { return JSON.parse($('dataset').value); }
function updateDatasetNote() {
  if (!state.datasets.length) { $('dataset-note').textContent = '没有可用的日线数据集'; return; }
  const item = selectedDataset();
  $('dataset-note').textContent = `${item.startDate} 至 ${item.endDate} · ${item.barCount} 根 Bar · manifest ${item.manifestHash}`;
  $('start-date').min = item.startDate; $('start-date').max = item.endDate;
  $('end-date').min = item.startDate; $('end-date').max = item.endDate;
  if (!$('start-date').value || $('start-date').value < item.startDate) $('start-date').value = item.startDate;
  if (!$('end-date').value || $('end-date').value > item.endDate) $('end-date').value = item.endDate;
}

function renderEvents(events = []) {
  $('event-count').textContent = `${events.length} 个事件`;
  const log = $('event-log');
  if (!events.length) { log.innerHTML = '<div class="empty-row">等待 worker 事件。</div>'; return; }
  log.replaceChildren(...events.map((event) => {
    const row = document.createElement('div'); row.className = 'event-line';
    const progress = event.payload?.progress == null ? '' : ` ${event.payload.progress}%`;
    row.innerHTML = `<span class="event-seq">${event.sequence}</span><span class="event-type">${event.type}</span><span class="event-message">${event.payload?.stage || event.payload?.errorCode || 'worker event'}${progress}</span>`;
    return row;
  }));
  log.scrollTop = log.scrollHeight;
}

function renderMetrics(summary) {
  $('metric-return').textContent = percent(summary.totalReturn);
  $('metric-end').textContent = money(summary.endValue);
  $('metric-start').textContent = money(summary.startValue);
  $('metric-pnl').textContent = `损益 ${money(summary.totalPnl)}`;
  $('metric-drawdown').textContent = percent(summary.maxDrawdown);
  $('metric-sharpe').textContent = summary.sharpeRatio == null ? '--' : Number(summary.sharpeRatio).toFixed(2);
  $('metric-trades').textContent = summary.tradeCount ?? '--';
}

function pointPath(points, x, y) { return points.map((point, index) => `${index ? 'L' : 'M'}${x(index)},${y(point)}`).join(' '); }
function renderChart(series) {
  const curve = series.equityCurve || []; const drawdown = series.drawdownCurve || [];
  $('chart-start').textContent = curve[0]?.date || '--'; $('chart-end').textContent = curve[curve.length - 1]?.date || '--';
  if (!curve.length) { $('equity-chart').innerHTML = '<text x="450" y="150" text-anchor="middle" class="empty-chart">没有可绘制的权益数据</text>'; return; }
  const svg = $('equity-chart'), width = 900, height = 300, pad = { left: 46, right: 15, top: 20, bottom: 24 };
  const values = curve.map((item) => Number(item.marketValue)); const lows = drawdown.map((item) => Number(item.drawdown));
  const min = Math.min(...values), max = Math.max(...values), range = max - min || Math.max(Math.abs(max) * .01, 1);
  const x = (index) => pad.left + index * (width - pad.left - pad.right) / Math.max(curve.length - 1, 1);
  const y = (value) => pad.top + (max - value) * (height - pad.top - pad.bottom) / range;
  const ddMin = Math.min(...lows, 0), ddRange = Math.abs(ddMin) || 1;
  const yd = (value) => height - pad.bottom - Math.abs(value) * 48 / ddRange;
  const grid = [0, .5, 1].map((fraction) => { const yy = pad.top + fraction * (height - pad.top - pad.bottom); return `<line x1="${pad.left}" x2="${width - pad.right}" y1="${yy}" y2="${yy}" class="chart-grid"/><text x="5" y="${yy + 4}" class="chart-label">${money(max - fraction * range)}</text>`; }).join('');
  svg.innerHTML = `${grid}<path class="equity-line" d="${pointPath(values, x, y)}"/><path class="drawdown-line" d="${pointPath(lows, x, yd)}"/>`;
}

function renderTrades(trades = []) {
  $('trade-count').textContent = `${trades.length} 笔`; const body = $('trade-body');
  if (!trades.length) { body.innerHTML = '<tr><td colspan="6" class="empty-row">暂无成交记录</td></tr>'; return; }
  body.replaceChildren(...trades.map((trade) => { const row = document.createElement('tr'); const side = trade.side === 'buy' ? '买入' : '卖出'; row.innerHTML = `<td>${trade.executedAt || '--'}</td><td>${trade.symbol || '--'}</td><td class="side-${trade.side}">${side}</td><td>${money(trade.quantity)}</td><td>${money(trade.price)}</td><td>${money(trade.commission)}</td>`; return row; }));
}

async function loadResult(runId) { const result = await getJson(`/api/backtests/${runId}/result`); renderMetrics(result.summary || {}); renderChart(result.series || {}); renderTrades(result.series?.trades || []); $('footer-run').textContent = `结果 ${result.resultId || runId} · ${result.generatedAt || ''}`; }
async function poll(runId) {
  // 工作台只跟踪当前回测，不会枚举所有任务。
  try {
    const status = await getJson(`/api/backtests/${runId}`); setRunStatus(status.status, runId); renderEvents(status.events);
    if (status.status === 'succeeded') { clearInterval(state.timer); state.timer = null; await loadResult(runId); }
    if (['failed', 'cancelled', 'timed_out'].includes(status.status)) { clearInterval(state.timer); state.timer = null; }
  } catch (error) { clearInterval(state.timer); state.timer = null; setRunStatus('failed', runId); $('event-log').innerHTML = `<div class="event-message">${error.message}</div>`; }
}

async function submit(event) {
  event.preventDefault(); if (!state.datasets.length) return;
  if (state.timer) clearInterval(state.timer);
  setRunStatus('queued'); renderMetrics({}); renderChart({}); renderTrades([]); renderEvents([]);
  const item = selectedDataset();
  const payload = { strategyCode: $('strategy-code').value, dataset: { id: item.id, version: item.version, manifestHash: item.manifestHash, adjustmentMode: 'none' }, dateRange: { start: $('start-date').value, end: $('end-date').value }, initialCapital: Number($('capital').value), benchmark: $('benchmark').value || null, parameters: { symbol: $('symbol').value, quantity: Number($('quantity').value) } };
  try { const accepted = await getJson('/api/backtests', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }); state.runId = accepted.runId; localStorage.setItem('qwesdk.lastRunId', state.runId); setRunStatus(accepted.status, state.runId); state.timer = setInterval(() => poll(state.runId), 500); await poll(state.runId); } catch (error) { setRunStatus('failed'); $('event-log').innerHTML = `<div class="event-message">${error.message}</div>`; }
}

async function restoreLastRun() {
  const savedRunId = localStorage.getItem('qwesdk.lastRunId');
  if (!savedRunId) return;
  try {
    state.runId = savedRunId;
    const status = await getJson(`/api/backtests/${savedRunId}`);
    setRunStatus(status.status, savedRunId); renderEvents(status.events);
    if (status.status === 'succeeded') await loadResult(savedRunId);
    else if (['queued', 'running'].includes(status.status)) { state.timer = setInterval(() => poll(savedRunId), 500); await poll(savedRunId); }
  } catch (error) { localStorage.removeItem('qwesdk.lastRunId'); }
}

async function init() {
  $('backtest-form').addEventListener('submit', submit); $('dataset').addEventListener('change', updateDatasetNote);
  $('cancel-button').addEventListener('click', async () => { if (state.runId) await getJson(`/api/backtests/${state.runId}/cancel`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' }); });
  try { state.datasets = await getJson('/api/datasets'); renderDatasets(); $('service-status').textContent = 'Gateway 已连接'; await restoreLastRun(); } catch (error) { $('service-status').textContent = 'Gateway 不可用'; $('dataset-note').textContent = error.message; }
}
init();
