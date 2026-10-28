"""Render the rankings page to static HTML for GitHub Pages.

Usage:
    python3 -m src.build_static [--out _site]
"""
import os
import sys
import json
import argparse
from .app import APP, DB_PATH, page_context
from .fetcher import extract_rankings_summary
from .storage import init_db, get_latest_rankings, get_recent_changes


def build(out_dir: str) -> bool:
    """Write index.html and JSON snapshots of the latest rankings to out_dir."""
    init_db(DB_PATH)
    rankings = get_latest_rankings(DB_PATH)
    if not rankings:
        print("ERROR: No rankings in database; run `python3 -m src.scheduler --once` first")
        return False

    changes = get_recent_changes(DB_PATH, limit=500)
    os.makedirs(out_dir, exist_ok=True)

    with APP.app_context():
        html = APP.jinja_env.get_template('index.html').render(
            **page_context(rankings, changes), static_site=True
        )

    with open(os.path.join(out_dir, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(html)
    with open(os.path.join(out_dir, 'rankings.json'), 'w', encoding='utf-8') as f:
        json.dump(extract_rankings_summary(rankings), f, ensure_ascii=False, indent=2)
    with open(os.path.join(out_dir, 'changes.json'), 'w', encoding='utf-8') as f:
        json.dump({'changes': get_recent_changes(DB_PATH, limit=50)}, f, ensure_ascii=False, indent=2)

    print(f"Built static site in {os.path.abspath(out_dir)}")
    return True


def main():
    parser = argparse.ArgumentParser(description='Build static rankings site')
    parser.add_argument('--out', default='_site', help='Output directory (default: _site)')
    args = parser.parse_args()
    sys.exit(0 if build(args.out) else 1)


if __name__ == "__main__":
    main()
