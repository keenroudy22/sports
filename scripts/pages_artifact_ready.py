"""Bounded read-only check for the exact uploaded Pages artifact before deploy."""
import json
import os
import time
import urllib.error
import urllib.request


def wait(run_id, artifact_id, name, token, *, fetch=None, sleep=time.sleep, attempts=6):
    if (not str(run_id).isdigit() or not str(artifact_id).isdigit()
            or not name.startswith('github-pages-') or not token or not 1 <= attempts <= 6):
        raise ValueError('Exact uploaded artifact identity required')
    url = f'https://api.github.com/repos/keenroudy22/sports/actions/runs/{run_id}/artifacts?per_page=100'
    def request():
        req = urllib.request.Request(url, headers={'Authorization': 'Bearer '+token,
            'Accept': 'application/vnd.github+json', 'User-Agent': 'Kookn-Pages-verifier'})
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.load(response)
    fetch = fetch or request
    for attempt in range(attempts):
        try:
            rows = fetch().get('artifacts', [])
        except urllib.error.HTTPError as error:
            # Do not retry through a provider rate/backoff or permission error.
            raise RuntimeError(f'Pages artifact check failed: HTTP {error.code}') from None
        except (urllib.error.URLError, TimeoutError):
            rows = []
        matches = [row for row in rows if row.get('name') == name and row.get('expired') is False]
        if len(matches) == 1 and str(matches[0].get('id')) == str(artifact_id):
            return {'artifactId': str(artifact_id), 'name': name, 'attempts': attempt+1}
        if attempt+1 < attempts:
            sleep(5)
    raise RuntimeError('Exact Pages artifact is not uniquely visible; deployment held')


if __name__ == '__main__':
    print(json.dumps(wait(os.environ['GITHUB_RUN_ID'], os.environ['PAGES_ARTIFACT_ID'],
                         os.environ['PAGES_ARTIFACT_NAME'], os.environ['GITHUB_TOKEN'])))
