"""核心邏輯回歸測試（不連網、純 stdlib）

測試對象：
- javdb_scraper.parse_size_gb
- javdb_scraper.parse_file_count
- realdebrid.RealDebrid._extract_code
- realdebrid.RealDebrid._filename_matches_code
- realdebrid.RealDebrid.pick_files

執行：
    python -m unittest discover -s tests -v
"""

import sys
import unittest
from pathlib import Path

# 把 repo root 加到 sys.path，讓測試能 import 上層模組
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from javdb_scraper import parse_size_gb, parse_file_count  # noqa: E402
from realdebrid import RealDebrid  # noqa: E402


def make_rd(min_size_mb: int = 500) -> RealDebrid:
    """建立 RealDebrid 物件但跳過 __init__（不連網、不需要 token）"""
    rd = RealDebrid.__new__(RealDebrid)
    rd.min_size_mb = min_size_mb
    return rd


def f(file_id: int, path: str, gb: float) -> dict:
    """建立測試用檔案 dict（與 RD API 回傳格式一致）"""
    return {"id": file_id, "path": path, "bytes": int(gb * 1024 * 1024 * 1024)}


# ---------------------------------------------------------------------------
# parse_size_gb
# ---------------------------------------------------------------------------
class ParseSizeGB(unittest.TestCase):
    def test_gb(self):
        self.assertAlmostEqual(parse_size_gb("5.67GB, 5個文件"), 5.67, places=2)

    def test_gb_no_decimal(self):
        self.assertAlmostEqual(parse_size_gb("4GB, 2個文件"), 4.0, places=2)

    def test_mb_converted_to_gb(self):
        # 512MB / 1024 = 0.5 GB
        self.assertAlmostEqual(parse_size_gb("512MB, 1個文件"), 0.5, places=4)

    def test_gb_lowercase(self):
        self.assertAlmostEqual(parse_size_gb("3.2gb"), 3.2, places=2)

    def test_unparseable_returns_zero(self):
        self.assertEqual(parse_size_gb("無法解析"), 0.0)

    def test_empty_string(self):
        self.assertEqual(parse_size_gb(""), 0.0)


# ---------------------------------------------------------------------------
# parse_file_count
# ---------------------------------------------------------------------------
class ParseFileCount(unittest.TestCase):
    def test_normal(self):
        self.assertEqual(parse_file_count("5.67GB, 5個文件"), 5)

    def test_single_file(self):
        self.assertEqual(parse_file_count("512MB, 1個文件"), 1)

    def test_unparseable_returns_999(self):
        self.assertEqual(parse_file_count("5.67GB"), 999)

    def test_empty_returns_999(self):
        self.assertEqual(parse_file_count(""), 999)


# ---------------------------------------------------------------------------
# RealDebrid._extract_code
# ---------------------------------------------------------------------------
class ExtractCode(unittest.TestCase):
    def test_dash_separated(self):
        magnet = "magnet:?xt=urn:btih:abc&dn=%5Bjavdb.com%5DSNOS-192"
        self.assertEqual(RealDebrid._extract_code(magnet), "SNOS-192")

    def test_no_separator(self):
        magnet = "magnet:?xt=urn:btih:abc&dn=snos192"
        self.assertEqual(RealDebrid._extract_code(magnet), "SNOS-192")

    def test_underscore_separator(self):
        magnet = "magnet:?xt=urn:btih:abc&dn=ipzz_851"
        self.assertEqual(RealDebrid._extract_code(magnet), "IPZZ-851")

    def test_lowercase_normalized_to_upper(self):
        magnet = "magnet:?xt=urn:btih:abc&dn=ipzz-851"
        self.assertEqual(RealDebrid._extract_code(magnet), "IPZZ-851")

    def test_no_code_returns_none(self):
        magnet = "magnet:?xt=urn:btih:abc&dn=Some Random Anime Episode"
        self.assertIsNone(RealDebrid._extract_code(magnet))

    def test_no_dn_returns_none(self):
        magnet = "magnet:?xt=urn:btih:abc"
        self.assertIsNone(RealDebrid._extract_code(magnet))

    def test_empty_magnet(self):
        self.assertIsNone(RealDebrid._extract_code(""))

    def test_url_encoded_dn(self):
        # dn=[javdb.com]ABF-350.torrent (URL encoded brackets and dot suffix)
        magnet = "magnet:?xt=urn:btih:abc&dn=%5Bjavdb.com%5DABF-350.torrent"
        self.assertEqual(RealDebrid._extract_code(magnet), "ABF-350")


