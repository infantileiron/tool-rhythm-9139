const KEY = 'tool-rhythm-session';

export const workbench = {
  user: JSON.parse(sessionStorage.getItem(KEY) || 'null'),
  stations: [],
  runs: [],
  ledger: {start: '2026-11-09', end: '2026-11-15', station: '', page: 1},
  signIn(user) {
    this.user = user;
    sessionStorage.setItem(KEY, JSON.stringify(user));
  },
  signOut() {
    this.user = null;
    this.stations = [];
    this.runs = [];
    this.ledger = {start: '2026-11-09', end: '2026-11-15', station: '', page: 1};
    sessionStorage.removeItem(KEY);
  },
};
