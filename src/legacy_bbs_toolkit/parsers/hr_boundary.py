"""
legacy-bbs-toolkit: hr境界系（REMIX/みずいろ/メイソ/有明）共通エンジン

対象: zantei20070218/ksphp-plus系のような投稿番号マーカー（<!-- N -->や
<div id="m...">）を持たず、`<hr>`のみを投稿の区切りとして使う一群のCGI
実装（くずはすくりぷと系の別亜種、あるいはMINIBBS系列の独立実装）。

実データ照合で確認した共通構造:
    <hr><font...><TAG>{title}</TAG></font>　投稿者：(<font...>)?<TAG>{author}</TAG>(</font>)?
    <font size="-1">　投稿日：{timestamp}...</font><p>
    <blockquote><pre>{body}</pre>...</blockquote>
    <hr>...(次の投稿)

TAG（<b>または<strong>）・タイムスタンプ書式（スラッシュ年あり/漢字年あり/
漢字年なし）がサイトごとに異なるため、共通のブロック分割・抽出ロジックを
このモジュールに集約し、サイトごとの差分だけをサブクラスでパラメータ化する
（2026-08-01、ユーザー指示「できる限り共通化」）。

投稿番号マーカーが無いため、post_idはファイル内の抽出成功順の連番
（1始まり、文字列）を合成する（2026-08-01決定：タイムスタンプ代用は
重複・ズレのリスクがあるため不採用）。この合成方式は各系統で共通。

ブロック分割は`<hr>`区切りの単純な方式（dauso0026/getlog.cgiの実装
「REMIXのログで、<hr>の後ろに改行があったりなかったりする対策」を参考に、
`<hr>`直後の改行有無を問わず分割する）。ページ先頭のフォーム・フッター等
`<hr>`で区切られた非投稿セグメントは、必須フィールド（投稿者・投稿日・
本文）が揃わないため自然に除外される（黙ってスキップ、warningsには
計上しない——ページ構造上の定型部分であり構造異常ではないため）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Pattern

from legacy_bbs_toolkit import host_pattern_detector, ng_check_bridge
from legacy_bbs_toolkit.parsers.kscrr1p9 import (
    DEFAULT_ASSUMED_TZ_OFFSET,
    IntermediateRecord,
    ParseResult,
    salted_sha256,
)

_HR_RE = re.compile(r"<hr\s*/?>", re.IGNORECASE)
_MAILTO_RE = re.compile(r'href="mailto:([^"]+)"', re.IGNORECASE)
_AUTHOR_LINK_RE = re.compile(r"<a[^>]*>(.*?)</a>", re.DOTALL | re.IGNORECASE)

_ENVADDR_RE = re.compile(
    r"(?:\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|[A-Za-z0-9.-]+\.[A-Za-z]{2,})"
)
_ENVUA_RE = re.compile(r"Mozilla|MSIE|compatible", re.IGNORECASE)


@dataclass
class TimestampFormat:
    """タイムスタンプ書式の差分をパラメータ化する。

    pattern: raw_timestampの抽出用正規表現。has_year=Trueならgroups()が
    (year, month, day, hour, minute, second)、Falseなら
    (month, day, hour, minute, second) の順。
    """

    pattern: Pattern[str]
    has_year: bool


# スラッシュ・年あり（REMIX: 2026/08/01(土)16時24分32秒）
TS_SLASH_WITH_YEAR = TimestampFormat(
    pattern=re.compile(
        r"(\d{4})/(\d{1,2})/(\d{1,2})\([月火水木金土日]\)"
        r"(\d{1,2})時(\d{1,2})分(\d{1,2})秒"
    ),
    has_year=True,
)

# 漢字・年あり（みずいろ/ダーザイン/メイソ: 2023年08月01日(火)11時24分30秒）
TS_KANJI_WITH_YEAR = TimestampFormat(
    pattern=re.compile(
        r"(\d{4})年(\d{1,2})月(\d{1,2})日\([月火水木金土日]\)"
        r"(\d{1,2})時(\d{1,2})分(\d{1,2})秒"
    ),
    has_year=True,
)

# 漢字・年なし（有明/MINIBBS: 06月08日(月)17時33分50秒）
# 年ありパターンの部分文字列として誤検出しないよう、月の先頭が
# 数字や「年」の直後（＝年ありパターンの一部）でないことを確認する。
# 単純に「直前がNNNN年」だけを否定後読みすると、正規表現エンジンが
# 月の1桁目をスキップして2桁目から再試行した際に検出をすり抜ける
# （実データ202308.htmlで確認・修正済み）ため、「直前が数字」「直前が
# 年」の両方を個別に否定する。
TS_KANJI_NO_YEAR = TimestampFormat(
    pattern=re.compile(
        r"(?<!\d)(?<!年)(\d{1,2})月(\d{1,2})日\([月火水木金土日]\)"
        r"(\d{1,2})時(\d{1,2})分(\d{1,2})秒"
    ),
    has_year=False,
)


class HrBoundaryParserBase:
    """`<hr>`境界系サイト共通のParser基底クラス。

    サブクラスはnamespace / tag / timestamp_format の3つを指定するだけで
    良い（抽出ロジック自体は完全に共通）。
    """

    namespace: str = ""
    tag: str = "b"  # "b" または "strong"
    timestamp_format: TimestampFormat = TS_KANJI_WITH_YEAR

    def __init__(
        self,
        host_pattern_salt: Optional[str] = None,
        ng_check_php_path: Optional[str] = None,
        ng_check_hashes_path: str = "hashes-txt.gz",
    ):
        """引数の意味はKscrr1p9Parser/KsphpPlusParserと同一。"""
        self._salt = (
            host_pattern_salt
            if host_pattern_salt is not None
            else host_pattern_detector.generate_runtime_salt()
        )
        self._ng_check_php_path = ng_check_php_path
        self._ng_check_hashes_path = ng_check_hashes_path

        # 注意: タグ名（<b>/<strong>）自体は大文字小文字を区別する
        # （re.IGNORECASEを付けない）。zantei系は同じ位置に大文字<B>を
        # 使うため、ここを大文字小文字区別なしにするとzanteiの実データを
        # 誤検出してしまう（実データ回帰テストで確認・修正済み）。
        # <font>ラッパー自体の大文字小文字は実データ上ゆれが無いため
        # 区別せず許容する。
        tag = re.escape(self.tag)
        self._title_re = re.compile(
            rf"<font[^>]*>\s*<{tag}[^>]*>(.*?)</{tag}>\s*</font>",
            re.DOTALL,
        )
        self._author_re = re.compile(
            rf"投稿者[：:]\s*(?:<font[^>]*>)?\s*<{tag}[^>]*>(.*?)</{tag}>",
            re.DOTALL,
        )
        self._body_re = re.compile(
            r"<blockquote[^>]*>\s*<pre[^>]*>(.*)</pre>",
            re.DOTALL | re.IGNORECASE,
        )

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------
    def detect(self, raw_text: str) -> bool:
        """Detection契約：対応可否を真偽値で返す。

        判定基準：`投稿者：<TAG>`（このサブクラスのタグ）と、このサブクラス
        のタイムスタンプ書式の両方が少なくとも1件ずつ存在すること。
        タグ・日付書式の組み合わせで系統ごとに排他的に判定される
        （TS_KANJI_NO_YEARは否定後読みでTS_KANJI_WITH_YEARとの誤検出を防止
        済み。tag違い＝<b>と<strong>は文字通り別集合なので排他）。
        """
        return bool(self._author_re.search(raw_text)) and bool(
            self.timestamp_format.pattern.search(raw_text)
        )

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------
    def parse(self, raw_text: str) -> ParseResult:
        result = ParseResult()
        seq = 0
        for segment in self._iter_segments(raw_text):
            record = self._extract_message(segment, seq + 1)
            if record is None:
                continue
            seq += 1
            result.records.append(record)
        return result

    def _iter_segments(self, raw_text: str):
        """`<hr>`区切りでセグメントに分割する。

        各セグメントが実際に1投稿として抽出可能かどうかは
        _extract_message側の必須フィールドチェックに委ねる（ページ先頭の
        投稿フォームやフッター等、非投稿セグメントはここでは除外しない）。
        """
        hrs = list(_HR_RE.finditer(raw_text))
        for i in range(len(hrs)):
            start = hrs[i].end()
            end = hrs[i + 1].start() if i + 1 < len(hrs) else len(raw_text)
            yield raw_text[start:end]

    def _extract_message(
        self, segment: str, next_seq: int
    ) -> Optional[IntermediateRecord]:
        """1セグメントからIR 1件を抽出する。投稿者・投稿日・本文のいずれか
        が欠けている場合はNone（非投稿セグメントとして黙ってスキップ）。
        """
        author_match = self._author_re.search(segment)
        ts_match = self.timestamp_format.pattern.search(segment)
        body_match = self._body_re.search(segment)
        if author_match is None or ts_match is None or body_match is None:
            return None

        post_id = str(next_seq)

        title_match = self._title_re.search(segment)
        title_raw = title_match.group(1).strip() if title_match else ""

        author_field = author_match.group(1)
        link_match = _AUTHOR_LINK_RE.search(author_field)
        author_raw = (link_match.group(1) if link_match else author_field).strip()

        raw_timestamp = ts_match.group(0)
        body_raw = body_match.group(1)

        author_pattern_hits = 0
        if author_raw:
            _, author_pattern_records = host_pattern_detector.sanitize(
                author_raw, salt=self._salt
            )
            author_pattern_hits = len(author_pattern_records)

        title_pattern_hits = 0
        if title_raw:
            _, title_pattern_records = host_pattern_detector.sanitize(
                title_raw, salt=self._salt
            )
            title_pattern_hits = len(title_pattern_records)

        body_sanitized = None
        body_pattern_hits = 0
        ng_check_ran = False
        ng_detected = False
        provenance_ng_match_count = 0
        if body_raw:
            body_sanitized, body_pattern_records = host_pattern_detector.sanitize(
                body_raw, salt=self._salt
            )
            body_pattern_hits = len(body_pattern_records)

            if self._ng_check_php_path:
                try:
                    ng_result = ng_check_bridge.sanitize_with_ng_check(
                        body_sanitized,
                        php_path=self._ng_check_php_path,
                        hashes_path=self._ng_check_hashes_path,
                    )
                    body_sanitized = ng_result.sanitized_text
                    ng_check_ran = True
                    ng_detected = ng_result.ng_detected
                    if ng_result.match_count > 0:
                        provenance_ng_match_count = ng_result.match_count
                except ng_check_bridge.NgCheckBridgeError:
                    pass

        provenance: dict = {
            "selection_path": "selection",
            "post_id_synthetic": "sequential",
        }
        parsed_timestamp = self._parse_timestamp(ts_match)
        if self.timestamp_format.has_year:
            provenance["assumed_timezone_offset"] = DEFAULT_ASSUMED_TZ_OFFSET
        else:
            # 年情報が原文に無いため、ISO 8601化は行わずProvenanceに
            # その旨を記録する（Timestamp Handling契約：原文はraw_timestamp
            # にそのまま保持、改変・推測補完はしない）。
            provenance["timestamp_year_missing"] = True

        host_meta_detected = False
        ua_meta_detected = False
        host_meta_sanitized = None
        ua_meta_sanitized = None
        env_addr_m = _ENVADDR_RE.search(segment)
        if env_addr_m and "envlist" in segment.lower():
            host_meta_detected = True
            host_meta_sanitized = salted_sha256(env_addr_m.group(0), self._salt)
        if _ENVUA_RE.search(segment) and "envlist" in segment.lower():
            ua_meta_detected = True
            ua_meta_sanitized = salted_sha256(segment, self._salt)

        author_email_detected = bool(_MAILTO_RE.search(author_field))
        author_email_sanitized = None
        if author_email_detected:
            email_m = _MAILTO_RE.search(author_field)
            author_email_sanitized = salted_sha256(email_m.group(1), self._salt)

        if host_meta_detected:
            provenance["host_meta_action"] = "anonymized"
        if ua_meta_detected:
            provenance["ua_meta_action"] = "anonymized"
        if author_email_detected:
            provenance["author_email_action"] = "anonymized"
        if author_pattern_hits:
            provenance["author_pattern_hits"] = author_pattern_hits
        if title_pattern_hits:
            provenance["title_pattern_hits"] = title_pattern_hits
        if body_pattern_hits:
            provenance["body_pattern_hits"] = body_pattern_hits
            provenance["body_pattern_action"] = "anonymized"
        provenance["ng_check_ran"] = ng_check_ran
        if ng_check_ran:
            provenance["ng_check_ng_detected"] = ng_detected
            if provenance_ng_match_count:
                provenance["ng_check_match_count"] = provenance_ng_match_count

        return IntermediateRecord(
            post_id=post_id,
            raw_timestamp=raw_timestamp,
            author_raw=author_raw,
            title_raw=title_raw,
            body_raw=body_raw,
            parser_namespace=self.namespace,
            body_sanitized=body_sanitized,
            parsed_timestamp=parsed_timestamp,
            author_email_detected=author_email_detected,
            author_email_sanitized=author_email_sanitized,
            host_meta_detected=host_meta_detected,
            host_meta_sanitized=host_meta_sanitized,
            ua_meta_detected=ua_meta_detected,
            ua_meta_sanitized=ua_meta_sanitized,
            provenance=provenance,
        )

    def _parse_timestamp(self, ts_match: re.Match) -> Optional[str]:
        if not self.timestamp_format.has_year:
            # 年情報が無いためISO 8601化不能（推測補完はしない）。
            return None
        year, month, day, hour, minute, second = ts_match.groups()
        return (
            f"{int(year):04d}-{int(month):02d}-{int(day):02d}T"
            f"{int(hour):02d}:{int(minute):02d}:{int(second):02d}"
            f"{DEFAULT_ASSUMED_TZ_OFFSET}"
        )


class RemixParser(HrBoundaryParserBase):
    """「リミックス」系統（strangeworld.ne.jp/remix/bbs.cgi）向けParser。

    実データ照合（202608.html）: マーカーなし・`<hr>`境界・<b>タグ・
    スラッシュ日付（YYYY/MM/DD(曜)HH時MM分SS秒、年あり）。
    """

    namespace = "legacy-bbs-toolkit.parser.remix"
    tag = "b"
    timestamp_format = TS_SLASH_WITH_YEAR


class MizuiroParser(HrBoundaryParserBase):
    """「みずいろ」系統向けParser（旧称ダーザイン、ユーザー確認により統一）。

    対象: あやしいわーるど＠じょしあな + Team MIZUIRO ＝ ダーザイン系列
    （202308.html「ダーザイン2012」、dauso0051、bbs.zip「チームみずいろ」）。
    実データ照合: マーカーなし・`<hr>`境界・<b>タグ・漢字日付
    （YYYY年MM月DD日(曜)HH時MM分SS秒、年あり）。旧バージョン
    （じょしあな+Team MIZUIRO v1.3以前）は年なしの日付だったことが
    conv.zip（データコンバータ）のソースから判明しているが、現存データは
    未確認のため今のところ年ありのみ対応。
    """

    namespace = "legacy-bbs-toolkit.parser.mizuiro"
    tag = "b"
    timestamp_format = TS_KANJI_WITH_YEAR


class MeisoParser(HrBoundaryParserBase):
    """「メイソ」系統向けParser（あやしいわーるどメイソ掲示板）。

    実データ照合（202510.html）: マーカーなし・`<hr>`境界・<strong>タグ
    （みずいろ系の<b>とは異なる）・漢字日付（年あり）・UTF-8エンコード。
    """

    namespace = "legacy-bbs-toolkit.parser.meiso"
    tag = "strong"
    timestamp_format = TS_KANJI_WITH_YEAR


class AriakeParser(HrBoundaryParserBase):
    """「有明」系統向けParser（あやしいわーるど＠有明、jca.apc.org、
    MINIBBS系列——くずはすくりぷと系ではなく独立した別実装）。

    実データ照合（ariake.zip）: マーカーなし・`<hr>`境界・<b>タグ・
    漢字日付だが**年情報が無い**（MM月DD日(曜)HH時MM分SS秒のみ）。
    parsed_timestampはISO 8601化できないためNoneとなり、
    provenance.timestamp_year_missing=Trueで明示する。
    """

    namespace = "legacy-bbs-toolkit.parser.ariake"
    tag = "b"
    timestamp_format = TS_KANJI_NO_YEAR
