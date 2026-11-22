export const routes = [
  {key: 'stations', label: '站点卷宗', mark: '▦'},
  {key: 'ledger', label: '归还时段', mark: '≡'},
  {key: 'analysis', label: '密度分型', mark: '◈'},
  {key: 'duty', label: '值班安排', mark: '▤'},
];

export function locationRoute() {
  const [key, id] = location.hash.slice(1).split('/');
  return {route: routes.find(item => item.key === key) || routes[0], id};
}

export function go(key, id) {
  location.hash = id ? `${key}/${id}` : key;
}
