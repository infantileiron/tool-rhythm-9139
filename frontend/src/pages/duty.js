import {api} from '../api/client.js';
import {badge, blank, heading, table} from '../components/common/board.js';
import {exceptionNotes, runLabels, stationLabels} from '../constants/domain.js';
import {bindForm} from '../hooks/forms.js';
import {workbench} from '../stores/workbench.js';
import {saveDownload} from '../utils/dom.js';
import {band, esc, localDateTime} from '../utils/format.js';

export async function dutyPage(container, id) {
  const admin = workbench.user.role === 'admin';
  if (id && !/^\d+$/.test(id)) throw new Error('方案版本号无效');
  const runs = (await api.runs()).filter(run => run.status === 'published' || (admin && run.status === 'ready'));
  if (!id) {
    container.innerHTML = `${heading('值班安排', '复核分组建议与例外站点，发布后可下载值班单。')}
      <section class="panel"><div class="panel-heading"><h2>值守方案</h2></div>
      ${runs.length ? table('值守方案', ['版本', '方案', '状态', ''], runs.map(run => `<tr>
        <td class="mono key">V${run.id}</td><td>${esc(run.title)}</td><td>${badge(runLabels[run.status], run.status)}</td>
        <td><a href="#duty/${run.id}">${run.status === 'ready' ? '复核安排' : '查看值班单'} →</a></td></tr>`)) :
        blank('没有可查阅的值守方案', '待计算完成、负责人核对并发布后，可在这里查看值班单。', '<a href="#analysis">打开分型方案 →</a>')}</section>`;
    return;
  }
  if (!runs.some(run => String(run.id) === id)) throw new Error('该方案当前不在值班安排中');
  const run = await api.run(id);
  const {groups, members} = run.result;
  const exceptions = members.filter(member => member.status in exceptionNotes);
  const {start, end} = run.snapshot.params;
  const published = run.status === 'published';
  container.innerHTML = `<a class="back" href="#duty">← 值班安排</a>
    ${heading(run.title, `V${run.id} · ${start} 至 ${end} · ${runLabels[run.status]}`, published ? '<button class="primary" id="download">下载值班单 CSV</button>' : '')}
    <p role="alert" class="error" id="duty-error"></p>
    ${published ? `<section class="panel published-note"><span class="eyebrow">发布记录</span><h2>本期值守说明</h2>
      <p>${esc(run.decision.memo)}</p><small>发布人 ${esc(run.decision.reviewer)} · ${localDateTime(run.published_at)}</small></section>
      <section class="panel"><div class="panel-heading"><h2>分组安排</h2></div>${groupTable(groups, run)}</section>
      <section class="panel"><div class="panel-heading"><h2>例外处置</h2></div>${exceptionTable(exceptions, run)}</section>` :
      `<form id="publish-form"><section class="panel review-panel"><div class="panel-heading"><h2>分组安排</h2><a href="#analysis/${id}">查看计算结果 ↗</a></div>
      ${groupTable(groups, run)}</section><section class="panel review-panel"><div class="panel-heading"><h2>例外处置</h2></div>${exceptionTable(exceptions, run)}</section>
      <section class="panel entry"><label>复核说明<textarea name="memo" minlength="4" maxlength="240" rows="2" required></textarea></label>
      <p role="alert" class="error"></p><button class="primary" type="submit">发布值班安排</button></section></form>`}`;
  if (published) {
    const button = container.querySelector('#download');
    const message = container.querySelector('#duty-error');
    button.onclick = async () => {
      button.disabled = true;
      message.textContent = '';
      try {
        saveDownload(await api.download(id), `duty-v${id}.csv`);
      } catch (error) {
        message.textContent = error.message;
      } finally {
        button.disabled = false;
      }
    };
  } else {
    bindForm(container.querySelector('#publish-form'), async data => {
      await api.publish(id, {memo: data.memo,
        groups: Object.fromEntries(groups.map(group => [group.key, data[`group-${group.key}`]])),
        exceptions: Object.fromEntries(exceptions.map(member => [member.code, data[`exception-${member.code}`]]))});
      await dutyPage(container, id);
    });
  }
}

function groupTable(groups, run) {
  if (!groups.length) return blank('本期无分组', '请填写例外站点的复查安排。');
  return table('分组安排', ['分组与峰段', '站点', '值守安排'], groups.map(group => `<tr>
    <td><strong class="key mono">${group.key}</strong><br>${band(run.snapshot.bands[group.peak])}</td>
    <td class="mono">${group.station_codes.join(' / ')}</td>
    <td>${run.decision ? esc(run.decision.groups[group.key]) :
      `<textarea name="group-${group.key}" aria-label="${group.key} 值守安排" minlength="4" maxlength="240" rows="2" required>${esc(group.advice)}</textarea>`}</td></tr>`));
}

function exceptionTable(exceptions, run) {
  if (!exceptions.length) return blank('本期无例外', '窗口内所有站点均已有分组安排。');
  return table('例外处置', ['站点', '类型', '处置意见'], exceptions.map(member => `<tr>
    <td><span class="key mono">${member.code}</span> · ${esc(member.name)}</td><td>${badge(stationLabels[member.status], member.status)}</td>
    <td>${run.decision ? esc(run.decision.exceptions[member.code]) :
      `<textarea name="exception-${member.code}" aria-label="${member.code} 处置意见" minlength="4" maxlength="240" rows="2" placeholder="${exceptionNotes[member.status]}" required></textarea>`}</td></tr>`));
}
