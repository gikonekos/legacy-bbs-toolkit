"""基本テスト。すべてダミーデータで実行する（実ログは使用しない）。

実行: python -m pytest tests/ または python tests/test_basic.py
"""

from __future__ import annotations

import unittest

from legacy_bbs_toolkit import host_pattern_detector
from legacy_bbs_toolkit.parsers.hr_boundary import (
    AriakeParser,
    MeisoParser,
    MizuiroParser,
    RemixParser,
)
from legacy_bbs_toolkit.parsers.ksphp_plus import KsphpPlusParser
from legacy_bbs_toolkit.parsers.kscrr1p9 import Kscrr1p9Parser
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


def make_ksphp_block(
    post_id: int,
    title: str,
    author: str,
    wdate: str,
    body: str,
    env: str = "",
) -> str:
    """sub/template.html "message"ブロックのテンプレート構造を模したダミーHTML。"""
    env_block = f'<div class="env">{env}</div>\n' if env else ""
    return (
        f'<div class="m" id="m{post_id}">\n'
        f'<span class="nw">\n'
        f'<span class="mnum">{post_id}.</span>\n'
        f'<span class="ms">{title}</span>&nbsp;&nbsp;\n'
        f'<span class="mu">投稿者</span>\n'
        f'<span class="mun">{author}</span>&nbsp;&nbsp;\n'
        f'<span class="md">投稿日 {wdate}<a id="a{post_id}">&nbsp;</a>'
        f'<span class="nb"></span></span>\n'
        f'</span>\n'
        f'<pre class="msgnormal">{body}</pre>\n'
        f"{env_block}"
        f"</div>\n"
    )


KSPHP_SAMPLE_1 = make_ksphp_block(
    101, "テスト投稿", "名無しさん", "2026/07/20(月)09:15:30", "こんにちは"
)


class TestDetection(unittest.TestCase):
    def test_detect_true(self):
        self.assertTrue(Kscrr1p9Parser().detect(SAMPLE_1))

    def test_detect_false(self):
        self.assertFalse(Kscrr1p9Parser().detect("ただのテキスト"))


class TestExtraction(unittest.TestCase):
    def setUp(self):
        self.parser = Kscrr1p9Parser(host_pattern_salt="test-salt")

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


class TestKsphpPlusDetection(unittest.TestCase):
    def test_detect_true(self):
        self.assertTrue(KsphpPlusParser().detect(KSPHP_SAMPLE_1))

    def test_detect_false(self):
        self.assertFalse(KsphpPlusParser().detect("ただのテキスト"))

    def test_detect_does_not_match_zantei_marker(self):
        """zantei用マーカーではdetect=Falseになる（両系列は排他）。"""
        self.assertFalse(KsphpPlusParser().detect(SAMPLE_1))

    def test_zantei_does_not_match_ksphp_marker(self):
        self.assertFalse(Kscrr1p9Parser().detect(KSPHP_SAMPLE_1))


