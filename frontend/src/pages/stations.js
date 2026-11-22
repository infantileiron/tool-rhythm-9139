import {api} from '../api/client.js';
import {blank, heading, table} from '../components/common/board.js';
import {bindForm} from '../hooks/forms.js';
import {workbench} from '../stores/workbench.js';
import {esc} from '../utils/format.js';

export async function stationsPage(container) {
  const canEdit = workbench.user.role === 'analyst';
  workbench.stations = await api.stations();
  container.innerHTML = `${heading('站点卷宗', '从站点进入时段台账，核对归还数量与登记来源。',
    canEdit ? '<button class="primary" id="add-station">登记站点</button>' : '')}
    <form id="station-form" class="entry panel" hidden>
      <h2>登记新站</h2><div class="field-grid">
      <label>站点编号<input name="code" pattern="[A-Z][A-Z0-9\\-]{1,11}" placeholder="X13" required></label>
      <label>站点名称<input name="name" minlength="2" maxlength="60" required></label>
      <label>位置<input name="address" minlength="2" maxlength="100" required></label>
      <label>联络人<input name="steward" minlength="2" maxlength="40" required></label></div>
      <p role="alert" class="error"></p><button type="submit" class="primary">保存站点</button>
    </form>
    <div class="station-layout">
      <section class="panel"><div class="panel-heading"><div><span class="eyebrow">站点名录</span><h2>共享节点 <span class="tally">${workbench.stations.length}</span></h2></div>
        <input type="search" id="station-filter" aria-label="筛选站点" placeholder="查找编号或站名"></div>
        <div id="station-rows"></div>
      </section>
      <aside class="field-note"><span class="eyebrow">归还口径</span><h2>先核对站点，<br>再对两路联单。</h2>
        <p>柜机流水与纸联都按站点、日期和小时进入台账。两路记同一件工具时只计一次，件数对不上的差额不计实收。</p>
        <a href="#ledger">打开归还时段与对账 →</a></aside>
    </div>`;
  const rows = container.querySelector('#station-rows');
  const filter = container.querySelector('#station-filter');
  const show = () => {
    const term = filter.value.trim().toLowerCase();
    const matches = workbench.stations.filter(site => `${site.code} ${site.name}`.toLowerCase().includes(term));
    rows.innerHTML = matches.length ? table('站点卷宗', ['编号', '站点', '所在位置', '联络人', ''], matches.map(site => `
      <tr><td class="mono key">${esc(site.code)}</td><td><strong>${esc(site.name)}</strong></td>
        <td>${esc(site.address)}</td><td>${esc(site.steward)}</td><td><a href="#ledger/${site.code}" aria-label="${esc(site.name)}台账">查台账 ↗</a></td></tr>`)) :
      blank('没有匹配站点', '试试其他站名或编号。');
  };
  filter.oninput = show;
  show();
  if (canEdit) {
    const form = container.querySelector('#station-form');
    container.querySelector('#add-station').onclick = () => {
      form.hidden = !form.hidden;
      if (!form.hidden) form.elements.code.focus();
    };
    bindForm(form, async data => {
      await api.addStation(data);
      await stationsPage(container);
    });
  }
}
