# Glossary

本プロジェクトで使用する用語の定義。カテゴリ別に整理する（ABC順ではなく
意味のまとまりで読めるようにするため）。

> ⚠️ 各用語の「定義」本文の多くは過去ログから確定文言を回収できていません。
> 用語一覧（カテゴリ分け）自体は確定済みです。定義本文は今後のセッションで
> 確定させる必要があります。

---

## Design Principles

- **Archive First（アーカイブファースト）**
- **Selectable Specification（選べる仕様）**
- **Separation of Specification and Implementation（仕様と実装の分離）**
- **Loose Coupling（疎結合）**
- **Respect for Works（著作物としての敬意）**

（各用語の定義は spec/principles.md 本文を参照。Glossaryとしての要約
文はまだ確定していない）

## Parser API

- **Parser**
- **Detection**
- **Selection**
- **Resolution Policy**
- **User Override**
- **Provenance**
- **Non-Guarantees**

（各用語の定義は spec/parser-api.md 本文を参照。Glossaryとしての要約
文はまだ確定していない）

## Data Model

- **Intermediate Representation（IR）**
- **IR Schema**

（未着手：intermediate.schema.json 側の仕様確定後、定義を転記する予定）

## Documentation

- **Specification**
- **Derived from**
- **Misuse Case**
- **Adversarial Review**
- **実施要項（Implementation Guidance）**
- **契約（Contract）**
  - 注記（確定済み）: 本プロジェクトにおける「契約」は、Specification
    への適合性を定義するための約束事を指す。法的な契約や罰則を意味する
    ものではない。

---

## 判断待ち・未確定

- **Capability**：Detectionの説明で「能力」の意味で使うか、独立した
  英語術語としてGlossaryに載せるかが未確定（保留中）
- **名前空間**：Parser Plugin Namespace策定に伴い、追加候補として
  挙がっているが、Phase 2完了後のバッチレビューに回す方針

（2026-07-16 解消済み: 「18語・5カテゴリ」という過去の要約は、
Documentationカテゴリへの Adversarial Review／契約 追加確定前の
中間スナップショットであったことを確認。最終確定状態は本ファイル
の通り 4カテゴリ・20語であり、第5カテゴリは存在しない。）
