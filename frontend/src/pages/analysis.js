import {api} from '../api/client.js';
import {badge, blank, heading, table} from '../components/common/board.js';
import {profileChart, vectorSummary} from '../components/profile.js';
import {channelLabels, demoPeriod, exceptionNotes, reconStateLabels, recordStateLabels, runLabels, stationLabels} from '../constants/domain.js';
import {bindForm} from '../hooks/forms.js';
import {pollWhile} from '../hooks/poll.js';
import {go} from '../router/routes.js';
import {workbench} from '../stores/workbench.js';
import {isProcessing} from '../types/run.js';
import {band, esc, localDateTime, number, pad} from '../utils/format.js';

export async function analysisPage(container, id) {
  if (id === 'trace') return traceIndex(container);
  if (id && id.includes('/')) return traceDetail(container, id);
  if (id) return analysisDetail(container, id);
  const canRun = workbench.user.role === 'analyst';
  workbench.runs = await api.runs();
  container.innerHTML = `${heading('密度分型', '按六个归还时段的分布形状寻找节律相近的工具站。两路联单先对账，只有实收进入向量。')}
    <div class="analysis-layout">
      <section class="panel config"><div class="panel-heading"><div><span class="eyebrow">余弦距离 / DBSCAN</span><h2>分型参数</h2></div></div>
      ${canRun ? `<form id="run-form">
        <label>方案名称<input name="title" value="11 月第二周 · 归还节律" minlength="2" maxlength="80" required></label>
        <div class="field-grid two"><label>窗口起日<input name="start" type="date" value="${demoPeriod.start}" required></label>
        <label>窗口止日<input name="end" type="date" value="${demoPeriod.end}" required></label></div>
        <fieldset><legend>密度门槛</legend><div class="field-grid three">
          <label>邻域半径 ε<input name="eps" type="number" min="0" max="1" step="any" value="0.035" required></label>
          <label>最少邻居数<input name="min_points" type="number" min="2" max="20" value="3" required></label>
          <label>最少归还件数<input name="min_returns" type="number" min="1" max="9999" value="30" required></label></div>
          <p>邻居数含本站。件数按对账实收计算，争议件数不计入。低于门槛的站点留待单独复核。</p></fieldset>
        <p class="error" role="alert"></p><button type="submit" class="primary">创建版本并计算 <span aria-hidden="true">→</span></button>
      </form>` : blank('参数由分析员提交', '打开右侧方案可查阅当前角色有权查看的版本。')}
      </section>
      <section class="panel"><div class="panel-heading"><div><span class="eyebrow">版本记录</span><h2>分型方案</h2></div></div>
        ${workbench.runs.length ? `<ul class="version-list">${workbench.runs.map(run => `
          <li><a href="#analysis/${run.id}"><span><small class="mono">V${run.id} · ${localDateTime(run.created_at)}</small><strong>${esc(run.title)}</strong></span>${badge(runLabels[run.status], run.status)}</a></li>`).join('')}</ul>` :
          blank('尚无可查阅版本', '计算将保存当时的站点向量，可在结果中核对输入指纹。')}
      </section>
    </div>`;
  if (canRun) bindForm(container.querySelector('#run-form'), async data => {
    const {id: runId} = await api.createRun({...data, eps: Number(data.eps), min_points: Number(data.min_points), min_returns: Number(data.min_returns)});
    go('analysis', runId);
  });
}

async function analysisDetail(container, id) {
  if (!/^\d+$/.test(id)) throw new Error('方案版本号无效');
  const run = await api.run(id);
  const render = data => {
    const {snapshot, result, status} = data;
    const {params, bands} = snapshot;
    const dutyLink = (status === 'published' || (status === 'ready' && workbench.user.role === 'admin'))
      ? `<a class="primary" href="#duty/${id}">${status === 'published' ? '查看值班单' : '进入值守复核'} →</a>` : '';
    container.innerHTML = `<a class="back" href="#analysis">← 分型方案</a>
      ${heading(data.title, `${params.start} 至 ${params.end} · ${runLabels[status]}`, dutyLink)}
      <div class="run-strip"><div><span>方案版本</span><strong>V${data.id}</strong></div>
        <div><span>半径 / 最少邻居</span><strong>${params.eps} / ${params.min_points}</strong></div>
        <div><span>纳入门槛</span><strong>${params.min_returns} 件实收</strong></div>
        <div><span>输入指纹</span><strong class="mono" title="${esc(data.checksum)}">${data.checksum.slice(0, 12)}</strong></div></div>
      ${result ? resultBoard(result, bands, id) : `<section class="panel">${blank(runLabels[status], isProcessing(data) ? '后台正在处理该版本。结果就绪后会自动显示。' : data.failure)}
        <p class="error poll-error" data-poll-error role="alert"></p></section>`}`;
  };
  render(run);
  if (isProcessing(run)) pollWhile(container, async () => {
    const next = await api.run(id);
    if (container.isConnected) render(next);
    return isProcessing(next);
  });
}