# ---------------------------------------------------------------------------
# RealDebrid._filename_matches_code
# ---------------------------------------------------------------------------
class FilenameMatchesCode(unittest.TestCase):
    def test_exact_match(self):
        self.assertTrue(RealDebrid._filename_matches_code("SNOS-192.mp4", "SNOS-192"))

    def test_lowercase_filename(self):
        self.assertTrue(RealDebrid._filename_matches_code("snos-192.mp4", "SNOS-192"))

    def test_uppercase_code_lower_file(self):
        self.assertTrue(RealDebrid._filename_matches_code("4k2.me@snos-192.mp4", "SNOS-192"))

    def test_no_dash_in_filename(self):
        # SNOS192.mp4 should match code SNOS-192
        self.assertTrue(RealDebrid._filename_matches_code("SNOS192.mp4", "SNOS-192"))

    def test_underscore_in_filename(self):
        # snos_192 should normalize to snos-192 then match
        self.assertTrue(RealDebrid._filename_matches_code("snos_192.mp4", "SNOS-192"))

    def test_multipart_match(self):
        # Multi-part files should still match
        self.assertTrue(RealDebrid._filename_matches_code("ABF-350-1.mp4", "ABF-350"))
        self.assertTrue(RealDebrid._filename_matches_code("ABF-350-2.mp4", "ABF-350"))

    def test_unrelated_filename(self):
        self.assertFalse(
            RealDebrid._filename_matches_code("三 上 悠 亚 想 要 跟 你 决 胜 负.mp4", "SNOS-192")
        )

    def test_different_code(self):
        self.assertFalse(RealDebrid._filename_matches_code("IPZZ-851.mp4", "SNOS-192"))

    def test_empty_code_returns_false(self):
        self.assertFalse(RealDebrid._filename_matches_code("anything.mp4", ""))


# ---------------------------------------------------------------------------
# RealDebrid.pick_files
# ---------------------------------------------------------------------------
class PickFilesAll(unittest.TestCase):
    def test_all_returns_every_id(self):
        rd = make_rd()
        files = [f(1, "a.url", 0.0), f(2, "video.mp4", 5.0), f(3, "ad.mp4", 0.02)]
        self.assertEqual(rd.pick_files(files, strategy="all"), [1, 2, 3])

    def test_all_empty_list(self):
        rd = make_rd()
        self.assertEqual(rd.pick_files([], strategy="all"), [])


class PickFilesVideo(unittest.TestCase):
    def test_only_video_extensions(self):
        rd = make_rd()
        files = [
            f(1, "promo.url", 0.0),
            f(2, "main.mp4", 5.0),
            f(3, "ad.mp4", 0.02),
            f(4, "extra.mkv", 1.5),
            f(5, "info.txt", 0.0),
        ]
        # video 策略保留所有影片副檔名（不過濾大小）
        self.assertEqual(sorted(rd.pick_files(files, strategy="video")), [2, 3, 4])

    def test_no_video_falls_back_to_largest(self):
        rd = make_rd()
        files = [f(1, "a.url", 0.0), f(2, "b.txt", 0.001), f(3, "c.url", 0.0)]
        # 沒有影片副檔名 → 退回最大檔（id=2 因為最大）
        self.assertEqual(rd.pick_files(files, strategy="video"), [2])


class PickFilesLargest(unittest.TestCase):
    def test_pick_largest_video(self):
        rd = make_rd()
        files = [
            f(1, "small_ad.mp4", 0.02),
            f(2, "main_video.mp4", 5.9),
            f(3, "trailer.mp4", 0.02),
        ]
        self.assertEqual(rd.pick_files(files, strategy="largest"), [2])

    def test_largest_skips_non_video_when_video_present(self):
        rd = make_rd()
        # 即使非影片檔最大，largest 仍只看影片
        files = [
            f(1, "huge_archive.zip", 10.0),
            f(2, "video.mp4", 5.0),
            f(3, "small.mp4", 0.5),
        ]
        self.assertEqual(rd.pick_files(files, strategy="largest"), [2])

    def test_largest_falls_back_when_no_video(self):
        rd = make_rd()
        files = [f(1, "a.zip", 1.0), f(2, "b.rar", 2.0), f(3, "c.7z", 0.5)]
        self.assertEqual(rd.pick_files(files, strategy="largest"), [2])


