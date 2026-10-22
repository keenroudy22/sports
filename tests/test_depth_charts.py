import importlib.util
import unittest
from datetime import datetime, timezone
from pathlib import Path

spec = importlib.util.spec_from_file_location('depth_charts', Path(__file__).resolve().parents[1] / 'scripts/depth_charts.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

NOW = datetime(2026, 10, 1, 16, tzinfo=timezone.utc)


def context(status='Out', position='RB'):
    return {'leagues': {'NFL': {'teams': {'23': {'name': 'Pittsburgh Steelers', 'players': [
        {'id': '2', 'name': 'Rico Dowdle', 'position': position, 'status': status}]}}}}}


def slate():
    return {'games': [{'id': 'NFL-1', 'league': 'NFL', 'state': 'pre', 'kickoff': '2026-10-02T00:15:00Z',
                       'away': {'id': '23'}, 'home': {'id': '5'}}]}


def payload():
    players = lambda *rows: [{'id': pid, 'displayName': name} for pid, name in rows]
    return {'team': {'id': '23', 'abbreviation': 'PIT', 'displayName': 'Pittsburgh Steelers'},
            'depthchart': [{'name': '3WR 1TE', 'positions': {
                'qb': {'position': {'abbreviation': 'QB'}, 'athletes': players(('10', 'Aaron Rodgers'))},
                'rb': {'position': {'abbreviation': 'RB'}, 'athletes': players(
                    ('1', 'Jaylen Warren'), ('2', 'Rico Dowdle'), ('3', 'Travis Homer'))},
                'wr1': {'position': {'abbreviation': 'WR'}, 'athletes': players(('4', 'DK Metcalf'))},
                'te': {'position': {'abbreviation': 'TE'}, 'athletes': players(('5', 'Darnell Washington'))},
            }}]}


def roster():
    return {'athletes': [{'position': 'offense', 'items': [
        {'id': '1', 'displayName': 'Jaylen Warren', 'injuries': []},
        {'id': '2', 'displayName': 'Rico Dowdle', 'injuries': [{'status': 'Out'}]},
        {'id': '3', 'displayName': 'Travis Homer', 'injuries': [{'status': 'Injured Reserve'}]},
    ]}]}


class DepthChartTests(unittest.TestCase):
    def test_upcoming_injuries_include_linemen_defense_and_questionable_roles(self):
        self.assertEqual(set(module.targets(context(), slate(), NOW)), {'23'})
        self.assertEqual(set(module.targets(context('Questionable'), slate(), NOW)), {'23'})
        self.assertEqual(set(module.targets(context(position='G'), slate(), NOW)), {'23'})
        self.assertEqual(set(module.targets(context(position='CB'), slate(), NOW)), {'23'})
        self.assertEqual(module.targets(context('Active'), slate(), NOW), {})

    def test_all_position_roles_do_not_leak_into_skill_next_up(self):
        data = payload()
        data['depthchart'][0]['positions']['lg'] = {'athletes': [{'id': '99', 'displayName': 'Guard'}]}
        data['depthchart'].append({'positions': {'cb': {'athletes': [{'id': '98', 'displayName': 'Corner'}]}}})
        row = module.normalize(data, '2026-10-01T16:00:00Z', 'source')
        self.assertTrue({'lg', 'cb'} <= {p['key'] for p in row['rolePositions']})
        self.assertFalse({'lg', 'cb'} & {p['key'] for p in row['positions']})

    def test_provider_order_is_preserved_for_the_next_player_up(self):
        row = module.normalize(payload(), '2026-10-01T16:00:00Z', 'source', roster())
        rb = next(p for p in row['positions'] if p['key'] == 'rb')
        self.assertEqual([(p['order'], p['name']) for p in rb['players']],
                         [(1, 'Jaylen Warren'), (2, 'Rico Dowdle'), (3, 'Travis Homer')])
        self.assertEqual(rb['group'], 'RB')
        self.assertFalse(rb['players'][0]['availability']['unavailable'])
        self.assertEqual(rb['players'][2]['availability'], {'status': 'Injured Reserve', 'unavailable': True})

    def test_a_failed_read_keeps_the_last_good_depth_chart(self):
        old = module.refresh({}, context(), slate(), lambda _: payload(), NOW)
        new = module.refresh(old, context(), slate(), lambda _: (_ for _ in ()).throw(OSError()), NOW)
        self.assertEqual(new['teams']['23']['positions'], old['teams']['23']['positions'])
        self.assertEqual(new['teams']['23']['status'], 'failed')


if __name__ == '__main__':
    unittest.main()
