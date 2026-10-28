import copy
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from types import SimpleNamespace
import daily_straight_card as daily
import buffer_post
import discord_post
import feed
import gates
import pick_card
import receipts
import social_style
import ticket_card
import x_post

NOW = datetime(2026, 10, 28, 15, tzinfo=timezone.utc)
DAY = '2026-10-28'


def world(count=2):
    games = {'g': {'id': 'g', 'league': 'CFB', 'kickoff': '2026-10-28T23:00:00Z',
                   'home': {'short': 'Miami'}, 'away': {'short': 'Ohio'}}}
    first = {f'CFB-2026-{i}': {'id': f'CFB-2026-{i}', 'title': f'Full Player Name {i} over 49.5 receiving yards',
              'athleteId': str(100 + i), 'market': 'recYds', 'marketType': 'prop', 'direction': 'over',
              'line': 49.5, 'gameIds': ['g'], 'kickoff': games['g']['kickoff'], 'lane': 'best_bet',
              'book': 'FanDuel', 'odds': -110, 'riskUnits': 0.5,
              'publishedAt': '2026-10-28T11:00:00Z'} for i in range(count)}
    log = {'posts': [{'id': k, 'kind': 'buffer:play', 'sentAt': '2026-10-28T12:00:00Z'} for k in first]}
    return first, {}, games, log


