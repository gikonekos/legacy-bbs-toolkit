"""
legacy-bbs-toolkit: ng_check_bridge

[[ng-check]]（ng-check.php、別リポジトリ github.com/gikonekos/ng-check-php）
をサブプロセス経由で呼び出し、body_raw等のNG語サニタイズを行うための
ブリッジ。

ng-check.phpのCLIインターフェース（実ソース照合済み）:
    php ng-check.php --file=<path> --hashes=<path>
                     --min-len=<N> --max-len=<N>
                     --mask-char=<char> --out=<path>

終了コード:
    0  = OK（該当なし）
    3  = NG該当あり
    1  = 引数/入力エラー

標準出力書式:
    判定: NG（該当あり）  または  判定: OK（該当なし）
    検出数: N件
    [置換後テキストは --out 指定時のみファイルへ、未指定時は標準出力に続く]

本ブリッジは --out に一時ファイルを渡し、置換後テキストをファイルから
読み込む方式で動作する（標準出力の判定行とテキストを分離するため）。

Derived from: spec/principles.md「疎結合」原則 — NG語判定ロジックを
Python側に複製せず外部コマンドとして連携する。
"""

from __future__ import annotations

import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


class NgCheckBridgeError(Exception):
    """ng-check.php呼び出し自体が失敗した場合（PHP不在、辞書ファイル
    不在、終了コード1等）。"""


@dataclass
class NgCheckResult:
    ng_detected: bool       # 終了コード3ならTrue、0ならFalse
    match_count: int        # 「検出数: N件」から取得
    sanitized_text: str     # --outファイルの内容


# 標準出力から検出件数を読み取る
_MATCH_COUNT_RE = re.compile(r"検出数[：:]\s*(\d+)件")
# 終了コード3 = NG該当あり
_EXIT_CODE_NG = 3


def sanitize_with_ng_check(
    text: str,
    *,
    php_path: str = "php",
    ng_check_path: str = "ng-check.php",
    hashes_path: str = "hashes-txt.gz",
    mask_char: str = "〇",
    min_len: int = 2,
    max_len: int = 16,
    timeout_seconds: int = 10,
) -> NgCheckResult:
    """textをng-check.phpに渡し、NG判定結果とサニタイズ済みテキストを
    取得する。

    実装方式: textを一時ファイルに書き出し、ng-check.phpへ --file= で渡す。
    置換後テキストは --out= で別の一時ファイルに書き出させ、それを読み込む。
    一時ファイルはUTF-8で扱う（Parser側でIRのbody_raw等は既にUTF-8化済み
    である前提。ng-check.php側も --from=AUTO で正しくUTF-8と判定する）。
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        in_path = Path(tmpdir) / "input.txt"
        out_path = Path(tmpdir) / "output.txt"
        in_path.write_text(text, encoding="utf-8")

        cmd = [
            php_path,
            ng_check_path,
            f"--file={in_path}",
            f"--hashes={hashes_path}",
            f"--min-len={min_len}",
            f"--max-len={max_len}",
            f"--mask-char={mask_char}",
            f"--out={out_path}",
        ]

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
        except FileNotFoundError as e:
            raise NgCheckBridgeError(
                f"php または ng-check.php が見つからない: {e}"
            ) from e
        except subprocess.TimeoutExpired as e:
            raise NgCheckBridgeError(
                f"ng-check.php がタイムアウトした（{timeout_seconds}秒）"
            ) from e

        # 終了コード1はエラー（辞書不在・引数不正等）
        if proc.returncode == 1:
            raise NgCheckBridgeError(
                f"ng-check.php がエラー終了（returncode=1）: "
                f"{proc.stderr.strip() or proc.stdout.strip()}"
            )

        ng_detected = proc.returncode == _EXIT_CODE_NG

        count_match = _MATCH_COUNT_RE.search(proc.stdout)
        match_count = int(count_match.group(1)) if count_match else 0

        # --outファイルが生成されていれば読み込む。
        # 生成されていない場合（検出数0でも必ず書き出されるはずだが
        # 念のため）は入力テキストをそのまま返す。
        if out_path.exists():
            sanitized_text = out_path.read_text(encoding="utf-8")
        else:
            sanitized_text = text

        return NgCheckResult(
            ng_detected=ng_detected,
            match_count=match_count,
            sanitized_text=sanitized_text,
        )