function resultBoard(result, bands, id) {
  const {groups, members, diagnostics} = result;
  const exceptions = members.filter(m => m.status in exceptionNotes);
  return `<section class="results-section"><div class="result-heading"><div><h2>分组画像</h2><p>每个站点先按实收换算成占比，再按组等权平均；争议件数不计入。</p></div>
      <div class="result-summary"><strong>${groups.length} 组</strong><span>${diagnostics.eligible} / ${diagnostics.stations} 站参与 · ${number(diagnostics.returns)} 件实收</span></div></div>
    ${diagnostics.disputed || diagnostics.unreconciled || diagnostics.partial ? `<div class="recon-banner">
      <span>对账提示</span>
      <p>争议 ${number(diagnostics.disputed || 0)} 件未计实收；${diagnostics.unreconciled || 0} 站未对账不参与分型，${diagnostics.partial || 0} 站部分对上照常分型。
        <a href="#analysis/trace/${id}">逐站追溯记录 ↔</a></p></div>` : ''}
    ${groups.length ? `<div class="profile-grid">${groups.map(group => `<article class="panel group-panel">
      <div class="group-title"><span class="letterpress">${group.key}</span><div><span class="eyebrow">主要归还时段</span><h3>${band(bands[group.peak])}</h3></div></div>
      ${profileChart(group.profile, bands, group.peak)}
      <p class="cohort">${group.station_codes.length} 站 · ${number(group.returns)} 件 · ${group.station_codes.join(' / ')}</p>
      <p class="group-advice">${esc(group.advice)}</p></article>`).join('')}</div>` :
      `<div class="panel">${blank('该版本未形成分组', '请复核逐站诊断，再判断是否扩大日期窗口或调整密度门槛。')}</div>`}
    </section>
    <section class="panel"><div class="panel-heading"><div><span class="eyebrow">单站复核</span><h2>例外站点 <span class="tally">${exceptions.length}</span></h2></div>
      <a href="#analysis/trace/${id}">查看逐站记录追溯 ↗</a></div>
      ${exceptions.length ? table('例外站点', ['站点', '类型', '对账', '实收 / 争议 / 凭证', '建议复核'], exceptions.map(m => `<tr>
        <td><span class="key mono">${m.code}</span> · ${esc(m.name)}</td><td>${badge(stationLabels[m.status], m.status)}</td>
        <td>${m.recon_state ? badge(reconStateLabels[m.recon_state] || m.recon_state, m.recon_state) : '—'}</td>
        <td class="mono">${number(m.actual ?? m.total)} / ${number(m.disputed || 0)} / ${number(m.credential ?? m.total)}</td>
        <td>${exceptionNotes[m.status]}</td></tr>`)) : blank('没有例外站点', '窗口内所有站点均已分型。')}</section>
    <section class="panel"><div class="panel-heading"><div><span class="eyebrow">邻域诊断</span><h2>逐站分型结果</h2></div></div>
      ${table('逐站分型结果', ['站点', '类型', '分组', '邻居', '实收', '争议', '分时实收（按时段顺序）'], members.map(m => `<tr>
        <td><span class="key mono">${m.code}</span> · ${esc(m.name)}</td><td>${badge(stationLabels[m.status], m.status)}</td>
        <td>${m.group || '—'}</td><td>${m.neighbors ?? '—'}</td>
        <td class="mono">${number(m.actual ?? m.total)}</td><td class="mono">${number(m.disputed || 0)}</td>
        <td>${vectorSummary(m)}</td></tr>`))}</section>`;
}

async function traceIndex(container) {
  const runs = await api.runs();
  container.innerHTML = `<a class="back" href="#analysis">← 分型方案</a>
    ${heading('记录追溯', '查看某一版本每个站点用了哪些记录、哪些还没对上。选择版本后查看逐站明细。')}
    <section class="panel"><div class="panel-heading"><div><span class="eyebrow">按版本追溯</span><h2>选择方案版本</h2></div></div>
    ${runs.length ? table('方案版本', ['版本', '方案', '状态', ''], runs.map(run => `<tr>
      <td class="mono key">V${run.id}</td><td>${esc(run.title)}</td><td>${badge(runLabels[run.status], run.status)}</td>
      <td><a href="#analysis/trace/${run.id}">逐站追溯 →</a></td></tr>`)) : blank('尚无可追溯版本', '创建并完成一次计算后即可追溯。')}</section>`;
}

