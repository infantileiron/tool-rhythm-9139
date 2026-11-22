import {blank} from './components/common/board.js';
import {roles} from './constants/domain.js';
import {analysisPage} from './pages/analysis.js';
import {dutyPage} from './pages/duty.js';
import {ledgerPage} from './pages/ledger.js';
import {loginPage} from './pages/login.js';
import {stationsPage} from './pages/stations.js';
import {locationRoute, routes} from './router/routes.js';
import {workbench} from './stores/workbench.js';
import {scrollTop} from './utils/dom.js';
import {esc} from './utils/format.js';

const root = document.querySelector('#app');
const pages = {stations: stationsPage, ledger: ledgerPage, analysis: analysisPage, duty: dutyPage};

function showLogin(notice = '') {
  loginPage(root, user => {
    workbench.signIn(user);
    render();
  }, notice);
}

async function render() {
  const user = workbench.user;
  if (!user) return showLogin();
  const {route, id} = locationRoute();
  root.innerHTML = `<div class="app-shell">
    <aside class="rail">
      <a class="press-brand" href="#stations"><span class="press-mark">溪</span><span>溪巷工坊<br><small>工具站值班板</small></span></a>
      <nav aria-label="业务导航">${routes.map(item => `<a href="#${item.key}" ${route.key === item.key ? 'aria-current="page"' : ''}>
        <span aria-hidden="true">${item.mark}</span>${item.label}</a>`).join('')}</nav>
      <div class="rail-bottom"><span>社区工具共用网络</span><small>北京时间 UTC+8</small></div>
    </aside>
    <div class="workspace"><header class="topline"><span>共享工具站节律分型</span><div class="identity"><span>${esc(user.name.split(' · ')[0])}</span>
      <span class="user-role">${esc(roles[user.role])}</span><button class="text-button" id="sign-out">退出</button></div></header>
      <main id="page" class="page"><p class="loading">正在读取${route.label}…</p></main></div></div>`;
  root.querySelector('#sign-out').onclick = () => leave();
  const container = root.querySelector('#page');
  scrollTop();
  try {
    await pages[route.key](container, id);
  } catch (error) {
    if (!container.isConnected) return;
    container.innerHTML = blank('无法打开页面', error.message, '<button type="button" class="secondary" id="retry">重试</button>');
    container.querySelector('#retry').onclick = render;
  }
}

function leave(notice) {
  workbench.signOut();
  history.replaceState(null, '', location.pathname);
  showLogin(notice);
  scrollTop();
}

window.addEventListener('hashchange', render);
document.addEventListener('session-expired', () => leave('登录已过期，请重新登录。'));
render();
