"""
legacy-bbs-toolkit: ksphp-plus Parser

Namespace: legacy-bbs-toolkit.parser.ksphp_plus
Derived from: spec/parser-api.md (Detection / Provenance / Timestamp Handling /
Parser Plugin Namespace), spec/principles.md (Archive First)

対象: kuzuha-scriptPHP+ (ksphp-plus) 系列の掲示板出力（sub/template.html
"message"ブロックのテンプレート構造）。zantei20070218系とは別のCGI/PHP
実装であり、タグ構造が異なるため独立したParserとして実装する。

抽出ロジックは実データ1ファイル（2026年、2189投稿、zantei系として検出済み
＝ksphp-plus系ではない）ではなく、テンプレートソース（ksphp-rc8提供分の
sub/template.html, bbs.php）の構造確認のみに基づく。実データでの検出確認
（20260720.html）はタグ骨格のみで内容は未閲覧。抽出ロジック自体はテンプレート
ソースから設計したもので、実データでの精密な抽出検証はTODO。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from legacy_bbs_toolkit import host_pattern_detector, ng_check_bridge
from legacy_bbs_toolkit.parsers.kscrr1p9 import (
    DEFAULT_ASSUMED_TZ_OFFSET,
    IntermediateRecord,
    ParseResult,
    salted_sha256,
)


PARSER_NAMESPACE = "legacy-bbs-toolkit.parser.ksphp_plus"

# メッセージブロックの開始・終了マーカー
# sub/template.html "message" テンプレートより:
#   <div class="m" id="m{POSTID}"> ... ブロック開始（POSTIDは投稿番号）
#   対応する終了 </div>（envlistブロックを含む場合もその内側）
_BLOCK_START_RE = re.compile(r'<div class="m" id="m(\d+)">')

# 投稿日時の書式（bbs.php getdatestr()より）:
#   YYYY/MM/DD(曜)HH:MM:SS  ※既定フォーマット "Y/m/d(-) H:i:s"
#   曜日は言語ファイル（日本語版）で「日月火水木金土」の1文字
_TIMESTAMP_RE = re.compile(
    r"(\d{4})/(\d{1,2})/(\d{1,2})\([日月火水木金土]\)"
    r"(\d{1,2}):(\d{1,2}):(\d{1,2})"
)

# 各フィールド抽出用正規表現（sub/template.html "message"ブロックより）:
#   <span class="ms">{TITLE}</span>
#   <span class="mun">{USER}</span>  （USERはmailtoリンクでラップされる場合あり）
#   <span class="md">{DATE_LABEL} {WDATE}<a id="a{POSTID}">...
#   <pre class="msgnormal">{MSG}</pre>
#   <div class="env">{ENVADDR}{ENVBR}{ENVUA}</div>  （IPPRINT/UAPRINT有効時のみ出現）
_TITLE_RE = re.compile(r'<span class="ms">(.*?)</span>', re.DOTALL)
_USER_RE = re.compile(r'<span class="mun">(.*?)</span>', re.DOTALL)
_USER_LINK_RE = re.compile(r"<A[^>]*>(.*?)</A>", re.DOTALL | re.IGNORECASE)
_DATE_RE = re.compile(r'<span class="md">(.*?)<a id="a\d+"', re.DOTALL)
_BODY_RE = re.compile(r'<pre class="msgnormal">(.*?)</pre>', re.DOTALL)
_ENV_RE = re.compile(r'<div class="env">(.*?)</div>', re.DOTALL)

# USER欄に稀に埋め込まれるmailtoリンク（実メールアドレス）の検出用。
# bbs.php: $message['MAIL'] があれば USER を <a href="mailto:...">でラップする。
_MAILTO_RE = re.compile(r'href="mailto:([^"]+)"', re.IGNORECASE)

# envlist内のENVADDR（IPv4またはホスト名）・ENVUA（User-Agent文字列）判定。
# kscrr1p9.pyの_ENVADDR_RE/_ENVUA_REと同方針（構造は異なるが判定基準は共通化）。
_ENVADDR_RE = re.compile(
    r"(?:\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|[A-Za-z0-9.-]+\.[A-Za-z]{2,})"
)
_ENVUA_RE = re.compile(r"Mozilla|MSIE|compatible", re.IGNORECASE)


class KsphpPlusParser:
    """ksphp-plus（kuzuha-scriptPHP+）系列向けParser。"""

    namespace = PARSER_NAMESPACE

    def __init__(
        self,
        host_pattern_salt: Optional[str] = None,
        ng_check_php_path: Optional[str] = None,
        ng_check_hashes_path: str = "hashes-txt.gz",
    ):
        """引数の意味はKscrr1p9Parserと同一（parsers/kscrr1p9.py参照）。"""
        self._salt = (
            host_pattern_salt
            if host_pattern_salt is not None
            else host_pattern_detector.generate_runtime_salt()
        )
        self._ng_check_php_path = ng_check_php_path
        self._ng_check_hashes_path = ng_check_hashes_path

    def detect(self, raw_text: str) -> bool:
        """Detection契約：対応可否を真偽値で返す。

        判定基準（案）：`<div class="m" id="mNNNN">`ブロック開始マーカーが
        少なくとも1件存在すること。zanteiの `<!-- 数字 -->` マーカーとは
        構造的に排他のため、両者の誤検出（両方detect=trueになる）は想定しない。
        """
        return bool(_BLOCK_START_RE.search(raw_text))

    def parse(self, raw_text: str) -> ParseResult:
        """rawテキストをParseResult（IRのリスト＋構造異常の警告）へ変換する。"""
        result = ParseResult()
        seen_ids: set[str] = set()
        for block in self._iter_blocks(raw_text, result.warnings):
            record = self._extract_message(block)
            if record is None:
                continue
            if record.post_id in seen_ids:
                result.warnings.append(
                    f"duplicate post_id detected: {record.post_id} "
                    "(both blocks are kept as-is; Archive First)"
                )
            seen_ids.add(record.post_id)
            result.records.append(record)
        return result

    def _iter_blocks(self, raw_text: str, warnings: list[str]):
        r"""`<div class="m" id="mNNNN">`〜次のブロック開始（またはEOF）の
        手前までを1件分のブロックとして切り出す。

        kscrr1p9.pyと同じ方針: divの厳密なネスト解析は行わず、次のブロック
        開始マーカーを境界とする単純な区切りとする。

        誤爆リスク（本文中に地の文で`<div class="m" id="m...">`が書き込まれ
        次ブロックを呑み込む懸念）について: bbs.phpのprocForm()が投稿受付時
        （保存前）にPOST/GET全フィールド（本文・タイトル・投稿者名含む）へ
        Func::html_escape()を一律適用しており、これは値が`^\w+$`（英数字
        のみ）でない限りhtmlspecialchars(..., ENT_QUOTES)を実行する
        （bbs.php html_escape()参照）。そのため通常の投稿経路では本文中の
        `<`/`>`は`&lt;`/`&gt;`にエスケープされ、生の`<div ...>`タグが
        本文に紛れ込むことは構造的にほぼ起こり得ない。

        注意: zantei20070218側もgetformdata()で同様の<→&lt;/>→&gt;
        エスケープを投稿受付時に行っていることをソース確認済み（両系列
        とも入力エスケープの原則は同じ）。ただしzantei側は実データ
        （post_id 8280）で生の<PRE>混入が構造検証済み（kscrr1p9.py参照、
        zantei固有のレガシー機能に起因、対応済み）。ksphp-plus側に
        相当する懸念は今のところ確認されていない。
        極端なエッジケース（エスケープ導入以前の旧データ、DB直接操作等）
        まではksphp-plus側も保証しない。
        """
        starts = list(_BLOCK_START_RE.finditer(raw_text))
        for i, start_match in enumerate(starts):
            block_end = (
                starts[i + 1].start() if i + 1 < len(starts) else len(raw_text)
            )
            yield {
                "post_id": start_match.group(1),
                "block_text": raw_text[start_match.end() : block_end],
            }

    def _extract_message(self, block: dict) -> Optional[IntermediateRecord]:
        """1ブロック分のテキストからIR 1件を抽出する。"""
        block_text = block["block_text"]
        post_id = block["post_id"]

        title_match = _TITLE_RE.search(block_text)
        title_raw = title_match.group(1).strip() if title_match else ""

        author_raw = ""
        author_email_detected = False
        author_email_sanitized = None
        user_match = _USER_RE.search(block_text)
        if user_match:
            user_field = user_match.group(1)
            mailto_match = _MAILTO_RE.search(user_field)
            if mailto_match:
                author_email_detected = True
                author_email_sanitized = salted_sha256(
                    mailto_match.group(1), self._salt
                )
            link_match = _USER_LINK_RE.search(user_field)
            author_raw = (link_match.group(1) if link_match else user_field).strip()

        raw_timestamp = ""
        date_match = _DATE_RE.search(block_text)
        if date_match:
            ts_match = _TIMESTAMP_RE.search(date_match.group(1))
            if ts_match:
                raw_timestamp = ts_match.group(0)

        body_match = _BODY_RE.search(block_text)
        body_raw = body_match.group(1) if body_match else ""

        # author_raw / title_raw へのhost_pattern_detector適用は
        # zanteiと同方針（principles.md参照、フィールド数の爆発回避のため
        # Provenanceへの件数記録にとどめる）。
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

        parsed_timestamp = None
        provenance: dict = {"selection_path": "selection"}
        if raw_timestamp:
            parsed_timestamp = self._parse_timestamp(raw_timestamp)
            # 原文にタイムゾーン表記が無いため、前提タイムゾーンを記録
            # （Timestamp Handling契約2、zanteiと同方針）
            provenance["assumed_timezone_offset"] = DEFAULT_ASSUMED_TZ_OFFSET

        # $envlist（envlistブロック）: <div class="env">{ENVADDR}{ENVBR}{ENVUA}</div>
        # IPPRINT/UAPRINT設定（conf.php）が有効な場合のみ出現する（bbs.php参照）。
        # ENVADDR/ENVUAは区切り文字なく連結されるため、構造的にどちらか一方
        # または両方が空の可能性があり、パターンで個別判定する
        # （zanteiのenvaddr/envuaコメント形式とは構造が異なるため、
        # 判定基準自体は_ENVADDR_RE/_ENVUA_REを流用しつつ独立実装とする）。
        host_meta_detected = False
        ua_meta_detected = False
        host_meta_sanitized = None
        ua_meta_sanitized = None
        env_match = _ENV_RE.search(block_text)
        if env_match:
            env_content = env_match.group(1)
            addr_m = _ENVADDR_RE.search(env_content)
            if addr_m:
                host_meta_detected = True
                host_meta_sanitized = salted_sha256(addr_m.group(0), self._salt)
            if _ENVUA_RE.search(env_content):
                ua_meta_detected = True
                ua_meta_sanitized = salted_sha256(env_content, self._salt)

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
            parser_namespace=PARSER_NAMESPACE,
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

    def _parse_timestamp(self, raw_timestamp: str) -> Optional[str]:
        """YYYY/MM/DD(曜)HH:MM:SS 形式をISO 8601へ変換する。"""
        m = _TIMESTAMP_RE.search(raw_timestamp)
        if not m:
            return None
        year, month, day, hour, minute, second = m.groups()
        return (
            f"{int(year):04d}-{int(month):02d}-{int(day):02d}T"
            f"{int(hour):02d}:{int(minute):02d}:{int(second):02d}"
            f"{DEFAULT_ASSUMED_TZ_OFFSET}"
        )