async function traceDetail(container, id) {
  const [, runId, code] = id.split('/');
  if (!/^\d+$/.test(runId || '')) throw new Error('方案版本号无效');
  const trace = await api.runTrace(runId);
  const codes = Object.keys(trace.stations);
  if (code && !codes.includes(code)) throw new Error('该方案中没有这个站点');
  const selected = code || null;
  const detail = selected ? trace.stations[selected] : null;
  container.innerHTML = `<a class="back" href="#analysis/${runId}">← 返回方案 V${runId}</a>
    ${heading(`记录追溯 · ${esc(trace.run.title)}`, `V${runId} · ${trace.run.params.start} 至 ${trace.run.params.end} · 输入指纹 ${trace.run.checksum.slice(0, 12)}`)}
    <div class="recon-strip">
      <div><span>凭证</span><strong>${number(trace.stats.records)}</strong></div>
      <div><span>成对</span><strong>${trace.stats.paired_slots}</strong></div>
      <div><span>争议槽</span><strong>${trace.stats.disputed_slots}</strong></div>
      <div><span>重复登记</span><strong>${trace.stats.duplicate_rows}</strong></div>
      <div><span>未对上</span><strong>${trace.stats.unresolved_rows + trace.stats.unattributed_rows}</strong></div>
    </div>
    <section class="panel"><div class="panel-heading"><div><span class="eyebrow">逐站选择</span><h2>站点 <span class="tally">${codes.length}</span></h2></div></div>
      ${table('逐站追溯', ['站点', '对账', '实收 / 争议', '所用记录', '未对上', ''], codes.map(key => {
        const site = trace.stations[key];
        return `<tr><td><span class="key mono">${esc(key)}</span> · ${esc(site.name)}</td>
          <td>${badge(reconStateLabels[site.state] || site.state, site.state)}</td>
          <td class="mono">${number(site.actual)} / ${number(site.disputed)}</td>
          <td class="mono">${site.records.filter(r => r.used).length}</td>
          <td class="mono">${site.unresolved.length}</td>
          <td><a href="#analysis/trace/${runId}/${encodeURIComponent(key)}">${selected === key ? '当前' : '查看'} →</a></td></tr>`;
      }).join(''))}</section>
    ${detail ? traceDetailBoard(detail) : ''}
    ${trace.unattributed.length ? `<section class="panel"><div class="panel-heading"><h2>无法归属的记录 <span class="tally">${trace.unattributed.length}</span></h2></div>
      ${table('无法归属的记录', ['通道', '日期 / 小时', '件数', '原因'], trace.unattributed.map(record => `<tr>
        <td>${badge(channelLabels[record.channel], record.channel)} <small>${esc(record.source || '')}</small></td>
        <td class="mono">${record.day || '缺日期'} ${pad(record.hour)}:00</td><td>${record.quantity}</td>
        <td>${record.reason === 'unknown_station' ? `站点 ${esc(record.station_code)} 尚未登记` : '缺少站点或日期'}</td></tr>`))}</section>` : ''}`;
}

function traceDetailBoard(site) {
  const rows = site.slots.length ? site.slots.map(slot => `<tr>
    <td class="mono">${slot.day} ${pad(slot.hour)}:00</td>
    <td class="mono">${slot.manual || '—'}</td><td class="mono">${slot.cabinet || '—'}</td><td class="mono">${slot.paper || '—'}</td>
    <td class="mono"><strong>${slot.actual}</strong></td><td class="mono">${slot.disputed || '—'}</td>
    <td>${badge(recordStateLabels[slot.state], slot.state)}</td>
    <td class="mono">${(slot.used_refs || []).map(ref => `#${ref}`).join(' ') || '—'}</td></tr>`) : '';
  return `<section class="panel"><div class="panel-heading"><div><span class="eyebrow">${esc(site.name)}</span><h2>${esc(site.code)} 的记录与槽位</h2></div>
      <strong class="key">实收 ${number(site.actual)} · 争议 ${number(site.disputed)}</strong></div>
    ${rows ? table('槽位追溯', ['日期 / 小时', '人工', '柜机', '纸联', '实收', '争议', '状态', '所用记录'], rows) : blank('该站没有记录', '该站未参与本版本分型。')}
    <div class="recon-sub"><h3>所用记录 <span class="tally">${site.records.filter(r => r.used).length}</span></h3>
      ${site.records.filter(r => r.used).length ? table('所用记录', ['记录', '通道', '日期 / 小时', '件数', '状态'], site.records.filter(r => r.used).map(record => `<tr>
        <td class="mono">#${record.id}</td><td>${badge(channelLabels[record.channel], record.channel)}</td>
        <td class="mono">${record.day || '缺日期'} ${pad(record.hour)}:00</td><td>${record.quantity}</td>
        <td>${badge(recordStateLabels[record.state], record.state)}</td></tr>`)) : '<p class="hint">没有计入实收的记录。</p>'}
    </div>
    <div class="recon-sub"><h3>还没对上 <span class="tally">${site.unresolved.length}</span></h3>
      ${site.unresolved.length ? table('未对上记录', ['记录', '通道', '日期 / 小时', '件数', '原因'], site.unresolved.map(record => `<tr>
        <td class="mono">#${record.id}</td><td>${badge(channelLabels[record.channel], record.channel)}</td>
        <td class="mono">${record.day || '缺日期'} ${pad(record.hour)}:00</td><td>${record.quantity}</td>
        <td>${record.reason === 'no_day' ? '缺少日期，补齐后进入实收' : '未对上'}</td></tr>`)) : '<p class="hint">该站全部记录都已对上。</p>'}
    </div>
    <p class="hint"><a href="#ledger/${encodeURIComponent(site.code)}">到台账补齐记录 →</a></p></section>`;
}
