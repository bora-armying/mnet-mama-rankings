"""SQLite storage for MAMA rankings with change tracking."""
import sqlite3
from typing import Dict, Optional, List
import json
from datetime import datetime


def init_db(db_path: str):
    """Initialize the database with tables for rankings and changes."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Table for storing full API snapshots
    cur.execute("""
    CREATE TABLE IF NOT EXISTS rankings_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data TEXT NOT NULL,
        updated_at TEXT,
        fetched_at TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Table for tracking individual artist ranking changes
    cur.execute("""
    CREATE TABLE IF NOT EXISTS ranking_changes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        snapshot_id INTEGER NOT NULL,
        category TEXT NOT NULL,
        artist_id TEXT NOT NULL,
        artist_name TEXT NOT NULL,
        old_rank INTEGER,
        new_rank INTEGER NOT NULL,
        rank_change INTEGER,
        detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (snapshot_id) REFERENCES rankings_snapshots(id)
    )
    """)

    # Index for faster queries
    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_artist_changes
    ON ranking_changes(artist_id, category, detected_at)
    """)

    conn.commit()
    conn.close()


def save_rankings(db_path: str, rankings_data: Dict) -> int:
    """Save a rankings snapshot and detect changes.

    Args:
        db_path: Path to SQLite database
        rankings_data: Full API response data

    Returns:
        ID of the saved snapshot
    """
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Save the snapshot
    cur.execute(
        "INSERT INTO rankings_snapshots (data, updated_at, fetched_at) VALUES (?, ?, ?)",
        (
            json.dumps(rankings_data),
            rankings_data.get('updatedAt'),
            rankings_data.get('fetchedAt', datetime.utcnow().isoformat() + 'Z')
        )
    )
    snapshot_id = cur.lastrowid

    # Get previous rankings for comparison
    cur.execute("""
        SELECT data FROM rankings_snapshots
        WHERE id < ?
        ORDER BY id DESC LIMIT 1
    """, (snapshot_id,))

    prev_row = cur.fetchone()
    if prev_row:
        prev_data = json.loads(prev_row[0])
        changes = detect_ranking_changes(prev_data, rankings_data)

        # Save detected changes
        for change in changes:
            cur.execute("""
                INSERT INTO ranking_changes
                (snapshot_id, category, artist_id, artist_name, old_rank, new_rank, rank_change)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                snapshot_id,
                change['category'],
                change['artist_id'],
                change['artist_name'],
                change['old_rank'],
                change['new_rank'],
                change['rank_change']
            ))

    conn.commit()
    conn.close()
    return snapshot_id


def detect_ranking_changes(old_data: Dict, new_data: Dict) -> List[Dict]:
    """Detect ranking changes between two snapshots.

    Args:
        old_data: Previous API response
        new_data: Current API response

    Returns:
        List of detected changes
    """
    changes = []

    # Build lookup for old rankings
    old_rankings = {}
    if 'groups' in old_data:
        for group in old_data['groups']:
            category = group['groupName']
            for option in group['options']:
                key = (category, option['artistId'])
                old_rankings[key] = option['rank']

    # Compare with new rankings
    if 'groups' in new_data:
        for group in new_data['groups']:
            category = group['groupName']
            for option in group['options']:
                key = (category, option['artistId'])
                new_rank = option['rank']
                old_rank = old_rankings.get(key)

                if old_rank is not None and old_rank != new_rank:
                    changes.append({
                        'category': category,
                        'artist_id': option['artistId'],
                        'artist_name': option['title'],
                        'old_rank': old_rank,
                        'new_rank': new_rank,
                        'rank_change': old_rank - new_rank  # Positive means moved up
                    })

    return changes


def get_latest_rankings(db_path: str) -> Optional[Dict]:
    """Get the most recent rankings snapshot.

    Returns:
        The latest rankings data or None if no data exists
    """
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT data FROM rankings_snapshots ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    conn.close()
    if row:
        return json.loads(row[0])
    return None


def get_recent_changes(db_path: str, limit: int = 50) -> List[Dict]:
    """Get recent ranking changes.

    Args:
        db_path: Path to SQLite database
        limit: Maximum number of changes to return

    Returns:
        List of recent ranking changes
    """
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        SELECT category, artist_name, old_rank, new_rank, rank_change, detected_at,
               artist_id, snapshot_id
        FROM ranking_changes
        ORDER BY snapshot_id DESC, id DESC
        LIMIT ?
    """, (limit,))

    changes = []
    for row in cur.fetchall():
        changes.append({
            'category': row[0],
            'artist': row[1],
            'old_rank': row[2],
            'new_rank': row[3],
            'change': row[4],
            'detected_at': row[5],
            'artist_id': row[6],
            'snapshot_id': row[7]
        })

    conn.close()
    return changes


def get_artist_history(db_path: str, artist_id: str, category: str) -> List[Dict]:
    """Get ranking history for a specific artist in a category.

    Args:
        db_path: Path to SQLite database
        artist_id: Artist ID to look up
        category: Category name

    Returns:
        List of ranking changes for the artist
    """
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        SELECT new_rank, detected_at
        FROM ranking_changes
        WHERE artist_id = ? AND category = ?
        ORDER BY detected_at ASC
    """, (artist_id, category))

    history = []
    for row in cur.fetchall():
        history.append({
            'rank': row[0],
            'timestamp': row[1]
        })

    conn.close()
    return history
