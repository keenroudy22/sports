import copy
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import daily_chef_review as review

NOW = datetime(2026, 11, 17, 19, tzinfo=timezone.utc)


def play(league, **extra):
    return dict(id=league+'-one', league=league, eventId=league+'-g',
                gameIds=[league+'-g'], kickoff='2026-11-18T00:00:00Z',
                marketType='spread', direction='home', line=-3.5, odds=-110,
                oppositeOdds=-110, book='DraftKings', riskUnits=1,
                quotedAt='2026-11-17T18:55:00Z', status='active', **extra)


def world():
    football = play('CFB')
    games = {league+'-g': {'id': league+'-g', 'league': league,
             'kickoff': '2026-11-18T00:00:00Z'} for league in review.SPORTS}
    return SimpleNamespace(first={football['id']: football}, latest={},
        games={'CFB-g': games['CFB-g']}, risk_games=games, root=Path('/unused'))


def snapshot(**kw):
    return review.snapshot(world(), NOW, posts=[],
        nba=[play('NBA', selectionMethod='sourced-nba-primary-prop-v1')],
        cbb=[play('CBB', selectionMethod='sourced-cbb-straight-v1')],
        check=lambda *args: None, **kw)


def packet(report):
    ranking = [r['terms']['id'] for r in report['rows'] if r['state']=='reviewable']
    return {'version': review.VERSION, 'reviewer': 'kookn-desk', 'approved': True,
        'reviewedAt': NOW.isoformat(), 'day': report['day'], 'fingerprint': report['fingerprint'],
        'coverage': {sport: 'Current supported slate reviewed; missing markets remain held.' for sport in review.SPORTS},
        'ranking': ranking, 'selectedId': ranking[0] if ranking else None,
        'why': 'Compared the current price, role and matchup evidence across the eligible slate.',
        'countercase': 'The strongest opponent evidence limits confidence at the original price.'}


