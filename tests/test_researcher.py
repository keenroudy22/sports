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
    assert command[:2] == ['codex', 'exec'] and '--output-last-message' in command
    Path(command[command.index('--output-last-message') + 1]).write_text('Here you go:\n' + json.dumps(ANSWER))
    return subprocess.CompletedProcess(command, 0, stdout='', stderr='')


def fake_opener(url):
    if url not in PAGES:
        raise OSError('404')
    return PAGES[url]


class ResearcherTests(unittest.TestCase):
    def test_off_unless_the_switch_is_set(self):
        self.assertFalse(researcher.enabled({}))
        self.assertFalse(researcher.enabled({'KEENROUDY_RESEARCHER': 'claude'}), 'the retired engine stays off')
        self.assertTrue(researcher.enabled({'KEENROUDY_RESEARCHER': 'Codex'}))
        self.assertFalse(researcher.enabled({'KEENROUDY_RESEARCHER': 'gemini'}), 'only the engines the desk knows')

    def test_codex_reads_the_web_read_only_in_its_own_folder_and_answers_to_a_schema(self):
        import tempfile
        seen = {}

        def codex(command, **kwargs):
            seen['command'], seen['cwd'] = command, kwargs.get('cwd')
            out = Path(command[command.index('--output-last-message') + 1])
            out.write_text(json.dumps(ANSWER))
            return subprocess.CompletedProcess(command, 0, stdout='', stderr='')
        with tempfile.TemporaryDirectory() as folder:
            text = researcher.run_codex('the prompt', runner=codex, folder=folder)
            schema = json.loads((Path(folder) / 'facts.schema.json').read_text())
        command = seen['command']
        self.assertEqual(command[:2], ['codex', 'exec'])
        self.assertEqual(command[command.index('--model') + 1], researcher.DEFAULT_CODEX_MODEL)
        self.assertIn(f'model_reasoning_effort="{researcher.DEFAULT_CODEX_REASONING}"', command)
        for flag, value in (('--sandbox', 'read-only'), ('--cd', seen['cwd'])):
            self.assertEqual(command[command.index(flag) + 1], value)
        self.assertIn('web_search="live"', command)
        self.assertIn('approval_policy="never"', command)
        self.assertTrue(command[-1].startswith(researcher.SYSTEM) and command[-1].endswith('the prompt'))
        self.assertEqual(json.loads(text), ANSWER)
        self.assertEqual(schema['properties']['facts']['items']['properties']['kind']['enum'], list(researcher.KINDS))

    def test_the_engine_names_the_facts_it_found(self):
        def codex(command, **kwargs):
            Path(command[command.index('--output-last-message') + 1]).write_text(json.dumps(ANSWER))
            return subprocess.CompletedProcess(command, 0, stdout='', stderr='')
        import tempfile
        from unittest import mock
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(researcher, 'SANDBOX', Path(folder)):
            kept, _ = researcher.research(GAME, 'total', 'over', runner=codex, opener=fake_opener,
                                          now=datetime(2026, 9, 26, tzinfo=timezone.utc), env={'KEENROUDY_RESEARCHER': 'codex'})
        self.assertEqual({f['origin'] for f in kept}, {'codex researcher'})
        self.assertTrue(all(researcher.from_web(f) for f in kept))
        self.assertTrue(researcher.from_web({'origin': 'claude researcher'}), 'facts stored before the move still count')

    def test_the_prompt_names_the_game_and_the_market(self):
        text = researcher.prompt_for(GAME, 'total', 'over')
        self.assertIn('Buffalo Bills at Detroit Lions', text)
        self.assertIn('Market being considered: total', text)
        self.assertIn('Return ONLY this JSON', text)

    def test_the_settlement_prompt_checks_in_game_injury_and_return_without_ruling_for_a_book(self):
        text = researcher.settlement_prompt_for(GAME, 'DeVon Achane')
        self.assertIn('completed player-prop result', text)
        self.assertIn('DeVon Achane', text)
        self.assertIn('whether the player returned', text)
        self.assertIn('Never decide how a sportsbook grades it', text)

    def test_extract_tolerates_prose_and_caps_the_list(self):
        self.assertEqual(len(researcher.extract('Sure!\n' + json.dumps(ANSWER) + '\nDone.')), 5)
        self.assertEqual(researcher.extract('no json here'), [])
        self.assertEqual(researcher.extract(json.dumps({'facts': [{}] * 20})), [{}] * researcher.MAX_FACTS)

    def test_research_keeps_only_verified_well_formed_facts(self):
        import tempfile
        from unittest import mock
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(researcher, 'SANDBOX', Path(folder)):
            kept, dropped = researcher.research(
                GAME, 'total', 'over', runner=fake_runner, opener=fake_opener,
                now=datetime(2026, 9, 26, tzinfo=timezone.utc), env={'KEENROUDY_RESEARCHER': 'codex'})
        self.assertEqual([f['kind'] for f in kept], ['injury', 'weather'])
        self.assertTrue(all(f['verified'] for f in kept))
        self.assertEqual(kept[0]['entities'], ['Terrion Arnold', 'D.J. Reed'])
        self.assertEqual(kept[0]['retrievedAt'], '2026-09-26T00:00:00Z')
        self.assertEqual(kept[0]['id'], 'web-NFL-1-0')
        notes = {f['claim']: f.get('verifyNote') for f in dropped}
        self.assertIn('not on the page: Ghost Player', notes['Someone starts.'])
        self.assertNotIn('Take the over.', notes, 'a malformed kind is dropped before any fetch')

    def test_a_failed_command_is_silence_not_an_error(self):
        import tempfile
        from unittest import mock
        def broken(command, **kwargs):
            return subprocess.CompletedProcess(command, 1, stdout='', stderr='boom')
        def missing(command, **kwargs):
            raise OSError('no codex')
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(researcher, 'SANDBOX', Path(folder)):
            env = {'KEENROUDY_RESEARCHER': 'codex'}
            self.assertEqual(researcher.research(GAME, 'total', 'over', runner=broken, opener=fake_opener, env=env), ([], []))
            self.assertEqual(researcher.research(GAME, 'total', 'over', runner=missing, opener=fake_opener, env=env), ([], []))

    def test_settlement_injury_distinguishes_a_clean_check_from_a_failed_one(self):
        import tempfile
        from unittest import mock
        answer = {'facts': [{
            'kind': 'injury', 'direction': 'neutral',
            'claim': 'DeVon Achane left in the first quarter with a shoulder injury and did not return.',
            'entities': ['DeVon Achane'], 'source': 'https://www.example.com/achane',
            'publishedAt': '2026-09-27'}]}

        def codex(command, **kwargs):
            Path(command[command.index('--output-last-message') + 1]).write_text(json.dumps(answer))
            return subprocess.CompletedProcess(command, 0, stdout='', stderr='')

        def page(url):
            self.assertEqual(url, 'https://www.example.com/achane')
            return b'DeVon Achane left in the first quarter with a shoulder injury and did not return.'

        def missing(command, **kwargs):
            raise OSError('no codex')

        with tempfile.TemporaryDirectory() as folder, mock.patch.object(researcher, 'SANDBOX', Path(folder)):
            result = researcher.settlement_injury(
                GAME, 'DeVon Achane', runner=codex, opener=page,
                now=datetime(2026, 9, 28, tzinfo=timezone.utc), env={'KEENROUDY_RESEARCHER': 'codex'})
            failed = researcher.settlement_injury(
                GAME, 'DeVon Achane', runner=missing, opener=page,
                now=datetime(2026, 9, 28, tzinfo=timezone.utc), env={'KEENROUDY_RESEARCHER': 'codex'})
        self.assertTrue(result['checked'])
        self.assertEqual(len(result['facts']), 1)
        self.assertFalse(failed['checked'])

    def test_malformed_settlement_answer_is_not_mistaken_for_a_clean_check(self):
        import tempfile
        from unittest import mock

        def codex(command, **kwargs):
            Path(command[command.index('--output-last-message') + 1]).write_text('not json')
            return subprocess.CompletedProcess(command, 0, stdout='', stderr='')

        with tempfile.TemporaryDirectory() as folder, mock.patch.object(researcher, 'SANDBOX', Path(folder)):
            result = researcher.settlement_injury(
                GAME, 'DeVon Achane', runner=codex,
                now=datetime(2026, 9, 28, tzinfo=timezone.utc), env={'KEENROUDY_RESEARCHER': 'codex'})
        self.assertFalse(result['checked'])

    def test_an_unknown_or_retired_engine_never_runs_a_fallback(self):
        from unittest import mock
        with mock.patch.object(researcher, 'run_codex') as codex:
            self.assertIsNone(researcher.ask('prompt', env={'KEENROUDY_RESEARCHER': 'claude'}))
            self.assertIsNone(researcher.ask('prompt', env={'KEENROUDY_RESEARCHER': 'unknown'}))
        codex.assert_not_called()




