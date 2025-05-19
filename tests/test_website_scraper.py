import unittest

from utils.website_scraper import WebsiteScraper, OrgRecord


class TestWebsiteScraper(unittest.TestCase):
    def setUp(self) -> None:
        self.scraper = WebsiteScraper(rate_limit=0)

    def test_parse_executives(self) -> None:
        html = """
        <html><body>
        <h2>Our Leadership Team</h2>
        <div class='exec'>
          <h3>Jane Doe</h3>
          <p>General Counsel</p>
        </div>
        <div class='exec'>
          <h3>John Smith</h3>
          <p>Chief Financial Officer</p>
          <p>john@example.com</p>
        </div>
        </body></html>
        """
        roles = ["General Counsel", "Chief Financial Officer"]
        execs = self.scraper.parse_executives(html, roles)
        self.assertEqual(len(execs), 2)
        self.assertEqual(execs[0].name, "Jane Doe")
        self.assertEqual(execs[0].title, "General Counsel")
        self.assertEqual(execs[1].email, "john@example.com")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
