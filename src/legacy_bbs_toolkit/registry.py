"""
legacy-bbs-toolkit: Parser Plugin Registry

Parser Plugin Namespace契約（spec/parser-api.md）の実装:
  1. 各Parserプラグインは一意な識別子（名前空間）を持たなければならない。
  2. 名前空間の一意性は、登録先のレジストリ内で検証可能でなければならない。
  3. 同一名前空間での二重登録（なりすまし等）は拒否しなければならない。
  4. 名前空間の具体的な文字列形式・命名規則は本契約の範囲外とし、実施要項
     で例示する（推奨形式: legacy-bbs-toolkit.parser.<name>）。

Python実装のentry_pointsグループ: legacy_bbs_toolkit.parsers

あわせて、Detection / Selection / User Override 契約の骨格実装も含む。
Resolution Policyの正式な比較基準（confidence→priority→登録順、等）は
未実装（TODO）。
"""

from __future__ import annotations

from importlib.metadata import entry_points
from typing import Any, Optional, Protocol, runtime_checkable


@runtime_checkable
class ParserProtocol(Protocol):
    """全Parserプラグインが満たすべき最小インターフェース。"""

    namespace: str

    def detect(self, raw_text: str) -> bool: ...
    def parse(self, raw_text: str) -> Any: ...


class NamespaceConflictError(Exception):
    """契約3: 同一名前空間での二重登録は拒否する。"""


class ParserRegistry:
    """Parser Plugin Namespace契約に基づくレジストリ実装。"""

    ENTRY_POINT_GROUP = "legacy_bbs_toolkit.parsers"

    def __init__(self) -> None:
        self._parsers: dict[str, ParserProtocol] = {}

    def register(self, parser: ParserProtocol) -> None:
        """契約1・2・3の実装本体。"""
        namespace = parser.namespace
        if namespace in self._parsers:
            existing = type(self._parsers[namespace]).__name__
            attempted = type(parser).__name__
            raise NamespaceConflictError(
                f"namespace '{namespace}' is already registered "
                f"(existing: {existing}, attempted: {attempted})"
            )
        self._parsers[namespace] = parser

    def is_registered(self, namespace: str) -> bool:
        return namespace in self._parsers

    def get(self, namespace: str) -> ParserProtocol:
        return self._parsers[namespace]

    def all_namespaces(self) -> list[str]:
        return sorted(self._parsers.keys())

    def load_from_entry_points(self) -> list[str]:
        """setuptools entry_points（legacy_bbs_toolkit.parsersグループ）
        経由でインストール済みのParserプラグインを自動検出・登録する。

        戻り値は正常に登録できたnamespaceのリスト。同一namespaceを
        持つプラグインが複数見つかった場合はNamespaceConflictErrorを
        送出する（契約3）。
        """
        loaded: list[str] = []
        for ep in entry_points(group=self.ENTRY_POINT_GROUP):
            parser_cls = ep.load()
            parser = parser_cls()
            self.register(parser)
            loaded.append(parser.namespace)
        return loaded


def detect_and_select(
    registry: ParserRegistry,
    raw_text: str,
    user_override: Optional[str] = None,
) -> tuple[Optional[str], dict]:
    """Detection→Selection→User Override契約の骨格実装。

    戻り値: (選択されたnamespace or None, provenance用の記録dict)

    TODO: Resolution Policyの正式な比較基準（confidence比較→priority比較→
    登録順、等）は未実装。現状は「Detectionがtrueを返した最初のParser
    （namespaceのソート順）」を選ぶ簡易実装に留める。
    """
    candidates = [
        ns
        for ns in registry.all_namespaces()
        if registry.get(ns).detect(raw_text)
    ]

    if user_override is not None:
        if user_override not in registry.all_namespaces():
            raise KeyError(f"unknown namespace: {user_override}")
        if not registry.get(user_override).detect(raw_text):
            # User Override契約3: Detectionがfalseの場合はOverrideをエラー
            # として拒否する。
            raise ValueError(
                f"user override '{user_override}' rejected: "
                f"parser reports it cannot handle this input (Detection=false)"
            )
        return user_override, {
            "selection_path": "user_override",
            "pre_override_selection": candidates[0] if candidates else None,
        }

    if not candidates:
        return None, {
            "selection_path": "selection",
            "resolution_basis": "no_candidate",
        }

    selected = candidates[0]
    return selected, {
        "selection_path": "selection",
        "resolution_basis": "first_candidate (TODO: full Resolution Policy)",
    }