class ReliabilityTests(unittest.TestCase):
    def test_an_injury_claim_needs_its_status_next_to_the_name(self):
        fact = {'kind': 'injury', 'claim': 'Navy quarterback Blake Horvath is out with a knee injury.', 'entities': ['Blake Horvath']}
        near = 'navy notes. quarterback blake horvath is out for saturday after the knee injury he suffered.'
        far = 'blake horvath threw for 200 yards. ' + 'x ' * 400 + 'the backup tackle is out for the season.'
        self.assertTrue(researcher.status_near_name(fact, near))
        self.assertFalse(researcher.status_near_name(fact, far), 'the name and an unrelated "out" far apart')
        self.assertTrue(researcher.status_near_name(dict(fact, claim='Blake Horvath leads the team in rushing.'), far),
                        'a claim with no status word falls back to the name check')


class QuarterbackTests(unittest.TestCase):
    def test_the_prompt_names_every_quarterback_who_started_this_season(self):
        game = {'away': {'name': 'Navy Midshipmen'}, 'home': {'name': 'UAB Blazers'}, 'league': 'CFB', 'kickoff': 'k'}
        text = researcher.prompt_for(game, 'total', 'over', policy={}, quarterbacks={'Navy': ['Jackson Gutierrez', 'Braxton Woodson'], 'UAB': ['Ryder Burton']})
        self.assertIn('Navy: Jackson Gutierrez, Braxton Woodson; UAB: Ryder Burton', text)
        self.assertNotIn('Quarterbacks who have started', researcher.prompt_for(game, 'total', 'over', policy={}))


if __name__ == '__main__':
    unittest.main()