class CrossSportReviewTests(unittest.TestCase):
    def test_separate_ledgers_share_review_without_probability_or_stake_changes(self):
        report = snapshot()
        self.assertEqual({r['terms']['league'] for r in report['rows']}, {'CFB','NBA','CBB'})
        self.assertEqual({r['terms']['riskUnits'] for r in report['rows']}, {1})
        self.assertEqual([r['evidenceKind'] for r in report['rows'] if r['terms']['league']=='NBA'], ['sourced judgment'])
        self.assertNotIn('chance', json.dumps(report))
        self.assertFalse(report['publicationAuthority'])
        self.assertEqual(report['coverage']['NFL']['games'], 1)
        self.assertIn('research still required', report['coverage']['NFL']['coverage'])

    def test_public_and_uncertain_delivery_are_not_relabel_candidates(self):
        ctx = world()
        posts = [{'id':'CFB-one','discord':{'state':'sent','sentAt':NOW.isoformat(),'messageId':'1572308502645309502'}},
                 {'id':'NBA-one','error':'uncertain transport'}]
        report = review.snapshot(ctx,NOW,posts=posts,nba=[play('NBA')],cbb=[],check=lambda *a: None)
        self.assertEqual({r['terms']['id']:r['state'] for r in report['rows']}, {'CFB-one':'public','NBA-one':'held'})
        self.assertIn('reconcile', next(r for r in report['rows'] if r['terms']['league']=='NBA')['hold'])

    def test_private_discord_receipt_freezes_even_before_post_log_recovery(self):
        pending=[{'id':'CFB-one','pick':play('CFB'),'league':'CFB','discordSentAt':NOW.isoformat()}]
        report=review.snapshot(world(),NOW,posts=[],pending=pending,nba=[],cbb=[],check=lambda *a: self.fail('No recheck of public original'))
        self.assertEqual(report['rows'][0]['state'],'public')

    def test_exact_adapter_hold_remains_visible_and_sources_do_not_become_odds(self):
        def check(p,*_): return 'Official report is older than 60 minutes' if p['league']=='NBA' else None
        report=review.snapshot(world(),NOW,posts=[],nba=[play('NBA')],cbb=[],check=check)
        row=next(r for r in report['rows'] if r['terms']['league']=='NBA')
        self.assertEqual(row['state'],'held')
        self.assertEqual(row['hold'],'Official report is older than 60 minutes')

    def test_excludes_fun_tickets_other_days_and_does_not_mutate_stores(self):
        ctx=world();ctx.first['parlay']={**play('CFB'),'id':'parlay','legs':[{},{}]}
        ctx.first['tomorrow']={**play('CFB'),'id':'tomorrow','kickoff':'2026-11-19T00:00:00Z'}
        before=copy.deepcopy(ctx.first)
        report=review.snapshot(ctx,NOW,posts=[],nba=[],cbb=[],check=lambda *a:None)
        self.assertEqual([r['terms']['id'] for r in report['rows']],['CFB-one'])
        self.assertEqual(ctx.first,before)

    def test_started_or_withdrawn_admissions_never_reach_current_checks(self):
        for extra in ({'kickoff':NOW.isoformat()},{'status':'expired'},{'result':'loss'}):
            ctx=world();ctx.first['CFB-one'].update(extra)
            report=review.snapshot(ctx,NOW,posts=[],nba=[],cbb=[],check=lambda *a:self.fail('Closed original was rechecked'))
            self.assertEqual(report['rows'][0]['state'],'held')

    def test_new_private_admission_is_seen_before_football_public_report(self):
        ctx=world();ctx.first={}
        report=review.snapshot(ctx,NOW,posts=[],pending=[{'id':'CFB-one','league':'CFB','pick':play('CFB')}],nba=[],cbb=[],check=lambda *a:None)
        self.assertEqual(report['rows'][0]['state'],'reviewable')

    def test_duplicate_store_identity_is_visible_failure(self):
        with self.assertRaisesRegex(ValueError,'Duplicate'):
            review.snapshot(world(),NOW,posts=[],nba=[play('CFB')],cbb=[],check=lambda *a:None)

    def test_each_sport_uses_its_existing_current_check_without_capture(self):
        with (mock.patch('cbb_picks.refusal',return_value='CBB quote expired') as cbb,
              mock.patch('nba_trial_runtime.current_match',return_value=False) as nba,
              mock.patch('run.private_release_refusal',return_value='Football line moved') as football):
            self.assertEqual(review.current_refusal(play('CBB'),world(),NOW),'CBB quote expired')
            self.assertIn('NBA current',review.current_refusal(play('NBA'),world(),NOW))
            self.assertEqual(review.current_refusal(play('CFB'),world(),NOW),'Football line moved')
            self.assertEqual((cbb.call_count,nba.call_count,football.call_count),(1,1,1))

    def test_report_is_private_and_atomic(self):
        with tempfile.TemporaryDirectory() as temp:
            path=review.save_snapshot(snapshot(),temp)
            self.assertEqual(path.stat().st_mode & 0o777,0o600)
            self.assertEqual(json.loads(path.read_text())['version'],review.VERSION)
            self.assertFalse(path.with_suffix('.tmp').exists())


