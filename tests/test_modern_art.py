import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import pick_card as P
import research_art as R

class ModernArtTests(unittest.TestCase):
    def test_straight_preserves_exact_selection_and_uses_full_portrait(self):
        pick={'id':'preview','title':'Player Name UNDER 4.5 receptions','athleteId':'1','market':'rec','direction':'under','line':4.5,'projection':3.2,'odds':-110,'book':'FanDuel'}
        card=P.modern_svg(pick,featured=True,art={'kind':'photo','uri':'data:image/png;base64,TEST'})
        ET.fromstring(card)
        for word in ('Player Name','UNDER 4.5','receptions','-110','FanDuel','We project 3.2','HOT PLATE (POTD)'): self.assertIn(word,card)
        self.assertNotIn('clip-path="url(#plate)"',card)
        self.assertNotIn('Served at',card)
        self.assertEqual(P.svg_size(card),(1080,1350))

    def test_research_keeps_counts_and_positive_category_label(self):
        card=R.svg({'title':'80%+ TREND BOARD','kicker':'FULL SEASON','accent':'#5eeaa4','rows':[{'title':'Player','price':'Over 4.5 receptions','metric':'4/5 this season','detail':'-110 FanDuel'}]})
        ET.fromstring(card)
        for word in ('4/5','SLATE RESEARCH','80%+','21+ · Entertainment only'): self.assertIn(word,card)
        self.assertNotIn('NOT A PLAY',card)
        self.assertNotIn('not guaranteed',card)
        self.assertNotIn('100%',card)

if __name__=='__main__':unittest.main()
