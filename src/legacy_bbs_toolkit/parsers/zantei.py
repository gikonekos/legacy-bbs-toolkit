"""
legacy-bbs-toolkit: zantei20070218 Parser

Namespace: legacy-bbs-toolkit.parser.zantei
Derived from: spec/parser-api.md (Detection / Provenance / Timestamp Handling /
Parser Plugin Namespace), spec/principles.md (Archive First)

抽出ロジックは実データ2ファイル（2002年、計12,015投稿）の構造をタグ構造
のみで確認した上で実装・検証済み。他の年代・他のログ生成バージョンでの
構造差異は未検証（TODO）。
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from typing import Optional

from legacy_bbs_toolkit import host_pattern_detector, ng_check_bridge


PARSER_NAMESPACE = "legacy-bbs-toolkit.parser.zantei"

# メッセージブロックの開始・終了マーカー
# zbbs.cgi の $tmpl_msg テンプレートより:
#   <!-- $postid -->  ... ブロック開始（$postid は投稿番号）
#   <!-- -->          ... ブロック終了
_BLOCK_START_RE = re.compile(r"<!--\s*(\d+)\s*-->")
_BLOCK_END_RE = re.compile(r"<!--\s*-->")

# 投稿日時の書式（getnowdate関数より）:
#   YYYY/MM/DD(曜)HH時MM分SS秒
_TIMESTAMP_RE = re.compile(
    r"(\d{4})/(\d{1,2})/(\d{1,2})\([月火水木金土日]\)"
    r"(\d{1,2})時(\d{1,2})分(\d{1,2})秒"
)

# メッセージブロック内の各フィールド抽出用正規表現。
# 実データ（20020105.html）の構造をタグ構造のみで確認して設計:
#   <FONT ...><B>(題名 or ＞返信マーカー)</B></FONT>
#   　投稿者：<B>(<A ...>)?(投稿者名)(</A>)?</B>
#   　<FONT ...>投稿日：(タイムスタンプ)</FONT>
#   <BLOCKQUOTE><PRE>(本文、AA・タグ含む原文)</PRE></BLOCKQUOTE>
_TITLE_RE = re.compile(r"<FONT[^>]*>\s*<B>(.*?)</B>\s*</FONT>", re.DOTALL)
_AUTHOR_RE = re.compile(r"投稿者[：:]\s*<B>(.*?)</B>", re.DOTALL)
# 本文抽出は貪欲マッチとする。テンプレート構造上、ブロック内の最後の
# </PRE>が本文の正しい終端であり、投稿者が本文中に文字通り「</PRE>」と
# 書き込んでいた場合（実データで文字通りの「<PRE>」の書き込みを1件確認、
# post_id 8280）でも本文が途中で切れないようにするため。
_BODY_RE = re.compile(r"<PRE[^>]*>(.*)</PRE>", re.DOTALL)
# 投稿者名が<A>タグでラップされている場合(mailtoまたはURL)に、
# 表示名部分だけを取り出すための補助パターン
_AUTHOR_LINK_RE = re.compile(r"<A[^>]*>(.*?)</A>", re.DOTALL | re.IGNORECASE)
# $envlist（<!--$envaddr$envbr$envua-->）の検出用。
# ブロック内のHTMLコメントをすべて検出し、空でも数字のみでもないもの
# をenvlist候補として個別に解析する。
_COMMENT_RE = re.compile(r"<!--(.*?)-->", re.DOTALL)

# 投稿者欄に稀に埋め込まれるmailtoリンク（実メールアドレス）の検出用。
# 実データ（20020105.html）で8,191ブロック中10件の出現を構造確認済み
# （中身は未閲覧・件数のみ確認）。
_MAILTO_RE = re.compile(r'href="mailto:[^"]*"', re.IGNORECASE)

DEFAULT_ASSUMED_TZ_OFFSET = "+09:00"  # Asia/Tokyo（Timestamp Handling契約の既定値）


@dataclass
class ParserOverrideRejected(Exception):
    """User Overrideが指定されたが、Detectionがfalseを返した場合に送出する
    （parser-api.md User Override契約3）。"""

    reason: str


@dataclass
class IntermediateRecord:
    """spec/intermediate.schema.json に対応するIR 1件分。"""

    post_id: str
    raw_timestamp: str
    author_raw: str
    title_raw: str
    body_raw: str
    parser_namespace: str = PARSER_NAMESPACE
    parsed_timestamp: Optional[str] = None
    body_sanitized: Optional[str] = None
    author_email_detected: bool = False
    author_email_sanitized: Optional[str] = None
    host_meta_detected: bool = False
    host_meta_sanitized: Optional[str] = None
    ua_meta_detected: bool = False
    ua_meta_sanitized: Optional[str] = None
    provenance: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """intermediate.schema.json準拠のdict（JSON直列化可能）を返す。"""
        return asdict(self)


@dataclass
class ParseResult:
    """parse()の結果。recordsに加え、パース中に検出した構造異常
    （終了マーカー欠落・post_id重複等）をwarningsとして保持する。

    後方互換のため、イテレート・len()はrecordsに委譲する。
    """

    records: list[IntermediateRecord] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def __iter__(self):
        return iter(self.records)

    def __len__(self) -> int:
        return len(self.records)


class ZanteiParser:
    """zantei20070218形式（あやしいわーるど＠暫定系列）向けParser。"""

    namespace = PARSER_NAMESPACE

    def __init__(
        self,
        host_pattern_salt: Optional[str] = None,
        ng_check_php_path: Optional[str] = None,
        ng_check_hashes_path: str = "hashes-txt.gz",
    ):
        """host_pattern_salt: body_raw等に含まれるホスト情報らしきパターン
        （host_pattern_detector）、およびhost_meta/ua_meta/author_email
        （salted_sha256）をハッシュ化する際のソルト。

        未指定の場合は、動作時（このParserインスタンス生成時）の年月日
        時分秒（generate_runtime_salt()）を自動的に使用する。完全一致
        するハッシュ値による複合を避けるため、ハッシュ自体も先頭8文字
        に切り詰める（salted_sha256, host_pattern_detector._salted_sha256
        いずれも同様の方針）。

        ng_check_php_path: [[ng-check]]（ng-check.php）を呼び出すための
        phpコマンドパス。Noneの場合はng-check連携を行わず、
        host_pattern_detectorのみでbody_sanitizedを生成する
        （疎結合：ng-check未導入環境でもParser自体は動作する）。
        """
        self._salt = (
            host_pattern_salt
            if host_pattern_salt is not None
            else host_pattern_detector.generate_runtime_salt()
        )
        self._ng_check_php_path = ng_check_php_path
        self._ng_check_hashes_path = ng_check_hashes_path

    def detect(self, raw_text: str) -> bool:
        """Detection契約：対応可否を真偽値で返す。

        判定基準（案）：ブロック開始マーカーと終了マーカーが
        少なくとも1組存在すること。
        """
        return bool(_BLOCK_START_RE.search(raw_text)) and bool(
            _BLOCK_END_RE.search(raw_text)
        )

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
        """ブロック開始〜終了マーカーの間のテキストを1件ずつ切り出す。

        終了マーカーの探索範囲は「次のブロック開始マーカーの手前まで」に
        限定する。中間ブロックの終了マーカーが欠落していた場合に、次の
        ブロックを丸ごと呑み込んでしまう誤りを防ぐため。終了マーカーの
        無いブロックはスキップし、warningsに記録する（黙って捨てない）。
        """
        starts = list(_BLOCK_START_RE.finditer(raw_text))
        for i, start_match in enumerate(starts):
            search_limit = (
                starts[i + 1].start() if i + 1 < len(starts) else len(raw_text)
            )
            end_match = _BLOCK_END_RE.search(
                raw_text, start_match.end(), search_limit
            )
            if end_match is None:
                warnings.append(
                    f"block post_id={start_match.group(1)} has no end marker "
                    "before the next block (or EOF); block skipped"
                )
                continue
            yield {
                "post_id": start_match.group(1),
                "block_text": raw_text[start_match.end() : end_match.start()],
            }

    def _extract_message(self, block: dict) -> Optional[IntermediateRecord]:
        """1ブロック分のテキストからIR 1件を抽出する。"""
        block_text = block["block_text"]
        post_id = block["post_id"]

        raw_timestamp_match = _TIMESTAMP_RE.search(block_text)
        raw_timestamp = raw_timestamp_match.group(0) if raw_timestamp_match else ""

        title_match = _TITLE_RE.search(block_text)
        title_raw = title_match.group(1).strip() if title_match else ""

        author_raw = ""
        author_match = _AUTHOR_RE.search(block_text)
        if author_match:
            author_field = author_match.group(1)
            # <A href="mailto:...">名前</A> や <A href="http://...">名前</A>
            # の形式であれば、表示名部分だけをauthor_rawとして扱う。
            # リンク先(メールアドレス等)自体はauthor_email_detected側で扱う。
            link_match = _AUTHOR_LINK_RE.search(author_field)
            author_raw = (link_match.group(1) if link_match else author_field).strip()

        body_match = _BODY_RE.search(block_text)
        body_raw = body_match.group(1) if body_match else ""

        # author_raw / title_raw に対してもhost_pattern_detectorを適用する。
        # 投稿者名欄や返信マーカー欄にも、他の投稿者のホスト情報が
        # 直接書き込まれるケースがあるため（設計上の決定、principles.md参照）。
        # 注意: author_raw / title_raw の「原文」は body_raw と同様に
        # IRの _raw フィールドとして改変禁止で保持しつつ、
        # サニタイズ後は body_sanitized に相当する別フィールドではなく
        # Provenanceへの記録（件数のみ）にとどめる。
        # フィールド数の爆発を避け、author_raw/title_rawはそれ自体が
        # 「サニタイズ対象である」という仕様の明示にとどめる
        # （将来 author_sanitized 追加の可能性はある）。
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

        # 本文中に地の文として紛れ込むホスト情報らしきパターン
        # （$envlistのような構造化フィールドとは別経路）をまず検出・匿名化
        # し、続けて[[ng-check]]（設定されていれば）でNG語のサニタイズを
        # 適用する。ng-check未設定の環境ではhost_pattern_detectorの結果
        # のみをbody_sanitizedとする（疎結合：どちらか一方が欠けても動作）。
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
            # （Timestamp Handling契約2）
            provenance["assumed_timezone_offset"] = DEFAULT_ASSUMED_TZ_OFFSET

        host_meta_detected = False
        ua_meta_detected = False
        host_meta_sanitized = None
        ua_meta_sanitized = None
        # $envlist の書式: <!--$envaddr$envbr$envua-->
        # $envaddr = $phost（zbbs.cgi、env addr部分）
        # $envua   = $agent（HTTP_USER_AGENT）
        # 実データ2ファイル計12,015件で $envlist 出現なし（非公開ログに
        # 残存している可能性は排除できない）。
        # envaddrはIPv4またはホスト名、envuaはUser-Agent文字列と想定。
        _ENVADDR_RE = re.compile(
            r"(?:\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|[A-Za-z0-9.-]+\.[A-Za-z]{2,})"
        )
        _ENVUA_RE = re.compile(r"Mozilla|MSIE|compatible", re.IGNORECASE)

        for comment_match in _COMMENT_RE.finditer(block_text):
            comment_content = comment_match.group(1).strip()
            if comment_content == "" or comment_content.isdigit():
                continue
            addr_m = _ENVADDR_RE.search(comment_content)
            if addr_m:
                host_meta_detected = True
                host_meta_sanitized = salted_sha256(addr_m.group(0), self._salt)
            if _ENVUA_RE.search(comment_content):
                ua_meta_detected = True
                ua_meta_sanitized = salted_sha256(comment_content, self._salt)

        author_email_detected = bool(_MAILTO_RE.search(block_text))
        author_email_sanitized = None
        if author_email_detected:
            email_m = re.search(r'href="mailto:([^"]+)"', block_text, re.IGNORECASE)
            if email_m:
                author_email_sanitized = salted_sha256(email_m.group(1), self._salt)

        parsed_timestamp = None
        provenance: dict = {"selection_path": "selection"}
        if raw_timestamp:
            parsed_timestamp = self._parse_timestamp(raw_timestamp)
            provenance["assumed_timezone_offset"] = DEFAULT_ASSUMED_TZ_OFFSET

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
        """YYYY/MM/DD(曜)HH時MM分SS秒 形式をISO 8601へ変換する。"""
        m = _TIMESTAMP_RE.search(raw_timestamp)
        if not m:
            return None
        year, month, day, hour, minute, second = m.groups()
        return (
            f"{int(year):04d}-{int(month):02d}-{int(day):02d}T"
            f"{int(hour):02d}:{int(minute):02d}:{int(second):02d}"
            f"{DEFAULT_ASSUMED_TZ_OFFSET}"
        )


def salted_sha256(value: str, salt: str) -> str:
    """host_meta / ua_meta / author_email の匿名化に使うソルト付きSHA-256
    ハッシュ。

    saltは通常generate_runtime_salt()（実行時刻ベース）を使う想定。
    完全なハッシュ値同士の一致による複合を避けるため、先頭8文字のみを
    保持する（host_pattern_detector._salted_sha256と同じ方針）。
    """
    return hashlib.sha256((salt + value).encode("utf-8")).hexdigest()[:8]
