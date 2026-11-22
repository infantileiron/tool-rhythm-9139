import {band, number, pct} from '../utils/format.js';

export function profileChart(profile, bands, peak) {
  return `<div class="profile" aria-label="分组时段画像">${bands.map((range, index) => `
      <div class="profile-row ${peak === index ? 'peak' : ''}">
        <span>${band(range)}</span><div class="track"><i style="width:${pct(profile[index])}"></i></div>
        <strong>${pct(profile[index])}</strong>
      </div>`).join('')}</div>`;
}

export function vectorSummary(member) {
  return `<span class="vector" aria-label="六个时段归还件数">${member.counts.map(n => `<span>${number(n)}</span>`).join('')}</span>`;
}
