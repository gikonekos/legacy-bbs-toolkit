"""
legacy-bbs-toolkit: host_pattern_detector

本文（body_raw）等の自由記述フィールド内に、投稿者自身によって地の文として
書き込まれたホスト情報らしき文字列（IPアドレス・ISPドメイン・proxy言及・
ブラウザUser-Agent文字列）を検出・匿名化するための専用検出器。

$envlist（$envaddr/$envua、隠しHTMLコメント）による構造化されたホスト情報
とは別の経路として設計する。実データ検証（20020721.html、3,825投稿）で、
本文中に ".ne.jp"(85件) ".co.jp"(122件) ".plala."(18件) ".dion."(4件)
"proxy"(1件) のようなパターンが、3,825投稿中104件（本文の様々な位置に
散在、末尾固定ではない）で確認された（中身は未閲覧・件数と位置比率のみ）。

Derived from: spec/principles.md（著作物としての敬意）、DISCLAIMER.md
（公開情報における個人情報の取扱い）
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime


def generate_runtime_salt() -> str:
    """動作時（処理実行時）の年月日時分秒をsaltとして生成する。

    完全一致するハッシュ値同士は「同じ元の値が複数箇所に存在する」ことの
    手がかりになり得る（複合による絞り込みのリスク）ため、本ツールキットの
    方針として、saltは実行のたびに変わる時刻ベースの値とし、かつハッシュ
    自体も先頭8文字に切り詰める（_salted_sha256参照）。
    """
    return datetime.now().strftime("%Y%m%d%H%M%S")


# IPv4アドレス（ドット区切り4組の数字）。
# \bだと直後が日本語（Unicode \w扱い）の場合に境界不成立となり検出漏れに
# なるため、数字の直前直後のみを見る否定先読み/後読みに変更。
_IPV4_RE = re.compile(r"(?<!\d)\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?!\d)")

# 日本国内でよく使われる組織種別TLD（.ne.jp/.co.jp/.or.jp/.ad.jp/.go.jp/
# .ac.jp/.gr.jp）を末尾に持つホスト名らしき文字列。
# 注意: 実際のホスト名はASCII文字のみで構成されるため、\w（Unicode対応、
# 日本語も含む）ではなく[A-Za-z0-9-]に限定する。\wのままだと直前の日本語
# 文字列まで巻き込んでマッチしてしまう問題を確認したため修正済み。
_JP_DOMAIN_RE = re.compile(
    r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.(?:ne|co|or|ad|go|ac|gr)\.jp",
    re.IGNORECASE,
)

# 主要な日本のISP名を含むホスト名（TLDがjpでない場合も含む）
_ISP_HINT_RE = re.compile(
    r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*"
    r"\.(?:plala|dion|odn|ocn|bbtec|nifty|so-net|asahi-net)"
    r"\.[A-Za-z0-9.]+",
    re.IGNORECASE,
)

# 「proxy」への直接言及（プロキシ経由の指摘等、荒らし対策文脈で頻出）。
# 直前が日本語（Unicode \w扱い）だと\bが成立せず検出漏れになるため、
# 先頭の\bは付けない。末尾もASCII文字限定で継続部分のみ拾う。
_PROXY_HINT_RE = re.compile(r"proxy[A-Za-z0-9._-]*", re.IGNORECASE)

# ブラウザUser-Agent文字列が本文中に貼り付けられているケースの検出
_UA_HINT_RE = re.compile(
    r"Mozilla/[\d.]+\s*\([^)]*\)|MSIE\s*[\d.]+|Opera/[\d.]+",
    re.IGNORECASE,
)

_ALL_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("ipv4", _IPV4_RE),
    ("jp_domain", _JP_DOMAIN_RE),
    ("isp_hint", _ISP_HINT_RE),
    ("proxy_hint", _PROXY_HINT_RE),
    ("ua_hint", _UA_HINT_RE),
]


@dataclass
class DetectionRecord:
    """検出1件分の記録。原文の値そのものは含まず、種別・位置・ハッシュ
    のみを保持する（Provenanceに記録する想定の形）。"""

    pattern_name: str
    start: int
    end: int
    salted_hash: str


def _salted_sha256(value: str, salt: str) -> str:
    """host_meta/ua_meta と同一方針（ソルト付きSHA-256）でハッシュ化する。

    完全なハッシュ値（64文字）同士が一致すると「同一の元の値が複数箇所に
    存在する」ことが分かってしまい、複合的な絞り込み（linkage）に使われ
    得るため、先頭8文字のみを保持する（衝突を意図的に増やし、一致しても
    元の値の同一性を断定できないようにする）。salt自体はgenerate_runtime_salt()
    による実行時刻ベースの値を想定する。
    """
    return hashlib.sha256((salt + value).encode("utf-8")).hexdigest()[:8]


def detect(text: str) -> list[tuple[str, int, int]]:
    """textの中からホスト情報らしきパターンの位置を検出する。

    戻り値は (pattern_name, start, end) のリスト。原文の値そのものは
    含まない（位置情報のみ）。
    """
    matches: list[tuple[str, int, int]] = []
    for name, pattern in _ALL_PATTERNS:
        for m in pattern.finditer(text):
            matches.append((name, m.start(), m.end()))
    matches.sort(key=lambda t: t[1])
    return matches


def _merge_spans(
    matches: list[tuple[str, int, int]]
) -> list[tuple[str, int, int]]:
    """複数パターンが重なって検出された区間をマージする。"""
    if not matches:
        return []
    merged = [matches[0]]
    for name, start, end in matches[1:]:
        last_name, last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_name, last_start, max(last_end, end))
        else:
            merged.append((name, start, end))
    return merged


def sanitize(
    text: str, salt: str, mask_char: str = "〇"
) -> tuple[str, list[DetectionRecord]]:
    """検出したパターンを同じ文字数のmask_charで置換する（ng-checkの
    マスク方式に合わせる）。

    戻り値:
        (匿名化後テキスト, 検出記録のリスト)
    検出記録には原文の値そのものは含まれず、ソルト付きSHA-256ハッシュ
    のみを保持する。
    """
    raw_matches = detect(text)
    merged = _merge_spans(raw_matches)

    result_chars = list(text)
    records: list[DetectionRecord] = []
    for name, start, end in merged:
        original_span = text[start:end]
        records.append(
            DetectionRecord(
                pattern_name=name,
                start=start,
                end=end,
                salted_hash=_salted_sha256(original_span, salt),
            )
        )
        for i in range(start, end):
            result_chars[i] = mask_char

    return "".join(result_chars), records
