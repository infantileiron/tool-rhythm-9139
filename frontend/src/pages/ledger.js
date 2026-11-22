import {api} from '../api/client.js';
import {badge, blank, heading, table} from '../components/common/board.js';
import {bindForm} from '../hooks/forms.js';
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
  container.innerHTML = `${heading('归还时段', '按北京时间登记每个站点每小时的归还件数。',
    canEdit ? '<button class="primary" id="new-record">补录归还</button>' : '')}
    <section class="panel"><form id="ledger-filter" class="filters">
      <label>起日<input name="start" type="date" value="${esc(view.start)}" required></label>
      <label>止日<input name="end" type="date" value="${esc(view.end)}" required></label>
      <label>站点<select name="station"><option value="">全部站点</option>${options}</select></label>
      <button class="secondary" type="submit">查询台账</button><p role="alert" class="error"></p>
    </form></section>
    <form id="record-form" class="entry panel" hidden>
      <h2>补录归还</h2><div class="field-grid">
        <label>站点<select name="station_code" required>${options}</select></label>
        <label>归还日期<input name="day" type="date" value="${esc(view.end)}" required></label>
        <label>起始小时<input name="hour" type="number" min="0" max="23" value="10" required></label>
        <label>件数<input name="quantity" type="number" min="1" max="9999" required></label>
        <label>来源联单<input name="source" minlength="2" maxlength="80" placeholder="回收联_1115补记.csv" required></label>
      </div><p role="alert" class="error"></p><button type="submit" class="primary">保存归还</button>
    </form>
    <section class="panel" id="ledger-list"><p class="loading">正在读取台账…</p></section>
    <dialog id="correction"><form class="entry"><h2>校正归还记录</h2><p id="record-meta"></p>
      <label>件数<input name="quantity" type="number" min="1" max="9999" required></label>
      <label>来源联单<input name="source" minlength="2" maxlength="80" required></label>
      <p role="alert" class="error"></p><div class="actions"><button type="submit" class="primary">保存校正</button><button type="button" class="secondary" data-close>取消</button></div>
    </form></dialog>`;
  const filters = container.querySelector('#ledger-filter');
  filters.elements.station.value = view.station;
  const ledger = container.querySelector('#ledger-list');
  const dialog = container.querySelector('#correction');
  let editing;
  const load = async (query = view) => {
    const {start, end, station, page} = query;
    const {total, quantity, items} = await api.records({start, end}, station, page);
    if (!container.isConnected) return;
    Object.assign(view, query);
    ledger.innerHTML = `<div class="panel-heading"><div><span class="eyebrow">小时归还联</span><h2>归还记录 <span class="tally">${number(total)} 笔</span></h2></div><strong class="key">${number(quantity)} 件</strong></div>` +
      (items.length ? table('归还记录', ['日期 / 小时', '站点', '件数', '联单', '修订', ...(canEdit ? ['操作'] : [])], items.map(row => `
        <tr><td class="mono">${row.day} <strong>${pad(row.hour)}:00</strong></td><td>${esc(row.name)} <small>${row.station_code}</small></td>
        <td><strong>${row.quantity}</strong></td><td>${esc(row.source)}</td><td>${badge(`R${row.revision}`)}</td>
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
        dialog.querySelector('#record-meta').textContent = `${editing.name} · ${editing.day} ${pad(editing.hour)}:00 · R${editing.revision}`;
        dialog.querySelector('[role=alert]').textContent = '';
        dialog.querySelector('[name=quantity]').value = editing.quantity;
        dialog.querySelector('[name=source]').value = editing.source;
        dialog.showModal();
      };
    }
  };
  const showError = error => filters.querySelector('[role=alert]').textContent = error.message;
  bindForm(filters, data => load({...data, page: 1}));
  dialog.querySelector('[data-close]').onclick = () => dialog.close();
  bindForm(dialog.querySelector('form'), async data => {
    await api.correctRecord(editing.id, {...data, quantity: Number(data.quantity), revision: editing.revision});
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
      await load({start: data.day, end: data.day, station: data.station_code, page: 1}).catch(showError);
    });
  }
  await load();
}
