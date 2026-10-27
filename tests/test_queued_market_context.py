import copy,sys,unittest
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import queued_market_context as q

class ContextTests(unittest.TestCase):
 def test_original_discord_terms_survive_and_only_private_confirmed_x_changes(self):
  text='Best Bet: Game over 51.5 (-102, DraftKings)\n\nVerified reason.\n\n21+ only'
  e={'id':'p','bufferPostId':'old','dueAt':'2026-10-27T20:16:21Z','textHash':q.x_post.text_hash(text),
     'queuedText':text,'discord':{'state':'sent','text':text},'bufferImage':'https://cdn.example.test/original.png','card':True}
  pick={'id':'p','line':51.5,'odds':-102,'book':'DraftKings','marketType':'total'}
  now=datetime(2026,10,27,20,10,tzinfo=timezone.utc)
  for state,okay in [('sent',False),('unknown',False),('scheduled',True)]:
   row=copy.deepcopy(e)
   with patch.object(q.buffer_post,'graphql',return_value={'post':{'status':state,'text':text}}),patch.object(q.buffer_post,'x_channel',return_value={'id':'c'}),patch.object(q.buffer_post,'create_post',return_value='new') as create,patch.object(q.buffer_post,'delete_post') as delete,patch.object(q.x_post,'guard',return_value=[]):
    if okay:
     self.assertTrue(q.update(row,pick,('DraftKings',52.5,-105),now))
     self.assertEqual(row['discord'],e['discord']);self.assertEqual(pick['line'],51.5)
     self.assertIn('Original play only',row['queuedText']);self.assertIn('Now 52.5',row['queuedText'])
     self.assertEqual(row['priorBufferPosts'][0]['text'],text);delete.assert_called_once_with('old')
    else:
     with self.assertRaises(q.buffer_post.BufferError):q.update(row,pick,('DraftKings',52.5,-105),now)
     create.assert_not_called();delete.assert_not_called()
