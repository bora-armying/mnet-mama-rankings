"""Fetcher for MNET MAMA rankings API.

This module fetches real-time rankings from the MAMA voting API.
"""
import json
import os
from typing import Dict, Optional
from datetime import datetime
import urllib.request
import urllib.error
import ssl
import certifi

MAMA_API_URL = "https://api.mnetplus.world/vote/v1/public/guest/votes/6acecda6f3778e1b06f5170b/options?sort=RANKED"


def fetch_current_rankings() -> Optional[Dict]:
    """Fetch current rankings from the MAMA API.

    Returns:
        Dict containing the full API response with groups, options, and rankings.
        None if the request fails.
    """
    try:
        # Create SSL context with certifi certificates
        context = ssl.create_default_context(cafile=certifi.where())

        with urllib.request.urlopen(MAMA_API_URL, timeout=10, context=context) as response:
            data = json.loads(response.read().decode('utf-8'))
            # Add fetch timestamp
            data['fetchedAt'] = datetime.utcnow().isoformat() + 'Z'
            return data
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as e:
        print(f"Error fetching rankings: {e}")
        return None


def extract_rankings_summary(data: Dict) -> Dict:
    """Extract a simplified summary of rankings from the API response.

    Args:
        data: Full API response

    Returns:
        Dict with simplified rankings organized by category
    """
    if not data or 'groups' not in data:
        return {}

    summary = {
        'updatedAt': data.get('updatedAt'),
        'fetchedAt': data.get('fetchedAt'),
        'categories': {}
    }

    for group in data['groups']:
        group_name = group['groupName']
        summary['categories'][group_name] = {
            'groupId': group['groupId'],
            'artists': [
                {
                    'rank': option['rank'],
                    'title': option['title'],
                    'artistId': option['artistId'],
                    'optionId': option['optionId']
                }
                for option in sorted(group['options'], key=lambda x: x['rank'])
            ]
        }

    return summary


if __name__ == "__main__":
    print("Fetching MAMA rankings...")
    rankings = fetch_current_rankings()
    if rankings:
        print(json.dumps(extract_rankings_summary(rankings), indent=2))
    else:
        print("Failed to fetch rankings")
