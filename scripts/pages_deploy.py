"""Deploy the verified artifact by ID through the GitHub Pages REST API."""

import json
import os
import re
import signal
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pages_artifact_ready

DEPLOYMENTS = 'https://api.github.com/repos/keenroudy22/sports/pages/deployments'
FAILED_STATES = {
    'deployment_failed', 'deployment_perms_error', 'deployment_content_failed',
    'deployment_cancelled', 'deployment_lost',
}


def request_json(url, token, *, payload=None, method=None):
    headers = {'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json',
               'User-Agent': 'Kookn-Pages-deployer'}
    body = None
    if payload is not None:
        headers['Content-Type'] = 'application/json'
        body = json.dumps(payload).encode()
    with urlopen(Request(url, data=body, headers=headers, method=method), timeout=10) as response:
        return {} if response.status == 204 else json.load(response)


def deploy(artifact_id, build_sha, github_token, oidc_token, *,
           request=request_json, sleep=time.sleep, clock=time.monotonic):
    if not str(artifact_id).isdigit() or not re.fullmatch(r'[a-f0-9]{40}', build_sha) or not oidc_token:
        raise ValueError('Verified artifact ID, build SHA and runner OIDC token required')
    # The artifact is already verified via REST. A second lookup through the
    # Actions Results service can report no artifacts for the same upload.
    created = request(DEPLOYMENTS, github_token, payload={
        'artifact_id': int(artifact_id), 'pages_build_version': build_sha,
        'environment': 'github-pages', 'oidc_token': oidc_token,
    })
    deployment_id = str(created.get('id') or build_sha)
    if not re.fullmatch(r'[a-zA-Z0-9-]+', deployment_id):
        raise RuntimeError('Invalid Pages deployment receipt')
    url = f'{DEPLOYMENTS}/{deployment_id}'
    print(f'Pages accepted deployment {deployment_id} for artifact {artifact_id}', flush=True)
    expires = clock() + 600
    try:
        while clock() < expires:
            sleep(10)
            try:
                status = request(url, github_token).get('status')
            except HTTPError as error:
                if error.code not in (404, 500, 502, 503, 504):
                    raise
                continue
            except (URLError, TimeoutError):
                continue
            if status == 'succeed':
                return created['page_url']
            if status in FAILED_STATES:
                raise RuntimeError(f'Pages deployment {deployment_id} ended with {status}')
    except KeyboardInterrupt:
        request(url + '/cancel', github_token, method='POST')
        raise
    request(url + '/cancel', github_token, method='POST')
    raise RuntimeError(f'Pages deployment {deployment_id} timed out')


def stop_on_signal(_signum, _frame):
    raise KeyboardInterrupt


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, stop_on_signal)
    token = os.environ['GITHUB_TOKEN']
    receipt = pages_artifact_ready.wait(os.environ['GITHUB_RUN_ID'], os.environ['PAGES_ARTIFACT_ID'],
                                        os.environ['PAGES_ARTIFACT_NAME'], token)
    print(json.dumps(receipt), flush=True)
    oidc = request_json(os.environ['ACTIONS_ID_TOKEN_REQUEST_URL'], os.environ['ACTIONS_ID_TOKEN_REQUEST_TOKEN'])
    page_url = deploy(receipt['artifactId'], os.environ['GITHUB_SHA'], token, oidc['value'])
    if not page_url or not isinstance(page_url, str) or '\n' in page_url or '\r' in page_url:
        raise RuntimeError('Invalid Pages deployment URL')
    with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as output:
        output.write(f'page_url={page_url}\n')
