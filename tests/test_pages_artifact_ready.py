import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import pages_artifact_ready as ready


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
