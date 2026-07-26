# Glossary

本プロジェクトで使用する用語の定義。カテゴリ別に整理する（ABC順ではなく
意味のまとまりで読めるようにするため）。

---

## Design Principles

各用語の定義は spec/principles.md 本文を参照。

- **Archive First（アーカイブファースト）** — 本ツールキットの根幹原則。処理の
  目的はアーカイブの安全・持続可能な保存であり、解析・匿名化はその手段。
- **Selectable Specification（選べる仕様）** — 唯一の正解を押し付けず、利用者が
  目的・倫理的判断に応じて処理方針を選択できるようにする設計原則。
- **Separation of Specification and Implementation（仕様と実装の分離）** — 仕様
  （spec/配下）は特定の実装言語・実装詳細に依存しない形で記述し、実装はその
  「ひとつの実現形」として位置づける。
- **Loose Coupling（疎結合）** — コア機能と解析等の利用例を互いに独立したモジュール
  として構成し、一方の変更が他方を強制的に変更させない構造を保つ。
- **Respect for Works（著作物としての敬意）** — BBSの過去ログは投稿者の著作物であり
  文化的資産である。本ツールキットはそれを「消す」のではなく、公開可能な形で
  未来へ残すことを目的とする。

## Parser API

各用語の定義は spec/parser-api.md 本文を参照。

- **Parser** — 特定のBBSログ形式を解析し、Intermediate Representationへ変換する
  プラグイン実装の単位。
- **Detection** — Parserが「自分はこの入力を処理できるか」を真偽値で返す操作。
- **Selection** — 登録されたParser群の中から、Resolution Policyに従い処理に用いる
  Parserを一つ決定する操作。
- **Resolution Policy** — Selectionがどの比較基準をどの順序で適用するかを定める方針。
  具体的な判定順序は実施要項で例示する（confidence比較→priority比較→登録順）。
- **User Override** — 自動SelectionをParserを明示指定して置き換える操作。
  Detectionがfalseを返したParserへのOverrideは拒否される。
- **Provenance** — 各処理対象についての選択経路・判断根拠・前提条件の記録。
  アーカイブとしての真正性・検証可能性を担保する。
- **Parser Plugin Namespace** — 各Parserプラグインが持つ一意な識別子。重複登録は
  拒否される。推奨形式: `legacy-bbs-toolkit.parser.<name>`。
- **Non-Guarantees** — Parserが「保証しないこと」を明文化した節。Detection=trueは
  解析結果の正確性を保証しない等。

## Data Model

- **Intermediate Representation（IR）** — 1投稿を表す中間データ構造。Parser出力の
  標準形式。スキーマは spec/intermediate.schema.json で定義する。
- **IR Schema** — IRのフィールド定義・型・制約をJSON Schema（draft 2020-12）形式で
  記述したもの。`spec/intermediate.schema.json` がその実体。

## Documentation

- **Specification** — spec/配下に置かれる、実装言語・実装詳細に依存しない設計仕様書。
- **Derived from** — 各契約節の冒頭に置く出典表記。どのDesign Principleから
  導かれた契約であるかを示す。
- **Misuse Case** — 想定しない誤用・悪用のシナリオ。spec/misuse-cases.md に整理する。
- **Adversarial Review** — 悪意ある利用者・実装者の視点から仕様の穴を検討する
  レビュー手法。本プロジェクトの策定プロセスに組み込まれている。
- **実施要項（Implementation Guidance）** — 契約（Contract）に付随する任意・非拘束の
  推奨実装例。仕様の範囲外だが、実装の参考になる情報を提供する。
- **契約（Contract）** — Specificationへの適合性を定義するための約束事。法的な
  契約や罰則を意味するものではない。

---

## 判断待ち・未確定

- **Capability**：Detectionの説明で「能力」の意味で使うか、独立した英語術語として
  Glossaryに載せるかが未確定（保留中）。
