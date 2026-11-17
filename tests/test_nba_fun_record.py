import copy
import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from contextlib import ExitStack
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from tests.test_prop_ticket_release import prepared, case
import buffer_post
import discord_post
import gates
import nba_fun_record as record
import nba_official_availability
import prop_ticket_release
import prop_ticket_review
import receipts
import release_queue
import run
import social_style
import staking
import ticket_card
import x_post


class NbaFunRecordTests(unittest.TestCase):
    def test_recovered_native_ticket_renders_units_and_exact_terms(self):
        spec, ctx, pick, _ = prepared('NBA-alts')
        game = dict(ctx.games['NBA-1'], home={'id': '10'}, away={'id': '11'})
        ctx.player_team = {}
        with patch.object(run.pick_card, 'chrome_path', return_value='/Chrome'), \
                patch.object(run.pick_card, 'fetch_data_uri', return_value=None) as images, \
                patch.object(run.pick_card, 'render') as render, patch('featured.of_day', return_value=None):
            run.render_private_play_card(pick['id'], pick, game, {'NBA-1': game}, ctx, ctx.now, Path('fixture.png'))
        svg = render.call_args.args[0]
        text = ' '.join(''.join(node.itertext()) for node in
                        ET.fromstring(svg).iter('{http://www.w3.org/2000/svg}text'))
        self.assertIn('+425', text)
        self.assertIn('DRAFTKINGS', text)
        self.assertIn('0.25u', text)
        self.assertFalse(social_style.privacy_issues(text))
        for leg in spec['legs']:
            self.assertIn(leg['player'], text)
            self.assertIn(run.pick_card.HEADSHOT.format(sport='nba', athlete=leg['athleteId']),
                          [call.args[0] for call in images.call_args_list])

    def test_worker_checks_official_roster_and_promotes_one_delivered_original(self):
        spec, ctx, pick, packet = prepared('NBA-alts')
        at = ctx.now
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            conf = root / 'private'
            ctx.root = root
            folder = root / 'data/nba-capture'
            (folder / 'rosters').mkdir(parents=True)
            game = dict(ctx.games['NBA-1'], providerId='1', status='scheduled',
                        season=2027, seasonType='regular-season',
                        teams={'home': {'id': '10'}, 'away': {'id': '11'}})
            (folder / 'slate.json').write_text(json.dumps({'games': [game]}))
            ctx.games = prop_ticket_review.nba_fixtures(root)
            players = [{'id': str(i), 'name': leg['player'], 'active': True, 'status': 'active'}
                       for i, leg in enumerate(spec['legs'])]
            for team, members in [('10', players), ('11', [])]:
                (folder / 'rosters' / f'{team}.json').write_text(json.dumps(
                    {'retrievedAt': at.isoformat(), 'team': team, 'season': 2027, 'players': members}))
            path = folder / 'injuries-current.json'
            reported = at.astimezone(nba_official_availability.EASTERN).strftime('%Y-%m-%d_%I_%M%p')
            snapshot = {'official': {'reportedAt': at.isoformat(), 'retrievedAt': at.isoformat(),
                                     'source': f'https://ak-static.cms.nba.com/referee/injury/Injury-Report_{reported}.pdf',
                                     'season': 2027},
                        'gameAvailability': {'1': {'kickoff': game['kickoff'], 'rows': [], 'teamHolds': {}}}}
            path.write_text(json.dumps(snapshot))
            book = {'posts': []}
            def render(_key, _pick, _game, _games, _ctx, _now, target):
                target.write_bytes(b'\x89PNG\r\n\x1a\n' + social_style.MARKER + b'\0' * 100)
            with ExitStack() as stack:
                bind = stack.enter_context
                for setup in (
                    patch.object(run, 'ROOT', root), patch.object(run, 'CONF', conf),
                    patch.object(prop_ticket_release, 'CONF', conf),
                    patch.object(run.features, 'load', return_value=[]), patch.object(run, 'live_games', return_value={}),
                    patch.object(receipts, 'prior_day_results_hold', return_value=None),
                    patch.object(x_post, 'load_log', return_value=book), patch.object(x_post, 'save_log'),
                    patch.object(run, 'render_private_play_card', side_effect=render), patch.object(run, 'run_tests'),
                    patch.object(run, 'commit_log'), patch.object(social_style, 'release_issues', return_value=[]),
                    patch('typefully_backup.config', return_value=None),
                    patch.object(buffer_post, 'x_channel', return_value={'id': 'fixture'}),
                    patch.object(buffer_post, 'yield_optional', return_value=0),
                    patch.object(buffer_post, 'rate_backoff', return_value=None),
                    patch.object(buffer_post.quota, 'buffer_block_reason', return_value=None),
                    patch.object(buffer_post, 'live_card_url', side_effect=[None, 'https://keenroudy.com/fixture.png']),
                    patch.object(discord_post, 'webhook', return_value='fixture'),
                ):
                    bind(setup)
                stores = bind(patch.object(gates, 'Stores'))
                x_send = bind(patch.object(buffer_post, 'create_post', return_value='fixture-buffer'))
                discord_send = bind(patch.object(discord_post, 'send_message', return_value={
                    'id': '123456789012345678', 'image': 'https://cdn.discordapp.com/fixture'}))
                stores.return_value.as_of.return_value = ctx
                admitted, hold = prop_ticket_release.enqueue(spec, ctx, at, conf)
                self.assertIsNone(hold)
                self.assertEqual(admitted['id'], pick['id'])
                self.assertEqual(run.release_private(at, log=lambda *_: None), [])
                discord_send.assert_not_called()
                prop_ticket_release.recheck(pick['id'], spec, ctx, at, conf)
                snapshot['gameAvailability']['1']['rows'] = [{'athleteId': '0', 'status': 'Out'}]
                path.write_text(json.dumps(snapshot))
                self.assertIn('participation is unresolved', prop_ticket_release.refusal(pick, ctx, conf=conf))
                snapshot['gameAvailability']['1']['rows'] = []
                path.write_text(json.dumps(snapshot))
                self.assertEqual(run.release_private(at, log=lambda *_: None), [])
                discord_send.assert_called_once()
                x_send.assert_not_called()
                self.assertEqual(len(record.public_rows(root, book['posts'], at)), 1)
                self.assertEqual(run.release_private(at, log=lambda *_: None), [pick['id']])
                discord_send.assert_called_once()
                x_send.assert_called_once()
                self.assertEqual(book['posts'][0]['bufferPostId'], 'fixture-buffer')
                self.assertFalse(release_queue.load(conf)['plays'])
                self.assertTrue((root / 'data/release-cards' / f"{pick['id']}.png").exists())

    def test_receipt_before_publication_and_append_only_graded_correction(self):
        spec, ctx, pick, packet = prepared('NBA-alts')
        admitted = ctx.now
        sent = admitted + timedelta(minutes=1)
        pick['publishedAt'] = gates.stamp(sent)
        post = {'id': pick['id'], 'kind': 'buffer:play', 'bufferPostId': 'queued-only'}
        _, evidence, final = case('NBA-alts')
        packet['settlementEvidence'] = evidence
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(ValueError, 'delivery receipt'):
                record.publish(root, pick, [post], sent)
            self.assertFalse((root / record.PATH).exists())
            post['discord'] = {'state': 'sent', 'sentAt': gates.stamp(sent),
                               'messageId': '123456789012345678', 'attachmentState': 'attached',
                               'attachmentReceipt': 'https://cdn.discordapp.com/fixture'}
            self.assertTrue(record.publish(root, pick, [post], sent))
            self.assertFalse(record.publish(root, pick, [post], sent))
            self.assertEqual(record.public_rows(root, [], sent), [])
            [public] = record.public_rows(root, [post], sent)
            self.assertEqual(public['delivery']['discordAt'], gates.stamp(sent))
            self.assertEqual(public['kind'], 'parlays')
            self.assertEqual(receipts.unit_fun_rows(sent, log_book={'posts': [post]}, root=root), [public])
            path = root / record.PATH
            original_bytes = path.read_bytes()
            self.assertNotIn(b'fixture.combined', original_bytes)
            self.assertNotIn(b'attachmentReceipt', original_bytes)
            self.assertNotIn(b'ticketQuote', original_bytes)
            self.assertEqual(staking.external(root, sent)[0][pick['id']]['riskUnits'], .25)
            ctx.risk_external = staking.external(root, sent)[0]
            ctx.now = sent
            self.assertFalse(gates.longshot_one_per_day(dict(pick, id='different'), ctx).ok)
            evidence['legs'][0]['injuryReview'] = 'unknown'
            with self.assertRaisesRegex(ValueError, 'injury/early-exit'):
                record.settle(root, pick['id'], [post], packet, final)
            self.assertEqual(path.read_bytes(), original_bytes)
            evidence['legs'][0]['injuryReview'] = 'clear'
            self.assertTrue(record.settle(root, pick['id'], [post], packet, final))
            self.assertFalse(record.settle(root, pick['id'], [post], packet, final+timedelta(minutes=1)))
            self.assertEqual(record.rows(root, final)[pick['id']]['settlementLegActuals'], [3, 3, 3])
            self.assertIn('points', record.rows(root, final)[pick['id']]['actual'])
            correction = copy.deepcopy(packet)
            correction['settlementEvidence']['legs'][0].update(actual=2, result='loss')
            correction['settlementEvidence']['bookSettlement'].update(result='loss', settledOdds=None)
            corrected = final+timedelta(minutes=2)
            self.assertTrue(record.settle(root, pick['id'], [post], correction, corrected))
            self.assertTrue(path.read_bytes().startswith(original_bytes))
            self.assertEqual(len(path.read_text().splitlines()),3)
            original, first, latest = map(json.loads,path.read_text().splitlines())
            self.assertEqual((original['odds'],first['result'],latest['result']), (425,'win','loss'))
            self.assertEqual(record.rows(root, final)[pick['id']]['result'], 'win')
            self.assertEqual(record.rows(root, corrected)[pick['id']]['units'], -.25)
            self.assertEqual(latest['correctedAt'], gates.stamp(corrected))

            with patch('community_record.ROOT', root):
                book = {'posts': [post]}
                [current] = record.public_rows(root, [post], corrected)
                final_id = receipts.nba_fun_final_id(current)
                self.assertEqual(buffer_post.quote_source_id(final_id), pick['id'])
                self.assertEqual(discord_post.queue_nba_fun_results(book, corrected), 1)
                self.assertEqual(discord_post.queue_nba_fun_results(book, corrected), 0)
                [planned] = receipts.result_cards({}, {}, {}, corrected, log_book=book)
                self.assertEqual(planned['card'], post['discord']['result']['cardKey'])
                self.assertIn('TICKET LOST', ticket_card.fun_final_svg(planned['pick']))
                self.assertIn('DAILY FINAL', ticket_card.daily_result_svg([current], 'Nov 16'))
                self.assertIn('no confirmed Discord', receipts.prior_individual_results_hold([current], book, 'all'))
                post['discord']['result'].update(state='sent', sentAt=gates.stamp(corrected), messageId='987654321012345678')
                self.assertIsNone(receipts.prior_individual_results_hold([current], book, 'all'))
                x_at = gates.stamp(sent)
                post.update(sentAt=x_at, tweetId='123456789012345679',
                            link='https://x.com/keenkooks/status/123456789012345679')
                book['posts'].append({'id': f"cashed:{pick['id']}", 'sentAt': gates.stamp(final),
                                      'tweetId': '123456789012345680'})
                self.assertIn('no confirmed X', receipts.prior_individual_results_hold([current], book, 'all'))
                [x_final] = receipts.cashed({}, {}, {}, book, corrected)
                self.assertEqual(x_final['key'], final_id)
                self.assertEqual(buffer_post.prior_discord_result(book, final_id)['finalId'], final_id)
