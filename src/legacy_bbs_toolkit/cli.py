"""
legacy-bbs-toolkit CLI

使い方:
    legacy-bbs-toolkit <入力ファイル> [--out 出力.jsonl]
                       [--override <namespace>]
                       [--salt <任意のsalt>]
                       [--ng-check-php <phpコマンドパス>]
                       [--ng-check-hashes <hashes-txt.gz>]
                       [--summary-only]

動作:
    1. entry_points（legacy_bbs_toolkit.parsers）経由で全Parserを登録
    2. Detection→Selection（--override指定時はUser Override契約に従う）
    3. 選択されたParserでparseし、IRをJSON Lines（1行1投稿）で--outへ出力
    4. 標準出力には件数・警告等のサマリのみを表示する
       （ログ本文そのものは標準出力に表示しない。--summary-onlyの場合は
       ファイル出力も行わず、サマリのみ）
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from legacy_bbs_toolkit.registry import ParserRegistry, detect_and_select

# to-utf8.phpのdetectEncodingHeuristic()と完全に同方針のヒューリスティック。
# バイトペアを見てスコアリングし、多数決で判定する。
# CP932/EUC-JPが互いに誤判定しやすいが、以下の条件で分離する:
#   CP932リードバイト: 0x81-0x9F, 0xE0-0xFC / トレイル: 0x40-0x7E, 0x80-0xFC
#   EUC-JPリードバイト: 0xA1-0xFE (0x8E=SS2, 0x8F=SS3含む) / トレイル: 0xA1-0xFE
#   両方に合致する曖昧ペアはCP932側にわずかに加点（実出現頻度がCP932優位の前提）
_ENCODINGS = ["utf-8", "cp932", "euc_jp"]


def _detect_encoding(raw: bytes) -> str:
    """バイト列から最も可能性の高いエンコーディングを返す。

    to-utf8.phpのisValidUtf8() + detectEncodingHeuristic()と完全に同方針:
    1. バイト単位でUTF-8の正当性を検証
    2. CP932/EUC-JPはバイトペアのスコアリングで多数決判定
    """
    # ---- UTF-8 厳密検証（to-utf8.phpのisValidUtf8()相当）----
    i = 0
    n = len(raw)
    valid_utf8 = True
    while i < n:
        b = raw[i]
        if b < 0x80:
            i += 1
            continue
        if (b & 0xE0) == 0xC0:
            extra = 1
        elif (b & 0xF0) == 0xE0:
            extra = 2
        elif (b & 0xF8) == 0xF0:
            extra = 3
        else:
            valid_utf8 = False
            break
        if i + extra >= n:
            valid_utf8 = False
            break
        for j in range(1, extra + 1):
            if (raw[i + j] & 0xC0) != 0x80:
                valid_utf8 = False
                break
        else:
            i += extra + 1
            continue
        break
    if valid_utf8:
        return "utf-8"

    # ---- CP932 / EUC-JP スコアリング（to-utf8.phpのdetectEncodingHeuristic()相当）----
    cp932_score = 0
    euc_score = 0
    i = 0
    ascii_only = True
    while i < n:
        b1 = raw[i]
        if b1 <= 0x7F:
            i += 1
            continue
        ascii_only = False
        if i + 1 >= n:
            break
        b2 = raw[i + 1]

        is_cp932_lead = (0x81 <= b1 <= 0x9F) or (0xE0 <= b1 <= 0xFC)
        is_cp932_trail = (0x40 <= b2 <= 0x7E) or (0x80 <= b2 <= 0xFC)
        is_euc_lead = (0xA1 <= b1 <= 0xFE) or b1 == 0x8E or b1 == 0x8F
        is_euc_trail = 0xA1 <= b2 <= 0xFE

        if is_cp932_lead and is_cp932_trail and not (is_euc_lead and is_euc_trail):
            cp932_score += 1
            i += 2
        elif is_euc_lead and is_euc_trail and not (is_cp932_lead and is_cp932_trail):
            euc_score += 1
            i += 2
        elif is_cp932_lead and is_cp932_trail:
            # 曖昧区間: CP932に加点（to-utf8.phpと同じタイブレーク方針）
            cp932_score += 1
            euc_score += 1
            i += 2
        else:
            i += 1

    if ascii_only:
        return "utf-8"  # ASCII-onlyはUTF-8として扱う（変換不要）
    if cp932_score == 0 and euc_score == 0:
        return "cp932"  # 判定不能時はCP932をデフォルト（to-utf8.phpのUNKNOWN相当）
    return "cp932" if cp932_score >= euc_score else "euc_jp"


def _read_file(path: Path, encoding_hint: str | None) -> str:
    """ファイルを読み込み、UTF-8文字列として返す。
    encoding_hintが指定されていればそれを優先し、なければ自動判定する。
    """
    raw = path.read_bytes()
    enc = encoding_hint if encoding_hint else _detect_encoding(raw)
    return raw.decode(enc, errors="replace")


# namespace -> 非エンジニア向けの日本語表示名・簡単な説明
# CLIサマリー表示専用。パーサー自体の識別・動作には一切影響しない。
_FRIENDLY_PARSER_NAMES: dict[str, str] = {
    "legacy-bbs-toolkit.parser.kscrr1p9": (
        "kscrr1p9系（あやしいわーるど＠暫定・zbbs.cgi系列）"
    ),
    "legacy-bbs-toolkit.parser.ksphp_plus": (
        "ksphp_plus系（kuzuha-scriptPHP+系列）"
    ),
    "legacy-bbs-toolkit.parser.remix": "remix系（リミックス系統）",
    "legacy-bbs-toolkit.parser.mizuiro": "mizuiro系（みずいろ／ダーザイン系統）",
    "legacy-bbs-toolkit.parser.meiso": "meiso系（メイソ系統）",
    "legacy-bbs-toolkit.parser.ariake": (
        "ariake系（有明／MINIBBS系統・投稿日時に年情報なし）"
    ),
}

_FRIENDLY_SELECTION_PATH: dict[str, str] = {
    "user_override": "手動指定（--override）",
    "selection": "自動判定",
}


def _friendly_parser_name(namespace: str) -> str:
    return _FRIENDLY_PARSER_NAMES.get(namespace, namespace)


def _friendly_selection_path(path: str | None) -> str:
    return _FRIENDLY_SELECTION_PATH.get(path or "", path or "不明")


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="legacy-bbs-toolkit",
        description="日本語BBS過去ログのアーカイブ前処理（IR生成）",
    )
    ap.add_argument("input", help="入力ログファイル（UTF-8を想定）")
    ap.add_argument(
        "--out",
        help="IR出力先（JSON Lines）。省略時は <入力名>.ir.jsonl",
    )
    ap.add_argument(
        "--from",
        dest="encoding",
        choices=["auto", "utf-8", "cp932", "euc_jp"],
        default="auto",
        help="入力ファイルの文字コード（既定: auto=自動判定）",
    )
    ap.add_argument(
        "--override",
        help="User Override: 使用するParserの名前空間を明示指定",
    )
    ap.add_argument(
        "--salt",
        help="匿名化ハッシュ用salt。省略時は実行時刻（YYYYMMDDHHMMSS）",
    )
    ap.add_argument("--ng-check-php", help="ng-check連携時のphpコマンドパス")
    ap.add_argument(
        "--ng-check-hashes",
        default="hashes-txt.gz",
        help="ng-check用NG辞書パス（既定: hashes-txt.gz）",
    )
    ap.add_argument(
        "--summary-only",
        action="store_true",
        help="ファイル出力せず、サマリ（件数・警告）のみ表示",
    )
    ap.add_argument(
        "--verbose",
        action="store_true",
        help="技術的な詳細（namespace文字列・selection内部情報等）も表示する",
    )
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    in_path = Path(args.input)
    if not in_path.exists():
        print(f"error: input not found: {in_path}", file=sys.stderr)
        return 2

    enc_hint = None if args.encoding == "auto" else args.encoding
    text = _read_file(in_path, enc_hint)

    registry = ParserRegistry()
    loaded = registry.load_from_entry_points()
    if not loaded:
        print(
            "error: no parsers registered "
            "(entry_points group legacy_bbs_toolkit.parsers is empty)",
            file=sys.stderr,
        )
        return 2

    try:
        namespace, selection_provenance = detect_and_select(
            registry, text, user_override=args.override
        )
    except (KeyError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    if namespace is None:
        print("error: no parser can handle this input (Detection all false)",
              file=sys.stderr)
        return 1

    parser = registry.get(namespace)
    # Parser個別の設定（salt/ng-check）はkscrr1p9 Parserのコンストラクタ
    # 引数として渡し直す。TODO: Parser共通の設定受け渡し方法は、仕様側
    # （Selectable Specification）とあわせて将来整理する。
    parser = type(parser)(
        host_pattern_salt=args.salt,
        ng_check_php_path=args.ng_check_php,
        ng_check_hashes_path=args.ng_check_hashes,
    )

    result = parser.parse(text)

    n_email = sum(1 for r in result.records if r.author_email_detected)
    n_body_hits = sum(
        r.provenance.get("body_pattern_hits", 0) for r in result.records
    )
    n_ng = sum(1 for r in result.records if r.provenance.get("ng_check_ran"))
    n_year_missing = sum(
        1 for r in result.records
        if r.provenance.get("timestamp_year_missing")
    )

    out_path = Path(args.out) if args.out else in_path.with_suffix(".ir.jsonl")

    # ---- 非エンジニア向けサマリー（既定表示） ----
    print("=" * 40)
    print(" legacy-bbs-toolkit 解析結果")
    print("=" * 40)
    print()
    if result.warnings:
        print("⚠️  警告があります。内容を確認してください。")
    else:
        print("✅ 正常に処理できました。")
    print()
    print(f"  使用したパーサー : {_friendly_parser_name(namespace)}")
    print(f"  判定方法         : {_friendly_selection_path(selection_provenance.get('selection_path'))}")
    print(f"  投稿件数         : {len(result.records)}件")
    print(f"  警告             : {'なし' if not result.warnings else f'{len(result.warnings)}件'}")
    for w in result.warnings:
        print(f"    - {w}")
    if n_email:
        print(f"  メールアドレスらしき記述: {n_email}件（自動的に匿名化されます）")
    if n_year_missing:
        print(f"  投稿日時に年情報がない投稿: {n_year_missing}件（年は補完せず空欄のまま出力）")
    if not args.summary_only:
        print(f"  出力先           : {out_path}")
    print()

    # ---- 技術的な詳細（--verbose指定時のみ） ----
    if args.verbose:
        print("-" * 40)
        print(" 技術的な詳細（--verbose）")
        print("-" * 40)
        print(f"parser        : {namespace}")
        print(f"selection     : {selection_provenance.get('selection_path')}")
        print(f"records       : {len(result.records)}")
        print(f"warnings      : {len(result.warnings)}")
        for w in result.warnings:
            print(f"  - {w}")
        print(f"author_email_detected : {n_email}")
        print(f"body_pattern_hits sum : {n_body_hits}")
        print(f"ng_check_ran          : {n_ng}")
        print(f"timestamp_year_missing: {n_year_missing}")
        print()

    if args.summary_only:
        return 0

    with out_path.open("w", encoding="utf-8") as f:
        for record in result.records:
            f.write(json.dumps(record.to_dict(), ensure_ascii=False))
            f.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
