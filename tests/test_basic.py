"""基本テスト。すべてダミーデータで実行する（実ログは使用しない）。

実行: python -m pytest tests/ または python tests/test_basic.py
"""

from __future__ import annotations

import unittest

from legacy_bbs_toolkit import host_pattern_detector
from legacy_bbs_toolkit.parsers.zantei import ZanteiParser
from legacy_bbs_toolkit.registry import (
    NamespaceConflictError,
    ParserRegistry,
    detect_and_select,
)


def make_block(post_id: int, title: str, author: str, wdate: str, body: str) -> str:
    return (
        f"<!-- {post_id} -->\n"
        f'<FONT size="+1" color="#fffffe"><B>{title}</B></FONT>\n'
        f"　投稿者：<B>{author}</B>\n"
        f'　<FONT size="-1">投稿日：{wdate}</FONT>\n'
        f"<BLOCKQUOTE>\n<PRE>\n{body}\n</PRE>\n\n</BLOCKQUOTE>\n<HR>\n"
        f"<!-- -->\n"
    )


SAMPLE_1 = make_block(
    1, "＞", "名無し", "2003/09/11(木)12時34分56秒", "こんにちは"
)


class TestDetection(unittest.TestCase):
    def test_detect_true(self):
        self.assertTrue(ZanteiParser().detect(SAMPLE_1))

    def test_detect_false(self):
        self.assertFalse(ZanteiParser().detect("ただのテキスト"))


class TestExtraction(unittest.TestCase):
    def setUp(self):
        self.parser = ZanteiParser(host_pattern_salt="test-salt")

    def test_basic_fields(self):
        result = self.parser.parse(SAMPLE_1)
        self.assertEqual(len(result), 1)
        r = result.records[0]
        self.assertEqual(r.post_id, "1")
        self.assertEqual(r.title_raw, "＞")
        self.assertEqual(r.author_raw, "名無し")
        self.assertEqual(r.raw_timestamp, "2003/09/11(木)12時34分56秒")
        self.assertEqual(r.parsed_timestamp, "2003-09-11T12:34:56+09:00")
        self.assertIn("こんにちは", r.body_raw)
        self.assertEqual(r.provenance["assumed_timezone_offset"], "+09:00")

    def test_author_with_mailto(self):
        block = make_block(
            2,
            "",
            '<A href="mailto:x@example.com">投稿者A</A>',
            "2003/09/11(木)12時34分56秒",
            "本文",
        )
        r = self.parser.parse(block).records[0]
        self.assertEqual(r.author_raw, "投稿者A")
        self.assertTrue(r.author_email_detected)
        # ハッシュが8文字の16進数文字列であること
        self.assertRegex(r.author_email_sanitized, r"^[0-9a-f]{8}$")

    def test_host_meta_in_envlist_comment(self):
        """$envlistのHTMLコメント内のIPv4を検出・ハッシュ化する。"""
        block = make_block(
            5, "", "名無し", "2003/09/11(木)12時34分56秒", "本文"
        ).replace(
            "</BLOCKQUOTE>",
            "<!--192.168.0.1<BR>Mozilla/5.0 (Windows)-->\n</BLOCKQUOTE>",
        )
        r = self.parser.parse(block).records[0]
        self.assertTrue(r.host_meta_detected)
        self.assertRegex(r.host_meta_sanitized, r"^[0-9a-f]{8}$")
        self.assertTrue(r.ua_meta_detected)
        self.assertRegex(r.ua_meta_sanitized, r"^[0-9a-f]{8}$")

    def test_author_pattern_hits_tracked(self):
        """author_rawにドメイン名が含まれる場合、provenance.author_pattern_hitsに記録。"""
        block = make_block(
            6, "", "xxx.ne.jp名無し", "2003/09/11(木)12時34分56秒", "本文"
        )
        r = self.parser.parse(block).records[0]
        self.assertGreater(r.provenance.get("author_pattern_hits", 0), 0)

    def test_title_pattern_hits_tracked(self):
        """title_rawにドメイン名が含まれる場合、provenance.title_pattern_hitsに記録。"""
        block = make_block(
            7, "＞xxx.ne.jp", "名無し", "2003/09/11(木)12時34分56秒", "本文"
        )
        r = self.parser.parse(block).records[0]
        self.assertGreater(r.provenance.get("title_pattern_hits", 0), 0)

    def test_body_with_literal_pre(self):
        """本文中に文字通りの</PRE>があっても本文が途中で切れない
        （貪欲マッチ修正の回帰テスト）。"""
        block = make_block(
            3, "", "名無し", "2003/09/11(木)12時34分56秒",
            "この</PRE>はただの文字列\nまだ本文続く",
        )
        r = self.parser.parse(block).records[0]
        self.assertIn("まだ本文続く", r.body_raw)

    def test_body_host_pattern_sanitized(self):
        block = make_block(
            4, "", "名無し", "2003/09/11(木)12時34分56秒",
            "xxx.ne.jpから来た192.168.1.1の奴",
        )
        r = self.parser.parse(block).records[0]
        self.assertEqual(r.provenance["body_pattern_hits"], 2)
        self.assertNotIn("ne.jp", r.body_sanitized)
        self.assertNotIn("192.168.1.1", r.body_sanitized)
        # body_rawは原文のまま（Archive First）
        self.assertIn("ne.jp", r.body_raw)

    def test_unclosed_block_warning(self):
        text = SAMPLE_1 + "<!-- 99 -->\n終了マーカーの無いブロック\n"
        result = self.parser.parse(text)
        self.assertEqual(len(result.records), 1)
        self.assertEqual(len(result.warnings), 1)
        self.assertIn("99", result.warnings[0])

    def test_missing_middle_end_marker_does_not_swallow_next(self):
        """中間ブロックの終了マーカー欠落時、次ブロックを呑み込まない。"""
        broken = (
            "<!-- 10 -->\n終了マーカーが無い\n"  # endなし
            + make_block(11, "", "名無しB", "2003/09/11(木)13時00分00秒", "次の投稿")
        )
        result = self.parser.parse(broken)
        self.assertEqual([r.post_id for r in result.records], ["11"])
        self.assertEqual(len(result.warnings), 1)
        self.assertIn("10", result.warnings[0])

    def test_duplicate_post_id_warning(self):
        text = SAMPLE_1 + SAMPLE_1
        result = self.parser.parse(text)
        self.assertEqual(len(result.records), 2)  # 両方保持（Archive First）
        self.assertTrue(any("duplicate" in w for w in result.warnings))

    def test_to_dict_json_serializable(self):
        import json

        r = self.parser.parse(SAMPLE_1).records[0]
        json.dumps(r.to_dict(), ensure_ascii=False)  # 例外が出なければOK


