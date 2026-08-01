"""Parserプラグイン群。

各Parserは spec/parser-api.md の契約（Detection / Parser Plugin
Namespace 等）に従い、entry_pointsグループ legacy_bbs_toolkit.parsers
経由でレジストリに登録される。
"""

from legacy_bbs_toolkit.parsers.kscrr1p9 import Kscrr1p9Parser

__all__ = ["Kscrr1p9Parser"]
