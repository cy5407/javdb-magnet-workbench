"""Tests for javdb_scraper.fetch_magnets — no network.

Mocks the session.get boundary with a hand-written JavDB-shaped HTML
fixture and asserts:
- 200 success path parses title / code / magnet rows (name, size, tags, date, href)
- non-200 status maps to error dict (HTTP <code>) with empty magnets
- malformed / empty pages do not crash and return empty magnets
"""

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from javdb_scraper import fetch_magnets  # noqa: E402


# A trimmed-down JavDB detail page fragment that contains exactly the
# DOM nodes fetch_magnets selectors target. Two magnet rows so we can
# assert order is preserved.
_SUCCESS_HTML = """
<html>
  <head><title>JavDB</title></head>
  <body>
    <h2 class="title is-4">
      <strong class="current-title">SNOS-192 Sample Title</strong>
    </h2>
    <div class="panel-block">
      <span class="value"><a href="/codes/SNOS-192">SNOS-192</a></span>
    </div>
    <div id="magnets-content">
      <div class="item">
        <div class="magnet-name">
          <a href="magnet:?xt=urn:btih:AAAA1111&dn=SNOS-192">
            <span class="name">SNOS-192-FHD</span>
            <span class="meta">5.67GB, 1個文件</span>
            <span class="tag is-warning">高清</span>
            <span class="tag is-info">中字</span>
          </a>
        </div>
        <div class="date">
          <span class="time">2026-05-01</span>
        </div>
      </div>
      <div class="item">
        <div class="magnet-name">
          <a href="magnet:?xt=urn:btih:BBBB2222&dn=other">
            <span class="name">SNOS-192-SD</span>
            <span class="meta">1.2GB, 2個文件</span>
          </a>
        </div>
        <div class="date">
          <span class="time">2026-04-30</span>
        </div>
      </div>
      <div class="item">
        <!-- intentionally has no .magnet-name a -->
        <div class="bogus">noise</div>
      </div>
    </div>
  </body>
</html>
"""


def _resp(status: int, text: str = "") -> mock.MagicMock:
    r = mock.MagicMock()
    r.status_code = status
    r.text = text
    return r


class FetchMagnetsSuccess(unittest.TestCase):
    def setUp(self):
        self.session = mock.MagicMock()
        self.session.get.return_value = _resp(200, _SUCCESS_HTML)
        self.cookies = {"sess": "abc"}

    def test_parses_title_and_code(self):
        result = fetch_magnets("https://javdb.com/v/x", self.session, self.cookies)
        self.assertEqual(result["error"], "")
        self.assertEqual(result["url"], "https://javdb.com/v/x")
        self.assertEqual(result["title"], "SNOS-192 Sample Title")
        # The selector grabs the parent's text — for our fixture that's just
        # the code itself. Important: it must NOT be empty.
        self.assertIn("SNOS-192", result["code"])

    def test_session_called_with_cookies_and_timeout(self):
        fetch_magnets("https://javdb.com/v/x", self.session, self.cookies)
        call = self.session.get.call_args
        # url is positional
        self.assertEqual(call.args[0], "https://javdb.com/v/x")
        self.assertEqual(call.kwargs["cookies"], self.cookies)
        self.assertEqual(call.kwargs["timeout"], 30)

    def test_parses_each_magnet_row(self):
        result = fetch_magnets("https://javdb.com/v/x", self.session, self.cookies)
        # The third <div class="item"> has no link → skipped.
        self.assertEqual(len(result["magnets"]), 2)

        m0 = result["magnets"][0]
        self.assertEqual(m0["name"], "SNOS-192-FHD")
        self.assertEqual(m0["size"], "5.67GB, 1個文件")
        self.assertEqual(m0["tags"], ["高清", "中字"])
        self.assertEqual(m0["date"], "2026-05-01")
        self.assertTrue(m0["magnet"].startswith("magnet:?xt=urn:btih:AAAA1111"))

        m1 = result["magnets"][1]
        self.assertEqual(m1["name"], "SNOS-192-SD")
        self.assertEqual(m1["tags"], [])  # no .tag children in second row
        self.assertEqual(m1["date"], "2026-04-30")
        self.assertTrue(m1["magnet"].startswith("magnet:?xt=urn:btih:BBBB2222"))


