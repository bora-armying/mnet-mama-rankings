from src.storage import init_db, save_rankings
from src.history import kst_hour, load_history, site_history, update_history


def rankings(fetched_at, ranks):
    return {
        'fetchedAt': fetched_at,
        'groups': [{
            'groupName': 'CATEGORY',
            'options': [
                {'artistId': artist, 'title': artist.upper(), 'thumbnailUrl': None, 'rank': rank}
                for artist, rank in ranks.items()
            ],
        }],
    }


def setup_paths(tmp_path):
    db_path = str(tmp_path / 'test.db')
    init_db(db_path)
    return db_path, str(tmp_path / 'history.json')


def test_kst_hour_crosses_midnight():
    assert kst_hour('2026-10-28T15:30:00.000000Z') == '2026-10-29T00'


def test_keeps_first_snapshot_of_each_hour(tmp_path):
    db_path, path = setup_paths(tmp_path)
    save_rankings(db_path, rankings('2026-10-28T11:01:00Z', {'a': 1, 'b': 2}))
    save_rankings(db_path, rankings('2026-10-28T11:06:00Z', {'a': 2, 'b': 1}))
    save_rankings(db_path, rankings('2026-10-28T12:01:00Z', {'a': 2, 'b': 1}))

    assert update_history(db_path, path) == 2
    snapshots = load_history(path)['snapshots']
    assert [s['hour'] for s in snapshots] == ['2026-10-28T20', '2026-10-28T21']
    assert snapshots[0]['groups']['CATEGORY'] == {'a': 1, 'b': 2}
    assert snapshots[0]['ranges']['CATEGORY'] == {'a': [1, 2], 'b': [1, 2]}
    assert snapshots[1]['ranges']['CATEGORY'] == {}


def test_range_catches_movement_that_reverts_within_the_hour(tmp_path):
    db_path, path = setup_paths(tmp_path)
    save_rankings(db_path, rankings('2026-10-28T11:01:00Z', {'a': 3}))
    save_rankings(db_path, rankings('2026-10-28T11:06:00Z', {'a': 1}))
    save_rankings(db_path, rankings('2026-10-28T11:11:00Z', {'a': 5}))
    save_rankings(db_path, rankings('2026-10-28T11:16:00Z', {'a': 3}))
    update_history(db_path, path)

    snapshot = load_history(path)['snapshots'][0]
    assert snapshot['groups']['CATEGORY'] == {'a': 3}
    assert snapshot['ranges']['CATEGORY'] == {'a': [1, 5]}


def test_latest_hour_keeps_updating_until_a_new_hour_is_added(tmp_path):
    db_path, path = setup_paths(tmp_path)
    save_rankings(db_path, rankings('2026-10-28T11:01:00Z', {'a': 3}))
    assert update_history(db_path, path) == 1

    save_rankings(db_path, rankings('2026-10-28T11:30:00Z', {'a': 1}))
    assert update_history(db_path, path) == 0
    assert load_history(path)['snapshots'][0]['ranges']['CATEGORY'] == {'a': [1, 3]}


def test_existing_hours_survive_a_lost_database(tmp_path):
    db_path, path = setup_paths(tmp_path)
    save_rankings(db_path, rankings('2026-10-28T11:01:00Z', {'a': 1}))
    update_history(db_path, path)

    new_db = str(tmp_path / 'new.db')
    init_db(new_db)
    save_rankings(new_db, rankings('2026-10-28T11:30:00Z', {'a': 9}))
    save_rankings(new_db, rankings('2026-10-28T12:01:00Z', {'a': 3}))

    assert update_history(new_db, path) == 1
    snapshots = load_history(path)['snapshots']
    assert [s['groups']['CATEGORY']['a'] for s in snapshots] == [1, 3]
    assert snapshots[0]['ranges']['CATEGORY'] == {'a': [1, 9]}


def test_site_history_aligns_ranks_to_latest_order(tmp_path):
    db_path, path = setup_paths(tmp_path)
    save_rankings(db_path, rankings('2026-10-28T11:01:00Z', {'a': 1, 'gone': 2}))
    save_rankings(db_path, rankings('2026-10-28T12:01:00Z', {'b': 1, 'a': 2}))
    update_history(db_path, path)

    site = site_history(load_history(path), 'CATEGORY')
    assert [a['id'] for a in site['artists']] == ['b', 'a', 'gone']
    assert [s['ranks'] for s in site['snapshots']] == [[None, 1, 2], [1, 2, None]]
    assert site['snapshots'][0]['ranges'] == {}
