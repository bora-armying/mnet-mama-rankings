"""Flask app to display MNET MAMA rankings with change tracking."""
from flask import Flask, render_template, jsonify, request
import os
from .fetcher import fetch_current_rankings, extract_rankings_summary
from .storage import init_db, save_rankings, get_latest_rankings, get_recent_changes

APP = Flask(__name__, template_folder=os.path.join(os.path.dirname(__file__), '..', 'templates'))
DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'rankings.db')

# Categories shown on the page, in display order
DISPLAY_CATEGORIES = ["FANS' CHOICE MALE", "FANS' CHOICE OF THE YEAR with VISA"]


def page_context(rankings, changes):
    """Build template context limited to DISPLAY_CATEGORIES.

    Each group gets its options sorted by rank, each annotated with
    'movement' (positive = moved up) from the group's most recent update
    in which any rank changed.
    """
    by_name = {g['groupName']: g for g in (rankings or {}).get('groups', [])}
    groups = []
    for name in DISPLAY_CATEGORIES:
        group = by_name.get(name)
        if not group:
            continue
        # changes are newest first; keep only the latest snapshot with movement
        group_changes = [c for c in changes if c['category'] == name]
        latest = [c for c in group_changes if c['snapshot_id'] == group_changes[0]['snapshot_id']] if group_changes else []
        movement = {c['artist_id']: c['change'] for c in latest}
        options = [
            dict(o, movement=movement.get(o['artistId'], 0))
            for o in sorted(group['options'], key=lambda o: o['rank'])
        ]
        groups.append({
            'id': group['groupId'],
            'name': name,
            'options': options,
            'moved_at': latest[0]['detected_at'] if latest else None,
        })
    return {'rankings': rankings, 'groups': groups}


@APP.before_request
def setup():
    """Initialize database on first request."""
    if not hasattr(APP, 'db_initialized'):
        init_db(DB_PATH)
        APP.db_initialized = True


@APP.route('/')
def index():
    """Display current rankings."""
    # Try DB first
    rankings = get_latest_rankings(DB_PATH)
    if not rankings:
        # Fallback to fetcher and persist
        rankings = fetch_current_rankings()
        if rankings:
            save_rankings(DB_PATH, rankings)

    # Get recent changes
    changes = get_recent_changes(DB_PATH, limit=500)

    return render_template('index.html', **page_context(rankings, changes))


@APP.route('/api/rankings')
def api_rankings():
    """API endpoint for current rankings."""
    rankings = get_latest_rankings(DB_PATH)
    if rankings:
        return jsonify(extract_rankings_summary(rankings))
    return jsonify({'error': 'No rankings available'}), 404


@APP.route('/api/changes')
def api_changes():
    """API endpoint for recent ranking changes."""
    limit = int(request.args.get('limit', 50))
    changes = get_recent_changes(DB_PATH, limit=limit)
    return jsonify({'changes': changes})


@APP.route('/refresh')
def refresh():
    """Manually fetch and update rankings."""
    rankings = fetch_current_rankings()
    if rankings:
        save_rankings(DB_PATH, rankings)
        return jsonify({'status': 'success', 'message': 'Rankings updated'})
    return jsonify({'status': 'error', 'message': 'Failed to fetch rankings'}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    APP.run(host='0.0.0.0', port=port, debug=False)