class TestKsphpPlusExtraction(unittest.TestCase):
    def setUp(self):
        self.parser = KsphpPlusParser(host_pattern_salt="test-salt")

    def test_basic_fields(self):
        result = self.parser.parse(KSPHP_SAMPLE_1)
        self.assertEqual(len(result), 1)
        r = result.records[0]
        self.assertEqual(r.post_id, "101")
        self.assertEqual(r.title_raw, "テスト投稿")
        self.assertEqual(r.author_raw, "名無しさん")
        self.assertEqual(r.raw_timestamp, "2026/07/20(月)09:15:30")
        self.assertEqual(r.parsed_timestamp, "2026-07-20T09:15:30+09:00")
        self.assertIn("こんにちは", r.body_raw)
        self.assertEqual(r.parser_namespace, "legacy-bbs-toolkit.parser.ksphp_plus")
        self.assertEqual(r.provenance["assumed_timezone_offset"], "+09:00")

    def test_author_with_mailto(self):
        block = make_ksphp_block(
            102,
            "",
            '<A href="mailto:x@example.com">投稿者A</A>',
            "2026/07/20(月)09:15:30",
            "本文",
        )
        r = self.parser.parse(block).records[0]
        self.assertEqual(r.author_raw, "投稿者A")
        self.assertTrue(r.author_email_detected)
        self.assertRegex(r.author_email_sanitized, r"^[0-9a-f]{8}$")

    def test_env_host_and_ua_detected(self):
        """<div class="env">{ENVADDR}{ENVBR}{ENVUA}</div>のIPv4・UAを検出・ハッシュ化する。"""
        block = make_ksphp_block(
            103, "", "名無しさん", "2026/07/20(月)09:15:30", "本文",
            env="192.168.0.1<br>Mozilla/5.0 (Windows)",
        )
        r = self.parser.parse(block).records[0]
        self.assertTrue(r.host_meta_detected)
        self.assertRegex(r.host_meta_sanitized, r"^[0-9a-f]{8}$")
        self.assertTrue(r.ua_meta_detected)
        self.assertRegex(r.ua_meta_sanitized, r"^[0-9a-f]{8}$")

    def test_env_absent_when_ippprint_disabled(self):
        """IPPRINT/UAPRINT無効時、$envlistブロック自体が出力されない想定。"""
        block = make_ksphp_block(
            104, "", "名無しさん", "2026/07/20(月)09:15:30", "本文", env="",
        )
        r = self.parser.parse(block).records[0]
        self.assertFalse(r.host_meta_detected)
        self.assertFalse(r.ua_meta_detected)

    def test_body_pattern_hits_tracked_and_sanitized(self):
        block = make_ksphp_block(
            105, "", "名無しさん", "2026/07/20(月)09:15:30",
            "xxx.ne.jpから来た192.168.1.1の奴",
        )
        r = self.parser.parse(block).records[0]
        self.assertEqual(r.provenance["body_pattern_hits"], 2)
        self.assertNotIn("ne.jp", r.body_sanitized)
        self.assertNotIn("192.168.1.1", r.body_sanitized)
        # body_rawは原文のまま（Archive First）
        self.assertIn("ne.jp", r.body_raw)

    def test_body_with_literal_pre_close_tag(self):
        """本文中に文字通りの</pre>があっても本文が途中で切れない。"""
        block = make_ksphp_block(
            106, "", "名無しさん", "2026/07/20(月)09:15:30",
            "この&lt;/pre&gt;はただの文字列\nまだ本文続く",
        )
        r = self.parser.parse(block).records[0]
        self.assertIn("まだ本文続く", r.body_raw)

    def test_duplicate_post_id_warning(self):
        text = KSPHP_SAMPLE_1 + KSPHP_SAMPLE_1
        result = self.parser.parse(text)
        self.assertEqual(len(result.records), 2)  # 両方保持（Archive First）
        self.assertTrue(any("duplicate" in w for w in result.warnings))

    def test_block_boundary_not_swallowed_by_next_block(self):
        """次ブロックの開始マーカーを境界として正しく分割される
        （html_escape()により本文中の生div混入は通常起こらない前提の回帰確認）。"""
        text = KSPHP_SAMPLE_1 + make_ksphp_block(
            107, "", "名無しさん2", "2026/07/20(月)10:00:00", "次の投稿"
        )
        result = self.parser.parse(text)
        self.assertEqual([r.post_id for r in result.records], ["101", "107"])

    def test_to_dict_json_serializable(self):
        import json

        r = self.parser.parse(KSPHP_SAMPLE_1).records[0]
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


class TestHrBoundaryDetection(unittest.TestCase):
    """remix/mizuiro/meiso/ariakeの相互排他性、zantei/ksphp_plusとの
    非衝突を確認する（実データ検証で見つかった大文字小文字バグの回帰）。"""

    def make_hr_block(self, tag, title, author, wdate, body, mailto=None):
        author_field = (
            f'<a href="mailto:{mailto}">{author}</a>' if mailto else author
        )
        return (
            f'<hr><font size="+1"><{tag}>{title}</{tag}></font>'
            f'　投稿者：<{tag}>{author_field}</{tag}>\n'
            f'<font size="-1">　投稿日：{wdate}</font><p>\n'
            f'<blockquote><pre>{body}</pre></blockquote>\n'
        )

    def setUp(self):
        self.remix_block = self.make_hr_block(
            "b", "件名", "名無し", "2026/08/01(土)16時24分32秒", "本文"
        )
        self.mizuiro_block = self.make_hr_block(
            "b", "件名", "名無し", "2023年08月01日(火)11時24分30秒", "本文"
        )
        self.meiso_block = self.make_hr_block(
            "strong", "(無題)", "名無し", "2025年10月01日(水)23時12分57秒", "本文"
        )
        self.ariake_block = self.make_hr_block(
            "b", "件名", "名無し", "06月08日(月)17時33分50秒", "本文"
        )

    def test_each_detects_only_its_own(self):
        cases = [
            ("remix", RemixParser(), self.remix_block),
            ("mizuiro", MizuiroParser(), self.mizuiro_block),
            ("meiso", MeisoParser(), self.meiso_block),
            ("ariake", AriakeParser(), self.ariake_block),
        ]
        for name, parser, block in cases:
            self.assertTrue(parser.detect(block), f"{name} should detect its own block")

    def test_mutual_exclusion(self):
        all_parsers = {
            "remix": RemixParser(),
            "mizuiro": MizuiroParser(),
            "meiso": MeisoParser(),
            "ariake": AriakeParser(),
        }
        blocks = {
            "remix": self.remix_block,
            "mizuiro": self.mizuiro_block,
            "meiso": self.meiso_block,
            "ariake": self.ariake_block,
        }
        for owner, block in blocks.items():
            hits = [name for name, p in all_parsers.items() if p.detect(block)]
            self.assertEqual(hits, [owner], f"block for {owner} matched {hits}")

    def test_does_not_match_zantei_sample(self):
        """zanteiの大文字<B>テンプレートを誤検出しない（実データ回帰）。"""
        for parser in (RemixParser(), MizuiroParser(), MeisoParser(), AriakeParser()):
            self.assertFalse(parser.detect(SAMPLE_1))

    def test_no_year_pattern_does_not_partial_match_with_year(self):
        """漢字・年ありの日付文字列の中間から、年なしパターンが
        部分一致で誤検出しないことを確認する（202308.htmlで発見・修正した
        バグの回帰テスト）。"""
        self.assertFalse(AriakeParser().detect(self.mizuiro_block))


