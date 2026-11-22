import {api} from '../api/client.js';
import {badge, blank, heading, table} from '../components/common/board.js';
import {bindForm} from '../hooks/forms.js';
import {channelLabels, demoPeriod, reconStateLabels, recordStateLabels} from '../constants/domain.js';
import {workbench} from '../stores/workbench.js';
import {esc, number, pad} from '../utils/format.js';

export async function ledgerPage(container, selected) {
  const canEdit = workbench.user.role === 'analyst';
  workbench.stations = await api.stations();
  const view = workbench.ledger;
  if (selected && workbench.stations.some(s => s.code === selected)) {
    view.station = selected;
    view.page = 1;
  }
  const options = workbench.stations.map(site => `<option value="${site.code}">${site.code} · ${esc(site.name)}</option>`).join('');
  container.innerHTML = `${heading('归还时段', '按北京时间登记每个站点每小时的归还件数。柜机流水与纸联在此导入、对账。',
    canEdit ? '<button class="primary" id="new-record">补录归还</button>' : '')}
    <section class="panel"><form id="ledger-filter" class="filters">
      <label>起日<input name="start" type="date" value="${esc(view.start)}" required></label>
      <label>止日<input name="end" type="date" value="${esc(view.end)}" required></label>
      <label>站点<select name="station"><option value="">全部站点</option>${options}</select></label>
      <label>通道<select name="channel"><option value="">全部通道</option>${Object.entries(channelLabels).map(([key, label]) => `<option value="${key}">${label}</option>`).join('')}</select></label>
      <button class="secondary" type="submit">查询台账</button><p role="alert" class="error"></p>
    </form></section>
    ${canEdit ? `<form id="import-form" class="entry panel">
      <div class="panel-heading"><div><span class="eyebrow">两路归还联</span><h2>导入柜机流水 / 纸联</h2></div></div>
      <p class="hint">柜机流水首行需含“站点、日期、小时、件数”；纸联可只剩“小时、件数”，缺站点或日期时用下方默认值补齐，仍缺的行保留为待落位。同一文件重跑不会重复计件。</p>
      <div class="field-grid">
        <label>来源通道<select name="channel" required><option value="cabinet">柜机流水</option><option value="paper">纸联</option></select></label>
        <label>文件名<input name="filename" minlength="2" maxlength="120" placeholder="回收联_1115.csv" required></label>
        <label>联单起日<input name="start" type="date" value="${esc(view.start)}" required></label>
        <label>联单止日<input name="end" type="date" value="${esc(view.end)}" required></label>
        <label>默认站点<select name="default_station"><option value="">—</option>${options}</select></label>
        <label>默认日期<input name="default_day" type="date"></label>
      </div>
      <label>CSV 内容<textarea name="content" rows="5" placeholder="站点,日期,小时,件数,联单&#10;X01,2026-11-09,8,5,回收联_1109.csv" required></textarea></label>
      <p role="alert" class="error"></p>
      <div class="actions"><button type="submit" class="primary">导入并计入台账</button></div>
      <p class="import-note" id="import-note"></p>
    </form>` : ''}
    <form id="record-form" class="entry panel" hidden>
      <h2>补录归还</h2><div class="field-grid">
        <label>站点<select name="station_code" required>${options}</select></label>
        <label>归还日期<input name="day" type="date" value="${esc(view.end)}" required></label>
        <label>起始小时<input name="hour" type="number" min="0" max="23" value="10" required></label>
        <label>件数<input name="quantity" type="number" min="1" max="9999" required></label>
        <label>来源联单<input name="source" minlength="2" maxlength="80" placeholder="回收联_1115补记.csv" required></label>
      </div><p role="alert" class="error"></p><button type="submit" class="primary">保存归还</button>
    </form>
    <section class="panel" id="reconcile-panel"><p class="loading">正在对账…</p></section>
    <section class="panel" id="ledger-list"><p class="loading">正在读取台账…</p></section>
    <dialog id="correction"><form class="entry"><h2>校正归还记录</h2><p id="record-meta"></p>
      <div class="field-grid">
        <label>站点<select name="station_code"><option value="">未落位</option>${options}</select></label>
        <label>归还日期<input name="day" type="date"></label>
        <label>起始小时<input name="hour" type="number" min="0" max="23"></label>
        <label>件数<input name="quantity" type="number" min="1" max="9999" required></label>
      </div>
      <label>来源联单<input name="source" minlength="2" maxlength="80" required></label>
      <p class="hint">补齐缺失的站点和日期后，该记录会从“未对上”转入实收。</p>
      <p role="alert" class="error"></p><div class="actions"><button type="submit" class="primary">保存校正</button><button type="button" class="secondary" data-close>取消</button></div>
    </form></dialog>`;
  const filters = container.querySelector('#ledger-filter');
  filters.elements.station.value = view.station;
  filters.elements.channel.value = view.channel || '';
  const ledger = container.querySelector('#ledger-list');
  const reconcilePanel = container.querySelector('#reconcile-panel');
  const dialog = container.querySelector('#correction');
  let editing;

  const loadReconcile = async (query = view) => {
    const {start, end, station} = query;
    const data = await api.reconcile({start, end}, station);
    if (!container.isConnected) return;
    reconcilePanel.innerHTML = `<div class="panel-heading"><div><span class="eyebrow">逐站对账</span><h2>实收核对
        <span class="tally">${number(data.stats.records)} 笔凭证</span></h2></div>
        <strong class="key">${number(data.stations.reduce((sum, site) => sum + site.actual, 0))} 件实收</strong></div>
      <div class="recon-strip">
        <div><span>成对槽</span><strong>${data.stats.paired_slots}</strong></div>
        <div><span>争议槽</span><strong>${data.stats.disputed_slots}</strong></div>
        <div><span>单边实收</span><strong>${data.stats.standalone_slots}</strong></div>
        <div><span>重复登记</span><strong>${data.stats.duplicate_rows}</strong></div>
        <div><span>待落位</span><strong>${data.stats.unresolved_rows + data.stats.unattributed_rows}</strong></div>
      </div>
      ${data.stations.length ? table('逐站对账', ['站点', '对账', '实收', '争议', '凭证', '待落位'], data.stations.map(site => `<tr>
        <td><a class="key mono" href="#ledger/${site.code}">${site.code}</a> · ${esc(site.name)}</td>
        <td>${badge(reconStateLabels[site.state], site.state)}<small>${esc(site.note)}</small></td>
        <td class="mono">${number(site.actual)}</td><td class="mono">${number(site.disputed)}</td>
        <td class="mono">${number(site.credential)}</td><td class="mono">${site.unresolved_count}</td></tr>`)) :
        blank('窗口内没有站点记录', '导入柜机流水与纸联后，这里会显示逐站实收与争议。')}
      ${data.unattributed.length ? `<div class="recon-sub"><h3>无法归属的记录 <span class="tally">${data.unattributed.length}</span></h3>
        ${table('无法归属的记录', ['来源', '日期 / 小时', '件数', '原因'], data.unattributed.map(record => `<tr>
          <td>${badge(channelLabels[record.channel], record.channel)} <small>${esc(record.source || '')}</small></td>
          <td class="mono">${record.day || '缺日期'} ${pad(record.hour)}:00</td><td>${record.quantity}</td>
          <td>${record.reason === 'unknown_station' ? `站点 ${esc(record.station_code)} 尚未登记` : '缺少站点'}</td></tr>`))}</div>` : ''}
      ${data.detail ? reconcileDetail(data.detail) : ''}`;
  };

  const load = async (query = view) => {
    const {start, end, station, channel, page} = query;
    const [{total, quantity, unresolved, items}] = await Promise.all([
      api.records({start, end, station_code: station || null, channel: channel || null}, page),
      loadReconcile(query),
    ]);
    if (!container.isConnected) return;
    Object.assign(view, query);
    ledger.innerHTML = `<div class="panel-heading"><div><span class="eyebrow">小时归还联</span><h2>归还记录 <span class="tally">${number(total)} 笔</span></h2></div>
      <strong class="key">${number(quantity)} 件凭证</strong></div>` +
      (unresolved ? `<p class="hint warn">其中 ${number(unresolved)} 笔缺少站点或日期，暂不计入实收；点“校正”补齐后可对上。</p>` : '') +
      (items.length ? table('归还记录', ['日期 / 小时', '站点', '通道', '件数', '联单', '批次', '修订', ...(canEdit ? ['操作'] : [])], items.map(row => `
        <tr${row.station_code && row.day ? '' : ' class="row-pending"'}><td class="mono">${row.day || '<em>缺日期</em>'} <strong>${pad(row.hour)}:00</strong></td>
        <td>${esc(row.name || '未落位')} <small>${row.station_code || '—'}</small></td>
        <td>${badge(channelLabels[row.channel], row.channel)}</td>
        <td><strong>${row.quantity}</strong></td><td>${esc(row.source)}</td>
        <td class="mono">${row.batch_id ? `#${row.batch_id}` : '—'}</td><td>${badge(`R${row.revision}`)}</td>
        ${canEdit ? `<td><button class="text-button" data-edit="${row.id}">校正</button></td>` : ''}</tr>`)) : blank('窗口内没有记录', '可扩大日期窗口，或请分析员检查是否漏录。')) +
      `<div class="pager"><button class="secondary" type="button" data-page="${page - 1}" ${page === 1 ? 'disabled' : ''}>上一页</button>
      <span>第 ${page} / ${Math.max(1, Math.ceil(total / 12))} 页</span>
      <button class="secondary" type="button" data-page="${page + 1}" ${page * 12 >= total ? 'disabled' : ''}>下一页</button></div>`;
    for (const button of ledger.querySelectorAll('[data-page]')) {
      button.onclick = () => load({...view, page: Number(button.dataset.page)}).catch(showError);
    }
    for (const button of ledger.querySelectorAll('[data-edit]')) {
      button.onclick = () => {
        editing = items.find(row => String(row.id) === button.dataset.edit);
        dialog.querySelector('#record-meta').textContent = `${editing.name || '未落位'} · ${editing.day || '缺日期'} ${pad(editing.hour)}:00 · R${editing.revision} · ${channelLabels[editing.channel]}`;
        dialog.querySelector('[role=alert]').textContent = '';
        dialog.elements.station_code.value = editing.station_code || '';
        dialog.elements.day.value = editing.day || '';
        dialog.elements.hour.value = editing.hour;
        dialog.elements.quantity.value = editing.quantity;
        dialog.elements.source.value = editing.source;
        dialog.showModal();
      };
    }
  };
  const showError = error => filters.querySelector('[role=alert]').textContent = error.message;
  bindForm(filters, data => load({...data, channel: data.channel, page: 1}));
  dialog.querySelector('[data-close]').onclick = () => dialog.close();
  bindForm(dialog.querySelector('form'), async data => {
    const change = {revision: editing.revision, quantity: Number(data.quantity), source: data.source};
    if (data.station_code && data.station_code !== editing.station_code) change.station_code = data.station_code;
    if (data.day && data.day !== editing.day) change.day = data.day;
    if (data.hour !== '' && Number(data.hour) !== editing.hour) change.hour = Number(data.hour);    await api.correctRecord(editing.id, change);
    dialog.close();
    await load().catch(showError);
  });
  if (canEdit) {
    const form = container.querySelector('#record-form');
    container.querySelector('#new-record').onclick = () => {
      form.hidden = !form.hidden;
      if (!form.hidden && view.station) form.elements.station_code.value = view.station;
    };
    bindForm(form, async data => {
      await api.addRecord({...data, hour: Number(data.hour), quantity: Number(data.quantity)});
      for (const [name, value] of Object.entries({start: data.day, end: data.day, station: data.station_code})) {
        filters.elements[name].value = value;
      }
      form.elements.quantity.value = '';
      form.hidden = true;
      await load({start: data.day, end: data.day, station: data.station_code, channel: view.channel || '', page: 1}).catch(showError);
    });
    const importForm = container.querySelector('#import-form');
    const note = container.querySelector('#import-note');
    bindForm(importForm, async data => {
      note.textContent = '';
      const result = await api.importLedger({
        channel: data.channel, filename: data.filename, content: data.content,
        default_station: data.default_station || null, default_day: data.default_day || null,
        start: data.start || view.start, end: data.end || view.end,
      });
      const batch = result.batch;
      note.innerHTML = `${result.replayed ? '该文件已导入过，未重复计件。' : '已导入。'}
        共 ${number(batch.rows_total)} 行，新增 ${number(batch.rows_inserted)}、重复 ${number(batch.rows_duplicate)}、待落位 ${number(batch.rows_unresolved)}。
        <a href="#ledger/${data.default_station || ''}">查看对账 →</a>`;
      importForm.elements.content.value = '';
      await load({...view, start: batch.period_start, end: batch.period_end, page: 1}).catch(showError);
    });
  }
  await load();
}

function reconcileDetail(detail) {
  if (!detail.slots.length && !detail.unresolved.length) {
    return `<div class="recon-sub"><h3>${esc(detail.name || detail.code)} 的对账明细</h3>${blank('该站没有可对的记录', '导入两路联单后，会在这里列出每个槽位的柜机与纸联件数。')}</div>`;
  }
  return `<div class="recon-sub"><h3>${esc(detail.name || detail.code)} 的对账明细
      <span class="tally">${reconStateLabels[detail.state]} · 实收 ${number(detail.actual)} / 争议 ${number(detail.disputed)}</span></h3>
    ${detail.slots.length ? table('槽位对账', ['日期 / 小时', '人工', '柜机', '纸联', '实收', '争议', '状态'], detail.slots.map(slot => `<tr>
      <td class="mono">${slot.day} ${pad(slot.hour)}:00</td><td class="mono">${slot.manual || '—'}</td>
      <td class="mono">${slot.cabinet || '—'}</td><td class="mono">${slot.paper || '—'}</td>
      <td class="mono"><strong>${slot.actual}</strong></td><td class="mono">${slot.disputed || '—'}</td>
      <td>${badge(recordStateLabels[slot.state], slot.state)}</td></tr>`)) : ''}
    ${detail.unresolved.length ? `<p class="hint warn">${detail.unresolved.length} 笔记录缺少日期，未对上；补齐后才能进入实收。</p>` : ''}
  </div>`;
}
