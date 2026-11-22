import {esc} from '../../utils/format.js';

export const heading = (title, text, actions = '') => `
  <header class="page-heading"><div><h1>${esc(title)}</h1><p>${esc(text)}</p></div>${actions}</header>`;

export const badge = (label, status = '') => `<span class="badge ${esc(status)}">${esc(label)}</span>`;

export const blank = (title, text, action = '') => `
  <div class="blank"><h3>${esc(title)}</h3><p>${esc(text)}</p>${action}</div>`;

export function table(label, columns, rows) {
  return `<div class="table-scroll" tabindex="0" role="region" aria-label="${esc(label)}"><table>
    <thead><tr>${columns.map(column => `<th scope="col">${esc(column)}</th>`).join('')}</tr></thead>
    <tbody>${rows.join('')}</tbody></table></div>`;
}