class ComparativeDecisionTests(unittest.TestCase):
    def test_stored_review_survives_report_refresh_but_not_changed_terms(self):
        report=snapshot();p=packet(report)
        with tempfile.TemporaryDirectory() as temp:
            review.save_private(p,Path(temp)/'pending/daily-chef-comparison.json')
            review.save_snapshot(report,temp)
            self.assertEqual(review.comparison(report,NOW,temp)['state'],'reviewed')
            self.assertEqual(review.comparison(report,NOW+timedelta(minutes=31),temp)['state'],'held')
            changed={**report,'fingerprint':'changed'}
            self.assertEqual(review.comparison(changed,NOW,temp)['state'],'held')

    def test_explicit_all_sport_ranking_is_not_publication_authority(self):
        report=snapshot();decision=review.validate_review(packet(report),report,NOW)
        self.assertEqual(decision['state'],'reviewed')
        self.assertIn('no publication',decision['designation'])

    def test_no_automatic_winner_and_every_alternative_must_be_compared(self):
        report=snapshot();p=packet(report)
        for field,value in [('ranking',[]),('selectedId','NBA-missing'),('coverage',{'NBA':'Only NBA reviewed'})]:
            bad={**p,field:value}
            with self.subTest(field=field),self.assertRaises(ValueError):review.validate_review(bad,report,NOW)

    def test_changed_exact_terms_source_facts_or_coverage_invalidate_review(self):
        original=snapshot();p=packet(original)
        for change in ('odds','book','game','source','reschedule'):
            ctx=world()
            if change=='game':ctx.risk_games['new']={'id':'new','league':'NBA','kickoff':'2026-11-18T01:00:00Z'}
            elif change=='reschedule':ctx.risk_games['NBA-g']['kickoff']='2026-11-18T02:00:00Z'
            elif change=='source':ctx.first['CFB-one']['sources']=['https://www.espn.com/new-evidence']
            else:ctx.first['CFB-one'][change]=-115 if change=='odds' else 'FanDuel'
            current=review.snapshot(ctx,NOW,posts=[],nba=[play('NBA',selectionMethod='sourced-nba-primary-prop-v1')],cbb=[play('CBB',selectionMethod='sourced-cbb-straight-v1')],check=lambda *a:None)
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,'changed'):
                review.validate_review(p,current,NOW)

    def test_future_and_stale_review_clocks_are_rejected(self):
        report=snapshot()
        for offset in (timedelta(seconds=1),-timedelta(minutes=31)):
            p=packet(report);p['reviewedAt']=(NOW+offset).isoformat()
            with self.assertRaisesRegex(ValueError,'Current'):review.validate_review(p,report,NOW)

    def test_hold_is_valid_and_probability_invention_is_not(self):
        report=snapshot();p=packet(report);p.update(selectedId=None,hold='No reviewed alternative is strong enough at the current exact price.')
        self.assertEqual(review.validate_review(p,report,NOW)['state'],'held')
        p['chance']=.65
        with self.assertRaisesRegex(ValueError,'probability'):review.validate_review(p,report,NOW)


class ScheduledReviewTests(unittest.TestCase):
    def test_run_exposes_shared_coverage_without_changing_legacy_selection(self):
        import run
        report=snapshot();status={}
        with tempfile.TemporaryDirectory() as temp, mock.patch.object(run,'CONF',Path(temp)), \
                mock.patch('featured.choose',return_value=None) as legacy, \
                mock.patch.object(review,'snapshot',return_value=report):
            run.pick_of_the_day(NOW,world(),status,write=True)
            self.assertIsNone(status['pickOfTheDay'])
            self.assertEqual(status['dailyChefReview']['state'],'comparison-required')
            self.assertEqual(set(status['dailyChefReview']['coverage']),set(review.SPORTS))
            self.assertTrue((Path(temp)/'pending/daily-chef-review.json').exists())
            self.assertFalse(status['dailyChefReview']['publicationAuthority'])
            legacy.assert_called_once()

    def test_read_only_run_does_not_write_private_review_and_failures_are_visible(self):
        import run
        with tempfile.TemporaryDirectory() as temp, mock.patch.object(run,'CONF',Path(temp)), \
                mock.patch('featured.choose',return_value=None), mock.patch.object(review,'snapshot',return_value=snapshot()):
            status={};run.pick_of_the_day(NOW,world(),status,write=False)
            self.assertFalse((Path(temp)/'pending').exists())
        with mock.patch('featured.choose',return_value=None), mock.patch.object(review,'snapshot',side_effect=ValueError('Broken sport ledger')):
            status={};run.pick_of_the_day(NOW,world(),status,write=False)
            self.assertEqual(status['dailyChefReview']['state'],'unavailable')
            self.assertIn('Broken sport ledger',status['dailyChefReview']['reason'])


if __name__=='__main__':unittest.main()