class PickFilesSmart(unittest.TestCase):
    """smart 策略：番號比對優先，退回 size 門檻，最後退回最大檔"""

    def test_smart_code_match_with_size_filter(self):
        """有番號匹配，且檔案 >= 門檻 → 只選番號匹配且過大小的"""
        rd = make_rd(min_size_mb=500)
        magnet = "magnet:?xt=urn:btih:abc&dn=%5Bjavdb.com%5DSNOS-192"
        files = [
            f(1, "promo.url", 0.0),
            f(2, "4k2.me@snos-192.mp4", 5.9),     # 番號匹配，大檔 ✓
            f(3, "三上悠亚直播.mp4", 0.02),         # 不匹配
            f(4, "ad_no_code.mp4", 0.02),          # 不匹配
        ]
        self.assertEqual(rd.pick_files(files, strategy="smart", magnet=magnet), [2])

    def test_smart_code_match_multipart(self):
        """多段切割時兩段都要選到（番號相符 + 大小過門檻）"""
        rd = make_rd(min_size_mb=500)
        magnet = "magnet:?xt=urn:btih:abc&dn=ABF-350"
        files = [
            f(1, "ABF-350-1.mp4", 4.0),
            f(2, "ABF-350-2.mp4", 4.0),
            f(3, "ad.mp4", 0.02),
        ]
        self.assertEqual(sorted(rd.pick_files(files, strategy="smart", magnet=magnet)), [1, 2])

    def test_smart_code_match_no_size_pass_keeps_code_matches(self):
        """番號全匹配但都低於 size 門檻 → 仍保留番號匹配的（不再縮減）"""
        rd = make_rd(min_size_mb=500)
        magnet = "magnet:?xt=urn:btih:abc&dn=SNOS-192"
        files = [
            f(1, "snos-192.mp4", 0.3),  # 番號匹配但 < 500MB
            f(2, "other.mp4", 1.0),     # 不匹配
        ]
        self.assertEqual(rd.pick_files(files, strategy="smart", magnet=magnet), [1])

    def test_smart_no_code_falls_back_to_size_threshold(self):
        """磁力沒番號（動畫情境）→ 走 size 門檻"""
        rd = make_rd(min_size_mb=500)
        magnet = "magnet:?xt=urn:btih:abc&dn=Some Random Anime Episode 01.mkv"
        files = [
            f(1, "ad.mp4", 0.02),
            f(2, "anime_ep01.mkv", 1.5),  # 大檔 ✓
            f(3, "small_extra.mkv", 0.2),
        ]
        self.assertEqual(rd.pick_files(files, strategy="smart", magnet=magnet), [2])

    def test_smart_code_present_but_no_filename_match_falls_back(self):
        """磁力有番號但 torrent 內檔名都不含番號 → 退回 size 門檻"""
        rd = make_rd(min_size_mb=500)
        magnet = "magnet:?xt=urn:btih:abc&dn=SNOS-192"
        files = [
            f(1, "unrelated_video.mp4", 5.0),  # >500MB
            f(2, "another.mp4", 0.01),
        ]
        # 番號 SNOS-192 沒命中任何檔名 → 走 size 門檻 → 只剩 id=1
        self.assertEqual(rd.pick_files(files, strategy="smart", magnet=magnet), [1])

    def test_smart_no_size_pass_falls_back_to_largest(self):
        """所有檔都低於門檻、且無番號匹配 → 退回最大檔"""
        rd = make_rd(min_size_mb=500)
        files = [
            f(1, "a.mp4", 0.1),
            f(2, "b.mp4", 0.3),  # 最大但仍 < 500MB
            f(3, "c.mp4", 0.05),
        ]
        self.assertEqual(rd.pick_files(files, strategy="smart"), [2])

    def test_smart_empty_files(self):
        rd = make_rd()
        self.assertEqual(rd.pick_files([], strategy="smart"), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
