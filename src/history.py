"""Hourly ranking history, committed to the repo as a JSON file.

Each KST hour keeps the ranks from its first fetch, plus each artist's best
and lowest rank across every fetch in that hour. Saved ranks are never
overwritten and ranges only widen, so the file stays the permanent record
even if the SQLite database (which lives in the Actions cache) is lost.

Usage:
    python3 -m src.history
"""
import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Dict, List
from .storage import init_db

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'rankings.db')
HISTORY_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'hourly_rankings.json')
KST = timezone(timedelta(hours=9))


def kst_hour(fetched_at: str) -> str:
    """Convert an ISO timestamp to its KST hour, e.g. '2026-10-28T20'."""
    parsed = datetime.fromisoformat(fetched_at.replace('Z', '+00:00'))
    return parsed.astimezone(KST).strftime('%Y-%m-%dT%H')


def load_history(path: str = HISTORY_PATH) -> Dict:
    """Load the history file, or an empty history if it doesn't exist yet."""
    if not os.path.exists(path):
        return {'artists': {}, 'snapshots': []}
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def save_history(history: Dict, path: str = HISTORY_PATH):
    """Write the history with one snapshot per line to keep git diffs small."""
    dump = lambda value: json.dumps(value, ensure_ascii=False, sort_keys=True)
    snapshots = ',\n'.join(dump(s) for s in history['snapshots'])
    with open(path, 'w', encoding='utf-8') as f:
        f.write('{\n"artists": ' + dump(history['artists']) + ',\n')
        f.write('"snapshots": [\n' + snapshots + '\n]\n}\n')


def add_snapshot(history: Dict, hour: str, data: Dict):
    """Add the ranks from one API response to the history."""
    groups = {}
    for group in data['groups']:
        groups[group['groupName']] = {o['artistId']: o['rank'] for o in group['options']}
        for option in group['options']:
            history['artists'][option['artistId']] = {
                'title': option['title'],
                'thumbnailUrl': option.get('thumbnailUrl'),
            }
    history['snapshots'].append({
        'hour': hour,
        'fetchedAt': data.get('fetchedAt'),
        'groups': groups,
    })


def merge_ranges(snapshot: Dict, data: Dict):
    """Widen a snapshot's [best, lowest] ranges with another fetch from its hour.

    Only artists that moved within the hour get a range.
    """
    ranges = snapshot.setdefault('ranges', {})
    for group in data['groups']:
        name = group['groupName']
        first = snapshot['groups'].get(name, {})
        group_ranges = ranges.setdefault(name, {})
        for option in group['options']:
            artist_id, rank = option['artistId'], option['rank']
            start = first.get(artist_id, rank)
            best, lowest = group_ranges.get(artist_id, [start, start])
            best, lowest = min(best, rank), max(lowest, rank)
            if best != lowest:
                group_ranges[artist_id] = [best, lowest]


def update_history(db_path: str = DB_PATH, path: str = HISTORY_PATH) -> int:
    """Add missing hours and update the ranges of the latest saved hour onward.

    Earlier hours are complete, so their snapshots aren't read again.

    Returns:
        Number of hours added
    """
    history = load_history(path)
    by_hour = {s['hour']: s for s in history['snapshots']}
    latest_saved = max(by_hour, default='')
    added = 0

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT id, fetched_at FROM rankings_snapshots ORDER BY id")
    for snapshot_id, fetched_at in cur.fetchall():
        hour = kst_hour(fetched_at)
        if hour in by_hour and hour < latest_saved:
            continue
        cur.execute("SELECT data FROM rankings_snapshots WHERE id = ?", (snapshot_id,))
        data = json.loads(cur.fetchone()[0])
        if not isinstance(data, dict) or 'groups' not in data:
            continue
        if hour not in by_hour:
            add_snapshot(history, hour, data)
            by_hour[hour] = history['snapshots'][-1]
            added += 1
        merge_ranges(by_hour[hour], data)
    conn.close()

    history['snapshots'].sort(key=lambda s: s['hour'])
    save_history(history, path)
    return added


def site_history(history: Dict, category: str) -> Dict:
    """Build the compact history of one category for the page.

    Artists are ordered by their latest rank, and each snapshot's ranks line
    up with that order (None if the artist wasn't in that snapshot). Ranges
    are keyed by the artist's position in that order.
    """
    snapshots = [s for s in history['snapshots'] if category in s['groups']]
    if not snapshots:
        return {'artists': [], 'snapshots': []}

    latest = snapshots[-1]['groups'][category]
    ids: List[str] = sorted(latest, key=lambda artist_id: latest[artist_id])
    for snapshot in snapshots:
        ids += [artist_id for artist_id in snapshot['groups'][category] if artist_id not in ids]

    return {
        'artists': [dict(history['artists'][artist_id], id=artist_id) for artist_id in ids],
        'snapshots': [
            {
                'hour': s['hour'],
                'fetchedAt': s['fetchedAt'],
                'ranks': [s['groups'][category].get(artist_id) for artist_id in ids],
                'ranges': {
                    ids.index(artist_id): artist_range
                    for artist_id, artist_range in s.get('ranges', {}).get(category, {}).items()
                    if artist_id in ids
                },
            }
            for s in snapshots
        ],
    }


if __name__ == "__main__":
    init_db(DB_PATH)
    # The workflow commits the file only when this count is above zero
    print(update_history())