class TestHostPatternDetector(unittest.TestCase):
    def test_hash_is_8_chars(self):
        _, records = host_pattern_detector.sanitize("xxx.ne.jp", salt="s")
        self.assertEqual(len(records[0].salted_hash), 8)

    def test_no_false_positive_on_plain_japanese(self):
        sanitized, records = host_pattern_detector.sanitize(
            "普通の書き込みです。こんにちは.今日はいい天気。", salt="s"
        )
        self.assertEqual(records, [])

    def test_adjacent_japanese_still_detected(self):
        _, records = host_pattern_detector.sanitize(
            "お前xxx.ne.jpだろproxy使うな", salt="s"
        )
        names = {r.pattern_name for r in records}
        self.assertIn("jp_domain", names)
        self.assertIn("proxy_hint", names)


class TestEncoding(unittest.TestCase):
    def _detect(self, s: str, enc: str) -> str:
        from legacy_bbs_toolkit.cli import _detect_encoding
        return _detect_encoding(s.encode(enc))

    def test_utf8(self):
        self.assertEqual(self._detect("こんにちは", "utf-8"), "utf-8")

    def test_ascii_treated_as_utf8(self):
        from legacy_bbs_toolkit.cli import _detect_encoding
        self.assertEqual(_detect_encoding(b"hello world"), "utf-8")

    def test_cp932(self):
        self.assertEqual(self._detect("こんにちは", "cp932"), "cp932")

    def test_euc_jp(self):
        self.assertEqual(self._detect("こんにちは", "euc_jp"), "euc_jp")

    def test_cp932_exclusive_range(self):
        # 0x81は CP932 専用リードバイト（EUC-JPには出現しない）
        from legacy_bbs_toolkit.cli import _detect_encoding
        raw = bytes([0x82, 0xa0])  # CP932の「ア」
        self.assertEqual(_detect_encoding(raw), "cp932")

    def test_euc_exclusive_range(self):
        # 0xA4はEUC-JP専用リードバイト（CP932には出現しない）
        from legacy_bbs_toolkit.cli import _detect_encoding
        raw = bytes([0xa4, 0xb3])  # EUC-JPの「こ」
        self.assertEqual(_detect_encoding(raw), "euc_jp")


class TestNgCheckBridge(unittest.TestCase):
    def test_php_missing_raises_bridge_error(self):
        from legacy_bbs_toolkit.ng_check_bridge import (
            NgCheckBridgeError,
            sanitize_with_ng_check,
        )
        with self.assertRaises(NgCheckBridgeError) as ctx:
            sanitize_with_ng_check("テスト", php_path="no-such-php")
        self.assertIn("見つからない", str(ctx.exception))

    def test_result_fields(self):
        from legacy_bbs_toolkit.ng_check_bridge import NgCheckResult
        r = NgCheckResult(ng_detected=True, match_count=2, sanitized_text="〇〇")
        self.assertTrue(r.ng_detected)
        self.assertEqual(r.match_count, 2)
        self.assertEqual(r.sanitized_text, "〇〇")


class TestRegistry(unittest.TestCase):
    def test_duplicate_namespace_rejected(self):
        r = ParserRegistry()
        r.register(ZanteiParser())
        with self.assertRaises(NamespaceConflictError):
            r.register(ZanteiParser())

    def test_user_override_detection_false_rejected(self):
        r = ParserRegistry()
        r.register(ZanteiParser())
        with self.assertRaises(ValueError):
            detect_and_select(
                r, "対応不能なテキスト",
                user_override="legacy-bbs-toolkit.parser.zantei",
            )

    def test_selection(self):
        r = ParserRegistry()
        r.register(ZanteiParser())
        ns, prov = detect_and_select(r, SAMPLE_1)
        self.assertEqual(ns, "legacy-bbs-toolkit.parser.zantei")
        self.assertEqual(prov["selection_path"], "selection")


if __name__ == "__main__":
    unittest.main()
