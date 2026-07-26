# 復元ノート（2026-07-13作成）

このzipは、過去の複数チャットセッションでの議論内容を検索・精査して
組み立てたものです。実際のリポジトリファイルが一度もアップロード
されていなかったため、会話ログからの再構成です。以下、確認レベルを
明記します。

## ほぼ確定文言のまま回収できたもの

- 最上位原則（二大モットー）
  Source: Claude conversation (2026-07-05)
- spec/principles.md：「アーカイブファースト」「仕様と実装の分離」
  「疎結合」「著作物としての敬意」の4原則、本文込み
  Source: Claude conversation (2026-07-05)
- spec/parser-api.md：Detection / Selection / Resolution Policy /
  User Override / Provenance / Non-Guarantees、ほぼ全文
  Source: Claude conversation (2026-07-11)
- spec/parser-api.md：Parser Plugin Namespace、Timestamp Handling
  （2026-07-13の別セッションで確定した分）
  Source: Claude conversation (2026-07-13/14, summary + fragments)
- LICENSE.md：MIT、Copyright (c) 2026 MOTOI Kenkichi
  Source: Claude conversation (2026-07-13/14, summary)

## 構造（見出し・項目名）は確定しているが、本文が未回収のもの

- spec/principles.md：「選べる仕様」原則の本文（再構成案を代わりに
  記載。関連する個別仕様の決定事項は確定済み）
  Source（構造・関連決定事項）: Claude conversation (2026-07-05)
  Source（原則本文）: 未回収
- spec/misuse-cases.md：4カテゴリの見出しは確定。1.1、1.2、2.1の
  シナリオ本文は未回収（3.1、3.2、4.1は回収済み）
  Source（見出し・3.1/3.2/4.1）: Claude conversation (2026-07-11)
  Source（1.1/1.2/2.1本文）: 未回収
- spec/glossary.md：4カテゴリ・約20語の用語一覧は確定。各語の定義
  本文はほとんど未回収
  Source（用語一覧）: Claude conversation (2026-07-11)
  Source（定義本文）: 未回収

## 解消済みの疑問点（2026-07-16）

- 「18語・5カテゴリ」問題：過去ログを再確認した結果、これは
  Documentationカテゴリへ Adversarial Review／契約 が追加確定される
  前の、セッション中盤時点の古いスナップショット値だったと判明。
  最終確定状態は spec/glossary.md の通り 4カテゴリ・20語であり、
  第5のカテゴリは存在しない。

## 要確認・矛盾がある点

- Parser Plugin Namespace / Timestamp Handling を parser-api.md内に
  置くか、別ファイルに分離するかは編集上の保留のまま未確定
- spec/README.md（Specification Writing Guide）は文体方針・Normative
  Language・雛形などの断片は見つかったが、独立ファイルとして組み立てる
  だけの分量は今回回収できず、このzipには含めていません
- DISCLAIMER.md / ETHICS.md：構成案（3層構造）の議論はあったが、
  本文確定には至っていない模様。このzipには含めていません

## 次回セッションでやるべきこと

1. 「選べる仕様」原則の本文を確定させる
2. misuse-cases.mdの未回収3項目（1.1, 1.2, 2.1）の本文を確定させる
3. glossary.mdの各語定義を確定させる
4. spec/README.md、DISCLAIMER.md、ETHICS.md の着手


## 2026-07-14 セッション追記（会話ログから回収）

Source: ChatGPT conversation (2026-07-14, Motoiさん経由でこのチャットへ共有)

- Provenance保存形式・改訂方式はPhase 2全体確定後に検討する方針を確認。
- Parser Plugin Namespace契約を確定し、parser-api.mdへ反映する方針を確認。
- Timestamp Handlingの内容は確定、配置先のみ編集上の保留と整理。
- glossary.mdは都度更新せず、Phase 2完了後に追加候補（例: Namespace）を一括レビューする方針。
- DISCLAIMER.mdおよびETHICS.mdは未着手であり、本文は未回収。新規起草対象。
- 保留事項は「仕様としての保留」と「編集上の保留」を区別して管理する方針を採用。


## 2026-07-27 追記（本記載が最新状態）

上記の記録と現状の差分を以下の通り解消する。上記の古い記述は履歴として残す。

- spec/glossary.md：各語の定義本文を新規起草した（過去ログからの「回収」では
  なく、確定済みの仕様本文に基づく新規の要約文である）。また、Phase 2完了後の
  バッチレビュー予定だった「Parser Plugin Namespace」を用語として追加した。
  現在は4カテゴリ・21語。
- DISCLAIMER.md / ETHICS.md：本文を新規起草・確定し、本リポジトリに追加済み。
  「未着手」の記載は解消。
- spec/principles.md「選べる仕様」：本文は引き続き再構成案のまま
  （過去ログからの原文回収は未了。ただし関連する個別仕様の決定事項は確定済み）。
- spec/misuse-cases.md：1.1／1.2／2.1のシナリオ本文は引き続き未回収。
- 実装：Python実装（src/legacy_bbs_toolkit/、tests/、pyproject.toml）を追加。
  zantei20070218形式Parserは実データ2ファイル（計12,015投稿）で検証済み。
