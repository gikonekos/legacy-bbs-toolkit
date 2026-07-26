"""legacy_bbs_toolkit — 日本語BBS過去ログのアーカイブ前処理基盤（実装）。

仕様: https://github.com/gikonekos/legacy-bbs-toolkit （spec/配下）
本パッケージはその仕様の「ひとつの実現形」であり、仕様に従属する
（spec/principles.md「仕様と実装の分離」）。
"""

from legacy_bbs_toolkit.registry import (
    NamespaceConflictError,
    ParserRegistry,
    detect_and_select,
)

__version__ = "0.1.0"

__all__ = [
    "ParserRegistry",
    "NamespaceConflictError",
    "detect_and_select",
    "__version__",
]