class TestHrBoundaryExtraction(unittest.TestCase):
    def test_remix_basic_fields_and_sequential_id(self):
        p = RemixParser(host_pattern_salt="s")
        block1 = TestHrBoundaryDetection().make_hr_block(
            "b", "件名1", "名無し1", "2026/08/01(土)16時24分32秒", "本文1"
        )
        block2 = TestHrBoundaryDetection().make_hr_block(
            "b", "件名2", "名無し2", "2026/08/01(土)17時00分00秒", "本文2"
        )
        result = p.parse(block1 + block2)
        self.assertEqual(len(result), 2)
        self.assertEqual([r.post_id for r in result.records], ["1", "2"])
        r = result.records[0]
        self.assertEqual(r.title_raw, "件名1")
        self.assertEqual(r.author_raw, "名無し1")
        self.assertEqual(r.raw_timestamp, "2026/08/01(土)16時24分32秒")
        self.assertEqual(r.parsed_timestamp, "2026-08-01T16:24:32+09:00")
        self.assertEqual(r.parser_namespace, "legacy-bbs-toolkit.parser.remix")
        self.assertEqual(r.provenance["post_id_synthetic"], "sequential")

    def test_mizuiro_mailto_author(self):
        p = MizuiroParser(host_pattern_salt="s")
        block = TestHrBoundaryDetection().make_hr_block(
            "b", "件名", "投稿者A", "2023年08月01日(火)11時24分30秒", "本文",
            mailto="x@example.com",
        )
        r = p.parse(block).records[0]
        self.assertEqual(r.author_raw, "投稿者A")
        self.assertTrue(r.author_email_detected)
        self.assertRegex(r.author_email_sanitized, r"^[0-9a-f]{8}$")

    def test_meiso_uses_strong_tag(self):
        p = MeisoParser(host_pattern_salt="s")
        block = TestHrBoundaryDetection().make_hr_block(
            "strong", "(無題)", "名無し", "2025年10月01日(水)23時12分57秒", "本文"
        )
        r = p.parse(block).records[0]
        self.assertEqual(r.title_raw, "(無題)")
        self.assertEqual(r.parsed_timestamp, "2025-10-01T23:12:57+09:00")

    def test_ariake_no_year_leaves_parsed_timestamp_none(self):
        p = AriakeParser(host_pattern_salt="s")
        block = TestHrBoundaryDetection().make_hr_block(
            "b", "件名", "名無し", "06月08日(月)17時33分50秒", "本文"
        )
        r = p.parse(block).records[0]
        self.assertEqual(r.raw_timestamp, "06月08日(月)17時33分50秒")
        self.assertIsNone(r.parsed_timestamp)
        self.assertTrue(r.provenance["timestamp_year_missing"])

    def test_non_post_hr_segment_is_skipped_silently(self):
        """フォーム・フッター等、必須フィールドが揃わないhr区切りの
        セグメントは警告なしで無視される。"""
        boilerplate = "<hr>ここはフォームなどの非投稿部分です<hr>"
        block = TestHrBoundaryDetection().make_hr_block(
            "b", "件名", "名無し", "2026/08/01(土)16時24分32秒", "本文"
        )
        result = RemixParser(host_pattern_salt="s").parse(boilerplate + block)
        self.assertEqual(len(result.records), 1)
        self.assertEqual(len(result.warnings), 0)

    def test_body_pattern_hits_sanitized(self):
        p = RemixParser(host_pattern_salt="s")
        block = TestHrBoundaryDetection().make_hr_block(
            "b", "件名", "名無し", "2026/08/01(土)16時24分32秒",
            "xxx.ne.jpから来た192.168.1.1の奴",
        )
        r = p.parse(block).records[0]
        self.assertEqual(r.provenance["body_pattern_hits"], 2)
        self.assertNotIn("ne.jp", r.body_sanitized)
        self.assertIn("ne.jp", r.body_raw)

    def test_to_dict_json_serializable(self):
        import json

        p = RemixParser(host_pattern_salt="s")
        block = TestHrBoundaryDetection().make_hr_block(
            "b", "件名", "名無し", "2026/08/01(土)16時24分32秒", "本文"
        )
        r = p.parse(block).records[0]
        json.dumps(r.to_dict(), ensure_ascii=False)