class DailyStraightCardTests(unittest.TestCase):
    def test_actual_individual_x_before_combined_and_every_active_row_required(self):
        first, latest, games, log = world()
        self.assertIsNotNone(daily.proposal(first, latest, games, log, NOW))
        log['posts'][0].pop('sentAt')
        log['posts'][0]['discord'] = {'state': 'sent', 'sentAt': '2026-10-28T12:00:00Z'}
        self.assertIsNone(daily.proposal(first, latest, games, log, NOW))
        log['posts'][0]['dueAt'] = '2026-10-28T14:00:00Z'
        self.assertIsNone(daily.proposal(first, latest, games, log, NOW))

    def test_no_legacy_backfill_started_games_or_new_single_summary(self):
        first, latest, games, log = world(1)
        self.assertIsNone(daily.proposal(first, latest, games, log, NOW))
        first, latest, games, log = world()
        self.assertIsNone(daily.proposal(first, latest, games, log, gates.when('2026-10-28T23:01:00Z')))
        self.assertIsNone(daily.proposal(first, latest, games, log, gates.when('2026-10-27T14:00:00Z')))

    def test_snapshot_is_immutable_and_other_categories_never_join(self):
        first, latest, games, log = world()
        for name, extra in [('fun', {'legs': [{'title': 'x'}]}), ('trial', {'lane': 'nba_trial'}),
                            ('personal', {'lane': 'community'}), ('climb', {'ladder': {'step': 1}, 'legs': [{'title': 'x'}]})]:
            first[name] = dict(next(iter(first.values())), id=name, **extra)
        found = daily.proposal(first, latest, games, log, NOW)
        self.assertEqual(len(found['straightCard']['rows']), 2)
        before = copy.deepcopy(found)
        first['CFB-2026-0']['odds'] = 180
        self.assertEqual(found, before)
        log['posts'].append({'id': found['key'], 'straightCard': found['straightCard'], 'cancelledAt': 'later'})
        self.assertIsNone(daily.proposal(first, latest, games, log, NOW))
        self.assertEqual(len(daily.history(first, latest, games, log, NOW)), 1)

    def test_missing_or_invalid_stake_price_holds_instead_of_guessing(self):
        for field, value in [('riskUnits', None), ('riskUnits', float('nan')), ('odds', None), ('odds', True)]:
            first, latest, games, log = world()
            first['CFB-2026-0'][field] = value
            self.assertIsNone(daily.proposal(first, latest, games, log, NOW))

    def test_linked_grading_uses_original_terms_all_outcomes_and_no_stored_unit_override(self):
        first, latest, games, log = world(4)
        found = daily.proposal(first, latest, games, log, NOW)
        log['posts'].append({'id': found['key'], 'straightCard': found['straightCard'],
                             'sentAt': '2026-10-28T15:03:00Z', 'link': 'https://x.com/keenkooks/status/12345'})
        for k, result in zip(first, ('win', 'loss', 'push', 'void')):
            latest[k] = {'result': result, 'odds': 900, 'riskUnits': 10, 'units': 90}
        proof = daily.linked(log, DAY, latest)
        self.assertIn('1W/1L/1P/1V', proof['text'])
        self.assertIn('-0.05u', proof['text'])
        self.assertEqual([r['odds'] for r in proof['rows']], [-110] * 4)
        self.assertEqual([r['riskUnits'] for r in proof['rows']], [0.5] * 4)
        raw = receipts.day_receipt(gates.eastern_date(NOW), receipts.released_first(first, log, games), latest, games, set(first))
        linked = daily.link_final(raw, log, latest, games)
        self.assertIn(proof['link'], linked['text'])
        self.assertIn('1W/1L/1P/1V', linked['text'])
        self.assertLessEqual(x_post.tweet_length(linked['text']), 280)
        self.assertEqual(receipts.guard(linked), [])
        final_svg = ticket_card.final_svg(proof['rows'], DAY)
        self.assertEqual(final_svg.count('-110 FanDuel'), 4)
        self.assertIn('0.5u', final_svg)
        self.assertEqual(social_style.issues(final_svg, graphic=True), [])
        self.assertEqual(social_style.issues(linked['text']), [])
        log['posts'][-1].pop('sentAt')
        self.assertIsNone(daily.linked(log, DAY, latest))

    def test_large_card_keeps_every_exact_wager_and_units_without_dollars(self):
        first, latest, games, log = world(10)
        found = daily.proposal(first, latest, games, log, NOW)
        self.assertLessEqual(x_post.tweet_length(found['text']), 280)
        self.assertEqual(social_style.issues(found['text']), [])
        self.assertEqual(receipts.guard(found), [])
        svg = ticket_card.daily_straight_svg(found['straightCard'], games)
        for i in range(10):
            self.assertIn(f'Full Player Name {i}', svg)
        self.assertEqual(svg.count('-110 FanDuel'), 10)
        self.assertEqual(social_style.issues(svg, graphic=True), [])

    def test_schedule_freezes_only_matching_card_and_mirrors_once_after_x(self):
        first, latest, games, log = world()
        found = daily.proposal(first, latest, games, log, NOW)
        ctx = SimpleNamespace(first=first, latest=latest, games=games)
        plan = [(found['key'], 'receipt', found['text'], found['due'], found['card'])]
        with patch.object(buffer_post.gates, 'Stores') as stores, \
             patch.object(buffer_post, 'live_card_url', return_value='https://example.com/card.png'), \
             patch.object(buffer_post, 'ticket_art_live', return_value=True), \
             patch.object(buffer_post, 'plain_art_live', return_value=True), \
             patch.object(buffer_post, 'create_post', return_value='real-buffer-id') as create:
            stores.return_value.as_of.return_value = ctx
            buffer_post.schedule(plan, 'x', log, NOW, log=lambda *_: None)
            self.assertEqual(create.call_count, 1)
        entry = log['posts'][-1]
        self.assertEqual(entry['straightCard'], found['straightCard'])
        self.assertEqual(entry['queuedText'].count('@Playbook'), 1)
        self.assertNotIn('Copy the bet', entry['discord']['text'])
        with patch.object(discord_post, 'send_message') as send:
            discord_post.mirror_sent(log, NOW, url='plays', log=lambda *_: None)
            send.assert_not_called()
            entry['sentAt'] = gates.stamp(NOW)
            entry['link'] = 'https://x.com/keenkooks/status/12345'
            discord_post.mirror_sent(log, NOW, url='plays', log=lambda *_: None)
            discord_post.mirror_sent(log, NOW, url='plays', log=lambda *_: None)
            self.assertEqual(send.call_count, 1)
            self.assertEqual(send.call_args.args[0], 'plays')
        self.assertEqual(entry['discord']['state'], 'sent')
        self.assertIsNone(daily.proposal(first, latest, games, log, NOW))

    def test_changed_or_unpriced_source_cannot_accept_a_stale_built_card(self):
        first, latest, games, log = world()
        found = daily.proposal(first, latest, games, log, NOW)
        first['CFB-2026-0']['odds'] = 180
        with patch.object(buffer_post.gates, 'Stores') as stores, \
             patch.object(buffer_post, 'create_post') as create:
            stores.return_value.as_of.return_value = SimpleNamespace(first=first, latest=latest, games=games)
            buffer_post.schedule([(found['key'], 'receipt', found['text'], found['due'], found['card'])],
                                 'x', log, NOW, log=lambda *_: None)
            create.assert_not_called()
        self.assertEqual(len(log['posts']), 2)

    def test_feed_renders_combined_card_without_network_or_missing_item_skip(self):
        import tempfile
        first, latest, games, log = world()
        found = daily.proposal(first, latest, games, log, NOW)
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(pick_card, 'chrome_path', return_value='chrome'), \
             patch.object(pick_card, 'render') as render:
            result = feed.render_cards([{'guid': found['card'], 'straightCard': found['straightCard']}],
                                       Path(folder), games=games, render_time=NOW)
            self.assertEqual(render.call_count, 1)
            self.assertIn(found['card'], result)

    def test_linked_final_alone_is_new_approved_discord_receipt_route(self):
        entry = {'id': 'receipt:day:2026-10-28', 'kind': 'buffer:receipt',
                 'sentAt': gates.stamp(NOW), 'straightCardResult': {'version': 1, 'day': DAY,
                 'source': 'https://x.com/keenkooks/status/12345', 'pickIds': ['one', 'two']},
                 'discord': {'state': 'pending', 'destination': 'plays', 'text': 'Card: 0W/2L/0P/0V · -1.00u'}}
        with patch.object(discord_post, 'send_message') as send:
            discord_post.mirror_sent({'posts': [entry]}, NOW, url='plays', log=lambda *_: None)
            self.assertEqual(send.call_count, 1)
        entry.pop('straightCardResult')
        entry['discord']['state'] = 'pending'
        with patch.object(discord_post, 'send_message') as send:
            discord_post.mirror_sent({'posts': [entry]}, NOW, url='plays', log=lambda *_: None)
            send.assert_not_called()


if __name__ == '__main__':
    unittest.main()
