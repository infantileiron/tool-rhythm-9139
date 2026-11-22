from collections import deque
from math import sqrt

from src.constants.domain import ReconState, StationStatus as Status


def unit_vector(counts):
    norm = sqrt(sum(value * value for value in counts))
    return [value / norm for value in counts]


def neighborhoods(vectors, eps):
    adjacent = {code: {code} for code in vectors}
    points = list(vectors.items())
    for index, (left, a) in enumerate(points):
        for right, b in points[index + 1:]:
            distance = max(0.0, 1.0 - sum(x * y for x, y in zip(a, b)))
            if distance <= eps + 1e-12:
                adjacent[left].add(right)
                adjacent[right].add(left)
    return {code: sorted(neighbors) for code, neighbors in adjacent.items()}


def dbscan(adjacent, min_points):
    core = {code for code, links in adjacent.items() if len(links) >= min_points}
    labels = {}
    cluster = 0
    for root in sorted(core):
        if root in labels:
            continue
        cluster += 1
        label = f'G{cluster:02d}'
        labels[root] = label
        queue = deque([root])
        while queue:
            for neighbor in adjacent[queue.popleft()]:
                if neighbor in labels:
                    continue
                labels[neighbor] = label
                if neighbor in core:
                    queue.append(neighbor)
    return labels, core


def has_usable_vector(site, params):
    """能进入分型的站点：对账后有实收、不是未对账/无记录状态、且实收达到件数门槛。"""
    return (site.get('recon_state') not in (ReconState.UNRECONCILED, ReconState.NO_DATA)
            and sum(site['counts']) >= params['min_returns'])


def classify(snapshot):
    params = snapshot['params']
    sites = sorted(snapshot['stations'], key=lambda site: site['code'])
    vectors = {s['code']: unit_vector(s['counts']) for s in sites if has_usable_vector(s, params)}
    adjacent = neighborhoods(vectors, params['eps'])
    labels, core = dbscan(adjacent, params['min_points'])
    members = []
    for site in sites:
        code, counts = site['code'], site['counts']
        total = sum(counts)
        recon_state = site.get('recon_state', ReconState.CLEAN)
        group = labels.get(code)
        if recon_state == ReconState.UNRECONCILED:
            status = Status.UNRECONCILED
        elif recon_state == ReconState.NO_DATA or not total:
            status = Status.EMPTY
        elif code not in vectors:
            status = Status.LOW
        elif not group:
            status = Status.NOISE
        else:
            status = Status.CORE if code in core else Status.BORDER
        members.append({**site, 'total': total, 'group': group, 'status': status,
                        'neighbors': len(adjacent[code]) if code in adjacent else None,
                        'profile': [n / total for n in counts] if total else None})
    groups = []
    for label in sorted(set(labels.values())):
        cohort = [member for member in members if member['group'] == label]
        profile = [sum(values) / len(cohort) for values in zip(*(m['profile'] for m in cohort))]
        peak = profile.index(max(profile))
        start, end = snapshot['bands'][peak]
        action = (f'优先安排 {start:02d}:00–{end:02d}:00 值守，按站点件数核定人手。'
                  if start >= 8 and start < 20 else
                  f'核对 {start:02d}:00–{end:02d}:00 自助柜记录，确认峰值后安排巡检。')
        groups.append({'key': label, 'station_codes': [m['code'] for m in cohort],
                       'profile': profile, 'peak': peak, 'advice': action,
                       'returns': sum(m['total'] for m in cohort)})
    return {'groups': groups, 'members': members,
            'diagnostics': {'eligible': len(vectors), 'stations': len(sites),
                            'returns': sum(m['total'] for m in members),
                            'disputed': sum(m.get('disputed', 0) for m in members),
                            'unreconciled': sum(1 for m in members if m['status'] == Status.UNRECONCILED),
                            'partial': sum(1 for m in members if m.get('recon_state') == ReconState.PARTIAL)}}