class TestRegistry(unittest.TestCase):
    def test_duplicate_namespace_rejected(self):
        r = ParserRegistry()
        r.register(Kscrr1p9Parser())
        with self.assertRaises(NamespaceConflictError):
            r.register(Kscrr1p9Parser())

    def test_user_override_detection_false_rejected(self):
        r = ParserRegistry()
        r.register(Kscrr1p9Parser())
        with self.assertRaises(ValueError):
            detect_and_select(
                r, "対応不能なテキスト",
                user_override="legacy-bbs-toolkit.parser.kscrr1p9",
            )

    def test_selection(self):
        r = ParserRegistry()
        r.register(Kscrr1p9Parser())
        ns, prov = detect_and_select(r, SAMPLE_1)
        self.assertEqual(ns, "legacy-bbs-toolkit.parser.kscrr1p9")
        self.assertEqual(prov["selection_path"], "selection")

    def test_selection_with_both_parsers_registered(self):
        """zanteiとksphp_plusを両方登録しても、それぞれのマーカーで
        正しく排他的に選択される（誤検出しないことの回帰確認）。"""
        r = ParserRegistry()
        r.register(Kscrr1p9Parser())
        r.register(KsphpPlusParser())
        ns_kscrr1p9, _ = detect_and_select(r, SAMPLE_1)
        self.assertEqual(ns_kscrr1p9, "legacy-bbs-toolkit.parser.kscrr1p9")
        ns_ksphp, _ = detect_and_select(r, KSPHP_SAMPLE_1)
        self.assertEqual(ns_ksphp, "legacy-bbs-toolkit.parser.ksphp_plus")

    def test_selection_with_all_six_parsers_registered(self):
        """6パーサー全部登録しても、各サンプルが自分自身のnamespaceに
        排他的に選択される（hr_boundary系追加時の全体回帰確認）。"""
        r = ParserRegistry()
        for parser in (
            Kscrr1p9Parser(),
            KsphpPlusParser(),
            RemixParser(),
            MizuiroParser(),
            MeisoParser(),
            AriakeParser(),
        ):
            r.register(parser)
        helper = TestHrBoundaryDetection()
        cases = {
            SAMPLE_1: "legacy-bbs-toolkit.parser.kscrr1p9",
            KSPHP_SAMPLE_1: "legacy-bbs-toolkit.parser.ksphp_plus",
            helper.make_hr_block(
                "b", "件名", "名無し", "2026/08/01(土)16時24分32秒", "本文"
            ): "legacy-bbs-toolkit.parser.remix",
            helper.make_hr_block(
                "b", "件名", "名無し", "2023年08月01日(火)11時24分30秒", "本文"
            ): "legacy-bbs-toolkit.parser.mizuiro",
            helper.make_hr_block(
                "strong", "(無題)", "名無し", "2025年10月01日(水)23時12分57秒", "本文"
            ): "legacy-bbs-toolkit.parser.meiso",
            helper.make_hr_block(
                "b", "件名", "名無し", "06月08日(月)17時33分50秒", "本文"
            ): "legacy-bbs-toolkit.parser.ariake",
        }
        for text, expected_ns in cases.items():
            ns, _ = detect_and_select(r, text)
            self.assertEqual(ns, expected_ns)


if __name__ == "__main__":
    unittest.main()
