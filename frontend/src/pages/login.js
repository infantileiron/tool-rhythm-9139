import {api} from '../api/client.js';
import {bindForm} from '../hooks/forms.js';
import {esc} from '../utils/format.js';

export function loginPage(root, authenticate, notice = '') {
  root.innerHTML = `
    <main class="login">
      <div class="login-cover">
        <div class="press-brand"><span class="press-mark">溪</span><span>溪巷工坊<br><small>社区工具共用网络</small></span></div>
        <div class="login-title"><span class="cover-tag">借用归还 / 值守调度</span><h1>共享工具站<br><em>节律分型</em></h1>
          <p>从分时归还记录识别工具站的忙时，按组排值班，逐站复核例外。</p></div>
        <div class="cover-ruler" aria-hidden="true"><span>00</span><span>08</span><span>11</span><span>14</span><span>17</span><span>20</span><span>24</span></div>
        <div class="cover-footer">归还记录一律使用北京时间 UTC+8</div>
      </div>
      <div class="login-side"><form id="login-form" class="login-form">
        <span class="eyebrow">溪巷工坊值班板</span><h2>登录工作台</h2>
        <label>账号<input name="username" autocomplete="username" required></label>
        <label>密码<input name="password" type="password" autocomplete="current-password" required></label>
        <p class="error" role="alert">${esc(notice)}</p>
        <button type="submit" class="primary">进入值班板 <span aria-hidden="true">→</span></button>
        <div class="demo-login"><span>演示账号</span><div>${[['analyst', '分析员'], ['admin', '负责人'], ['observer', '观察员']].map(([key, label]) => `<button type="button" data-account="${key}">${label}</button>`).join('')}</div></div>
      </form></div>
    </main>`;
  const form = root.querySelector('form');
  for (const button of form.querySelectorAll('[data-account]')) {
    button.onclick = () => {
      form.elements.username.value = button.dataset.account;
      form.elements.password.value = 'Workbench-5206';
    };
  }
  bindForm(form, async data => authenticate(await api.login(data)));
}
