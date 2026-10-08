"""Owner-approved informational-site footer copy."""
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SiteFooterTests(unittest.TestCase):
    def test_footer_is_exactly_the_owner_approved_one_line(self):
        html = (ROOT / 'site' / 'index.html').read_text(encoding='utf-8')
        footer = html.split('<footer class="footer">', 1)[1].split('</footer>', 1)[0]
        self.assertEqual(footer.strip(), '<p>21+ · Entertainment only</p>')

    def test_record_and_start_here_keep_the_context_off_the_footer(self):
        more = (ROOT / 'site' / 'app-more.js').read_text(encoding='utf-8')
        self.assertIn('Win or lose, at the price and book we posted.', more)
        self.assertEqual(more.count('Times are Eastern.'), 1)
        self.assertEqual(more.count("Analytics: Cloudflare's cookie-free counter. Nothing personal is collected."), 1)

    def test_free_site_has_no_responsible_gaming_page_or_menu_link(self):
        more = (ROOT / 'site' / 'app-more.js').read_text(encoding='utf-8')
        self.assertNotIn('views.responsible', more)
        self.assertNotIn('href="#responsible"', more)
        self.assertNotIn('Responsible gaming', more)

    def test_public_navigation_hides_private_desk_pages(self):
        more = (ROOT / 'site' / 'app-more.js').read_text(encoding='utf-8')
        for removed in ('href="#schedule"', 'href="#status"', 'Release schedule', 'Data status'):
            self.assertNotIn(removed, more)
        self.assertIn('views.schedule = async () => views.more()', more)
        self.assertIn('views.status = async () => views.more()', more)

    def test_desk_timing_is_written_only_to_ignored_local_status(self):
        build = (ROOT / 'scripts' / 'build_site.py').read_text(encoding='utf-8')
        self.assertIn("write(ROOT / 'work' / 'desk-status.json'", build)
        self.assertIn('work/', (ROOT / '.gitignore').read_text(encoding='utf-8'))
        self.assertNotIn("'deskRuns': runs", build)
        self.assertNotIn("'deskRuns': desk_runs()}", build.split("write(OUT / 'today.json'", 1)[1])


if __name__ == '__main__':
    unittest.main()
