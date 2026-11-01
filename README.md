# MNET MAMA Rankings Tracker

A Python application to track and monitor MAMA (Mnet Asian Music Awards) rankings in real-time, with automatic change detection and historical tracking.

## Features

- **Real-time API Integration**: Fetches current rankings from the official MAMA voting API
- **Change Tracking**: Automatically detects and records ranking changes over time
- **Historical Data**: Stores all ranking snapshots in SQLite database
- **Web Interface**: Flask app to view current rankings and recent changes
- **Periodic Updates**: Scheduler to automatically fetch rankings at configurable intervals
- **REST API**: JSON endpoints for programmatic access

## Quick Start

### 1. Setup Environment

```bash
# Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Fetch Rankings (One-time)

```bash
# Fetch current rankings once
python3 -m src.scheduler --once
```

### 3. Run the Web App

```bash
# Start the Flask web server
python3 -m src.app
```

Open http://127.0.0.1:5000/ in your browser to view rankings.

## Hourly history

The GitHub Pages workflow saves each KST hour to `data/hourly_rankings.json`:
the ranks from the hour's first fetch, plus each artist's best and lowest rank
across every fetch in that hour. A new hour commits the file. The page reads it
for its hour picker and rank chart. To update it from the local database, run
`python3 -m src.history`.

## Usage

### Continuous Monitoring

Run the scheduler to periodically fetch rankings:

```bash
# Fetch every hour (default)
python3 -m src.scheduler

# Fetch every 30 minutes
python3 -m src.scheduler --interval 30

# Fetch every 5 minutes
python3 -m src.scheduler --interval 5
```

Press `Ctrl+C` to stop the scheduler.

### Cron Job Setup

For production use, set up a cron job to run the scheduler:

```bash
# Edit crontab
crontab -e

# Add this line to run every hour
0 * * * * cd /path/to/mnet-mama-rankings && .venv/bin/python -m src.scheduler --once
```

### API Endpoints

The Flask app provides the following endpoints:

- `GET /` - Web interface showing current rankings
- `GET /api/rankings` - JSON of current rankings summary
- `GET /api/changes?limit=50` - JSON of recent ranking changes
- `GET /refresh` - Manually trigger a rankings update

Example API usage:

```bash
# Get current rankings
curl http://127.0.0.1:5000/api/rankings

# Get last 20 ranking changes
curl http://127.0.0.1:5000/api/changes?limit=20

# Manually refresh data
curl http://127.0.0.1:5000/refresh
```

## Project Structure

```
mnet-mama-rankings/
├── src/
│   ├── __init__.py
│   ├── fetcher.py       # API client for MAMA rankings
│   ├── storage.py       # SQLite database operations
│   ├── app.py           # Flask web application
│   └── scheduler.py     # Periodic fetcher daemon
├── data/
│   ├── mama_rankings_latest.json  # Latest API response
│   ├── sample_rankings.json       # Sample data
│   └── rankings.db                # SQLite database (auto-created)
├── templates/           # HTML templates for web UI
├── tests/
│   ├── test_fetcher.py
│   └── test_storage.py
├── requirements.txt
└── README.md
```

## Data Structure

### API Response

The MAMA API returns rankings organized into three categories:

1. **FANS' CHOICE MALE** - Male artist rankings
2. **FANS' CHOICE FEMALE** - Female artist rankings
3. **VISA FANS' CHOICE OF THE YEAR** - Overall rankings

Each artist entry includes:
- `rank`: Current ranking position
- `title`: Artist name
- `artistId`: Unique artist identifier
- `thumbnailUrl`: Artist image
- `optionId`: Voting option ID

### Database Schema

**rankings_snapshots** - Full API snapshots
- `id`: Snapshot ID
- `data`: Complete JSON response
- `updated_at`: When rankings were last updated by MAMA
- `fetched_at`: When we fetched the data
- `created_at`: Database insertion time

**ranking_changes** - Individual ranking movements
- `snapshot_id`: Reference to snapshot
- `category`: Category name (e.g., "FANS' CHOICE MALE")
- `artist_id`: Artist identifier
- `artist_name`: Artist display name
- `old_rank`: Previous ranking
- `new_rank`: Current ranking
- `rank_change`: Change amount (positive = moved up)
- `detected_at`: When change was detected

## Development

### Running Tests

```bash
python -m pytest tests/
```

### Testing the Fetcher

```bash
# Test API fetch
python3 -m src.fetcher
```

## API Source

Data is fetched from:
```
https://api.mnetplus.world/vote/v1/public/guest/votes/690020de20a9a4058b351522/options?sort=RANKED
```

This is the official MAMA voting API endpoint.

## Notes

- Rankings are updated by MAMA periodically (check `updatedAt` field)
- The scheduler will detect and log all ranking changes
- All timestamps are in UTC
- Database grows over time - consider implementing data retention policies for long-term use

## License

MIT
