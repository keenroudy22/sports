import sys,json,unittest
from pathlib import Path
from datetime import datetime,timezone,timedelta
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import social_learning as s
import buffer_post as b
import gates

NOW=datetime(2026,10,22,20,tzinfo=timezone.utc)


class SocialLearningTests(unittest.TestCase):
    def test_checkpoints_and_no_old_fake_backfill(self):
        e=dict(bufferPostId='p',sentAt=gates.stamp(NOW-timedelta(hours=73)),metricsAt=gates.stamp(NOW-timedelta(hours=49)))
        self.assertEqual(s.checkpoint(e,NOW),72)
        self.assertIsNone(s.checkpoint(dict(e,metricsAt=gates.stamp(NOW)),NOW))
        self.assertIsNone(s.checkpoint(e,NOW+timedelta(days=20)))

    def test_snapshots_preserve_first_read_and_repeat_at_seven_days(self):
        e=dict(id='a',bufferPostId='a',sentAt=gates.stamp(NOW-timedelta(hours=73)),
               metricsAt=gates.stamp(NOW-timedelta(hours=49)),metrics={'impressions':100})
        def send(*args):
            return 200,json.dumps({'data':{'post':{'metrics':[{'type':'impressions','value':300}]}}}).encode()
        book={'posts':[e]}
        self.assertEqual(b.collect_metrics(book,NOW,key='t',send=send),1)
        self.assertEqual(e['metricsHistory'][0]['metrics']['impressions'],100)
        self.assertEqual(e['metricsHistory'][1]['checkpointHours'],72)
        self.assertEqual(b.collect_metrics(book,NOW,key='t',send=send),0)
        self.assertEqual(b.collect_metrics(book,NOW+timedelta(hours=96),key='t',send=send),1)
        self.assertEqual(e['metricsHistory'][-1]['checkpointHours'],168)

    def test_missing_metrics_do_not_erase_prior(self):
        e=dict(id='a',bufferPostId='a',sentAt=gates.stamp(NOW-timedelta(hours=73)),
               metricsAt=gates.stamp(NOW-timedelta(hours=49)),metrics={'impressions':100})
        send=lambda *a:(200,b'{"data":{"post":{"metrics":[]}}}')
        self.assertEqual(b.collect_metrics({'posts':[e]},NOW,key='t',send=send,log=lambda *_:None),0)
        self.assertEqual(e['metrics']['impressions'],100)

    def test_mature_families_change_actual_order_not_small_samples(self):
        rows=[]
        for family,views,n in [('prep',50,8),('season',200,8),('matchup',9000,1)]:
            for i in range(n):
                rows.append(dict(id=f'research:{family}:{i}',sentAt=gates.stamp(NOW-timedelta(days=3)),
                    metricsAt=gates.stamp(NOW-timedelta(days=2)),metrics={'impressions':views}))
        order,evidence=s.research_order(['prep','matchup','season'],{'posts':rows},NOW)
        self.assertEqual(order,['season','matchup','prep'])
        self.assertNotIn('matchup',evidence)

    def test_followup_daily_budget(self):
        entries=[dict(id=str(i),bufferPostId=str(i),sentAt=gates.stamp(NOW-timedelta(hours=73)),
               metricsAt=gates.stamp(NOW-timedelta(hours=49)),metrics={'impressions':100}) for i in range(10)]
        send=lambda *a:(200,b'{"data":{"post":{"metrics":[{"type":"impressions","value":200}]}}}')
        self.assertEqual(b.collect_metrics({'posts':entries},NOW,key='t',send=send),8)
        self.assertEqual(b.collect_metrics({'posts':entries},NOW,key='t',send=send),0)

    def test_failed_reads_are_budgeted_and_first_reads_go_first(self):
        entries=[dict(id=str(i),bufferPostId=str(i),sentAt=gates.stamp(NOW-timedelta(hours=73)),
               metricsAt=gates.stamp(NOW-timedelta(hours=49)),metrics={'impressions':100}) for i in range(10)]
        entries.append(dict(id='first',bufferPostId='first',sentAt=gates.stamp(NOW-timedelta(hours=25))))
        calls=[]
        def failed(url,body,headers):
            calls.append(body['variables']['id'])
            return 500,b'temporary error'
        book={'posts':entries}
        self.assertEqual(b.collect_metrics(book,NOW,key='t',send=failed,log=lambda *_:None),0)
        self.assertEqual(calls[0],'first')
        self.assertEqual(len(calls),9)
        calls.clear()
        b.collect_metrics(book,NOW,key='t',send=failed,log=lambda *_:None)
        self.assertEqual(calls,['first'])

    def test_tickets_and_results_reserve_queue_before_optional_updates(self):
        self.assertIn('community',b.BUFFER_ESSENTIAL)
        self.assertIn('play',b.BUFFER_ESSENTIAL)
        self.assertIn('cashed',b.BUFFER_ESSENTIAL)
        self.assertNotIn('research',b.BUFFER_ESSENTIAL)