class FetchMagnetsHttpError(unittest.TestCase):
    def test_non_200_returns_error_dict(self):
        session = mock.MagicMock()
        session.get.return_value = _resp(500, "<html>boom</html>")
        result = fetch_magnets("https://javdb.com/v/x", session, {})
        self.assertEqual(result["error"], "HTTP 500")
        self.assertEqual(result["magnets"], [])
        self.assertEqual(result["code"], "")
        self.assertEqual(result["title"], "")
        # url is echoed back so the caller can match the response to the request.
        self.assertEqual(result["url"], "https://javdb.com/v/x")

    def test_403_returns_http_403_error(self):
        # sidecar maps "403" substring → cloudflare_block, so this string
        # shape is part of the contract.
        session = mock.MagicMock()
        session.get.return_value = _resp(403, "")
        result = fetch_magnets("https://javdb.com/v/x", session, {})
        self.assertIn("403", result["error"])
        self.assertEqual(result["magnets"], [])

    def test_404_returns_http_404_error(self):
        session = mock.MagicMock()
        session.get.return_value = _resp(404, "")
        result = fetch_magnets("https://javdb.com/v/x", session, {})
        self.assertEqual(result["error"], "HTTP 404")


class FetchMagnetsEdgeCases(unittest.TestCase):
    def test_empty_html_yields_unknown_title_and_no_magnets(self):
        session = mock.MagicMock()
        session.get.return_value = _resp(200, "<html><body></body></html>")
        result = fetch_magnets("https://javdb.com/v/x", session, {})
        self.assertEqual(result["error"], "")
        # title defaults to "未知" when h2.title.is-4 .current-title is missing
        self.assertEqual(result["title"], "未知")
        self.assertEqual(result["code"], "")
        self.assertEqual(result["magnets"], [])

    def test_magnets_content_present_but_empty(self):
        html = """
        <html><body>
          <h2 class="title is-4"><span class="current-title">T</span></h2>
          <div id="magnets-content"></div>
        </body></html>
        """
        session = mock.MagicMock()
        session.get.return_value = _resp(200, html)
        result = fetch_magnets("https://javdb.com/v/x", session, {})
        self.assertEqual(result["title"], "T")
        self.assertEqual(result["magnets"], [])

    def test_magnet_row_without_name_or_meta_tags(self):
        # link exists but inner .name / .meta / .tag / date are all missing
        html = """
        <html><body>
          <div id="magnets-content">
            <div class="item">
              <div class="magnet-name">
                <a href="magnet:?xt=urn:btih:CAFEBABE"></a>
              </div>
            </div>
          </div>
        </body></html>
        """
        session = mock.MagicMock()
        session.get.return_value = _resp(200, html)
        result = fetch_magnets("https://javdb.com/v/x", session, {})
        self.assertEqual(len(result["magnets"]), 1)
        m = result["magnets"][0]
        self.assertEqual(m["name"], "")
        self.assertEqual(m["size"], "")
        self.assertEqual(m["tags"], [])
        self.assertEqual(m["date"], "")
        self.assertTrue(m["magnet"].startswith("magnet:?xt=urn:btih:CAFEBABE"))


class CreateSessionTests(unittest.TestCase):
    """Cover the create_session factory — header set + engine label."""

    def test_returns_session_and_engine_label(self):
        from javdb_scraper import create_session

        session, engine = create_session()
        # Engine is one of two known labels depending on curl_cffi availability.
        self.assertIn(engine, ("curl_cffi", "requests"))
        # Either branch sets browser-like Accept-Language; if it falls back to
        # requests it also sets a User-Agent.
        if engine == "requests":
            self.assertIn("User-Agent", session.headers)
            self.assertIn("Chrome", session.headers["User-Agent"])
        # Common headers are present regardless of engine.
        self.assertIn("Accept-Language", session.headers)
        self.assertIn("zh-TW", session.headers["Accept-Language"])

    def test_falls_back_to_requests_when_curl_cffi_missing(self):
        # When curl_cffi isn't importable (e.g. minimal CI image), the
        # factory must still return a usable session via stdlib `requests`.
        # Patch the module flag to simulate the missing-extension branch.
        import javdb_scraper as js

        with mock.patch.object(js, "HAS_CURL_CFFI", False):
            session, engine = js.create_session()
        self.assertEqual(engine, "requests")
        self.assertIn("User-Agent", session.headers)
        self.assertIn("Chrome", session.headers["User-Agent"])
        # Common headers still set in this branch.
        self.assertIn("Accept-Language", session.headers)
        self.assertEqual(
            session.headers["Accept-Encoding"], "gzip, deflate, br"
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
