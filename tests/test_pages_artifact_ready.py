import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import pages_artifact_ready as ready
import pages_deploy


class PagesArtifactTests(unittest.TestCase):
    def test_uploaded_artifact_can_become_visible_after_the_first_list(self):
        row = {'id': 22, 'name': 'github-pages-11-2', 'expired': False}
        fetch = Mock(side_effect=[{'artifacts': []}, {'artifacts': [row]}]); sleep = Mock()
        self.assertEqual(ready.wait('11','22',row['name'],'synthetic',fetch=fetch,sleep=sleep)['attempts'],2)
        sleep.assert_called_once_with(5)

    def test_wrong_expired_or_duplicate_artifact_never_deploys(self):
        row = {'id': 22, 'name': 'github-pages-11-2', 'expired': False}
        for rows in ([], [dict(row,id=21)], [dict(row,expired=True)], [row,row]):
            fetch = Mock(return_value={'artifacts':rows}); sleep = Mock()
            with self.assertRaisesRegex(RuntimeError,'not uniquely visible'):
                ready.wait('11','22',row['name'],'synthetic',fetch=fetch,sleep=sleep,attempts=2)
            self.assertEqual(fetch.call_count,2)

    def test_previous_attempt_does_not_conflict_with_new_attempt(self):
        rows=[{'id':21,'name':'github-pages-11-1','expired':False},
              {'id':22,'name':'github-pages-11-2','expired':False}]
        self.assertEqual(ready.wait('11','22','github-pages-11-2','synthetic',
            fetch=lambda:{'artifacts':rows},sleep=lambda _:None)['artifactId'],'22')

    def test_verified_id_creates_one_deployment_and_waits_for_success(self):
        request = Mock(side_effect=[
            {'id': 'example', 'page_url': 'https://example.com/'},
            {'status': 'syncing_files'}, {'status': 'succeed'},
        ])
        self.assertEqual(pages_deploy.deploy('22', 'a'*40, 'token', 'oidc',
            request=request, sleep=lambda _: None), 'https://example.com/')
        self.assertEqual(request.call_args_list[0].kwargs['payload']['artifact_id'], 22)
        self.assertEqual(request.call_args_list[0].kwargs['payload']['oidc_token'], 'oidc')
        self.assertEqual(request.call_count, 3)
        self.assertEqual(request.call_args.args[0], pages_deploy.DEPLOYMENTS + '/example')

    def test_timeout_cancels_only_the_created_deployment(self):
        request = Mock(side_effect=[{'id': 'example'}, {}])
        clock = Mock(side_effect=[0, 600])
        with self.assertRaisesRegex(RuntimeError, 'timed out'):
            pages_deploy.deploy('22', 'a'*40, 'token', 'oidc', request=request, clock=clock)
        request.assert_called_with(pages_deploy.DEPLOYMENTS + '/example/cancel', 'token', method='POST')
