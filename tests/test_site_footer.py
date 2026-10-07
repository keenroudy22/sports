"""Owner-approved informational-site footer copy."""
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SiteFooterTests(unittest.TestCase):
    def test_footer_keeps_disclosure_but_not_helpline_or_responsible_link(self):
        html = (ROOT / 'site' / 'index.html').read_text(encoding='utf-8')
        footer = html.split('<footer class="footer">', 1)[1].split('</footer>', 1)[0]
        for required in ('For entertainment only.', 'Not betting advice.', 'Nothing here is a guarantee.',
                         '21+ where legal.', 'Every best bet is graded at the price and book we posted.',
                         'Times are Eastern.', 'Cloudflare Web Analytics'):
            self.assertIn(required, footer)
        for removed in ('1-800-', 'Gambling problem?', 'href="#responsible"'):
            self.assertNotIn(removed, footer)

    def test_free_site_has_no_responsible_gaming_page_or_menu_link(self):
        more = (ROOT / 'site' / 'app-more.js').read_text(encoding='utf-8')
        self.assertNotIn('views.responsible', more)
        self.assertNotIn('href="#responsible"', more)
        self.assertNotIn('Responsible gaming', more)


if __name__ == '__main__':
    unittest.main()
