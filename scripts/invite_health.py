"""Check the public Kook'n invite during the existing daily heartbeat."""
import json
import urllib.request

CODE = 'ZnjubjsBPM'
GUILD = '1554298777169297449'
URL = f'https://discord.com/api/v10/invites/{CODE}'


def check(opener=None):
    opener = opener or urllib.request.urlopen
    request = urllib.request.Request(URL, headers={'User-Agent': 'KooknSportsInviteHealth/1.0'})
    try:
        with opener(request, timeout=8) as response:
            payload = json.load(response)
    except Exception:
        return 'Discord invite could not be verified; check the public invite.'
    if payload.get('code') != CODE or (payload.get('guild') or {}).get('id') != GUILD:
        return 'Discord invite no longer points to the Kook\'n Sports server.'
    if payload.get('expires_at') is not None:
        return 'Discord invite has an expiry date; check the public invite.'
    return None
