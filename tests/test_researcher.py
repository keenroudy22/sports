import json
import subprocess
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import researcher

GAME = {'id': 'NFL-1', 'league': 'NFL', 'kickoff': '2026-09-27T17:00Z',
        'home': {'name': 'Detroit Lions', 'abbreviation': 'DET'}, 'away': {'name': 'Buffalo Bills', 'abbreviation': 'BUF'}}
ANSWER = {'facts': [
    {'kind': 'injury', 'direction': 'for', 'claim': 'Lions list two starting corners out.', 'entities': ['Terrion Arnold', 'D.J. Reed'],
     'source': 'https://www.detroitlions.com/team/injury-report', 'publishedAt': '2026-09-25'},
    {'kind': 'weather', 'direction': 'against', 'claim': 'Wind forecast 18 mph at kickoff.', 'entities': [],
     'source': 'https://forecast.weather.gov/x'},
    {'kind': 'opinion', 'direction': 'for', 'claim': 'Take the over.', 'entities': [], 'source': 'https://x'},
    {'kind': 'injury', 'direction': 'for', 'claim': 'no source', 'entities': ['Nobody'], 'source': 'http://insecure'},
    {'kind': 'role', 'direction': 'for', 'claim': 'Someone starts.', 'entities': ['Ghost Player'], 'source': 'https://www.example.com/a'}]}
PAGES = {'https://www.detroitlions.com/team/injury-report': b'<html><body>Injury report: Terrion Arnold (out), D.J. Reed (out)</body></html>',
         'https://forecast.weather.gov/x': b'<html>Wind 18 mph</html>',
         'https://www.example.com/a': b'<html>nothing about anyone</html>'}


def fake_runner(command, **kwargs):
    assert command[:2] == ['claude', '-p'] and '--allowedTools' in command
    return subprocess.CompletedProcess(command, 0, stdout=json.dumps({'result': 'Here you go:\n' + json.dumps(ANSWER)}), stderr='')


def fake_opener(url):
    if url not in PAGES:
        raise OSError('404')
    return PAGES[url]


class ResearcherTests(unittest.TestCase):
    def test_off_unless_the_switch_is_set(self):
        self.assertFalse(researcher.enabled({}))
        self.assertTrue(researcher.enabled({'KEENROUDY_RESEARCHER': 'claude'}))

    def test_the_prompt_names_the_game_and_the_market(self):
        text = researcher.prompt_for(GAME, 'total', 'over')
        self.assertIn('Buffalo Bills at Detroit Lions', text)
        self.assertIn('Market being considered: total', text)
        self.assertIn('Return ONLY this JSON', text)

    def test_extract_tolerates_prose_and_caps_the_list(self):
        self.assertEqual(len(researcher.extract('Sure!\n' + json.dumps(ANSWER) + '\nDone.')), 5)
        self.assertEqual(researcher.extract('no json here'), [])
        self.assertEqual(researcher.extract(json.dumps({'facts': [{}] * 20})), [{}] * researcher.MAX_FACTS)

    def test_research_keeps_only_verified_well_formed_facts(self):
        kept, dropped = researcher.research(GAME, 'total', 'over', runner=fake_runner, opener=fake_opener, now=datetime(2026, 9, 26, tzinfo=timezone.utc))
        self.assertEqual([f['kind'] for f in kept], ['injury', 'weather'])
        self.assertTrue(all(f['verified'] for f in kept))
        self.assertEqual(kept[0]['entities'], ['Terrion Arnold', 'D.J. Reed'])
        self.assertEqual(kept[0]['retrievedAt'], '2026-09-26T00:00:00Z')
        self.assertEqual(kept[0]['id'], 'web-NFL-1-0')
        notes = {f['claim']: f.get('verifyNote') for f in dropped}
        self.assertIn('not on the page: Ghost Player', notes['Someone starts.'])
        self.assertNotIn('Take the over.', notes, 'a malformed kind is dropped before any fetch')

    def test_a_failed_command_is_silence_not_an_error(self):
        def broken(command, **kwargs):
            return subprocess.CompletedProcess(command, 1, stdout='', stderr='boom')
        self.assertEqual(researcher.research(GAME, 'total', 'over', runner=broken, opener=fake_opener), ([], []))

        def missing(command, **kwargs):
            raise OSError('no claude')
        self.assertEqual(researcher.research(GAME, 'total', 'over', runner=missing, opener=fake_opener), ([], []))




class ReliabilityTests(unittest.TestCase):
    def test_a_researcher_that_runs_out_of_turns_is_asked_to_answer_with_what_it_found(self):
        import json as _json
        from types import SimpleNamespace
        calls = []

        def runner(command, **kw):
            calls.append(command)
            if '--resume' in command:
                return SimpleNamespace(returncode=0, stdout=_json.dumps({'result': '{"facts": [{"kind": "injury"}]}'}), stderr='')
            return SimpleNamespace(returncode=1, stdout=_json.dumps({'subtype': 'error_max_turns', 'session_id': 's-1', 'result': None}), stderr='')
        self.assertEqual(researcher.run_claude('p', runner=runner), '{"facts": [{"kind": "injury"}]}')
        self.assertIn('--resume', calls[1])
        self.assertIn('s-1', calls[1])
        self.assertIn('--max-turns', calls[0])
        self.assertEqual(calls[0][calls[0].index('--max-turns') + 1], str(researcher.MAX_TURNS))
        broken = lambda command, **kw: SimpleNamespace(returncode=1, stdout='', stderr='boom')
        self.assertIsNone(researcher.run_claude('p', runner=broken))

    def test_an_injury_claim_needs_its_status_next_to_the_name(self):
        fact = {'kind': 'injury', 'claim': 'Navy quarterback Blake Horvath is out with a knee injury.', 'entities': ['Blake Horvath']}
        near = 'navy notes. quarterback blake horvath is out for saturday after the knee injury he suffered.'
        far = 'blake horvath threw for 200 yards. ' + 'x ' * 400 + 'the backup tackle is out for the season.'
        self.assertTrue(researcher.status_near_name(fact, near))
        self.assertFalse(researcher.status_near_name(fact, far), 'the name and an unrelated "out" far apart')
        self.assertTrue(researcher.status_near_name(dict(fact, claim='Blake Horvath leads the team in rushing.'), far),
                        'a claim with no status word falls back to the name check')


if __name__ == '__main__':
    unittest.main()
