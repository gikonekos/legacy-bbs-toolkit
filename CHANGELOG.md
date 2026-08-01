# CHANGELOG

## 2026-08-02（2回目）

### 追加
- PyPI公開に向けたメタデータを `pyproject.toml` に追加
  （`readme`、`authors`（MOTOI Kenkichi）、`keywords`、`classifiers`、
  `[project.urls]`（Homepage/Repository/Changelog））。
- GitHub Actions ワークフロー `.github/workflows/workflow.yml` を追加。
  PyPI Trusted Publishing（OIDC）によるリリース公開時の自動パッケージ公開に対応。
- 「くずはすくりぷとm (2008/01/17)」系統（サイト「あやしくないわーるど＠ふぁっしょん」、
  post_id 161-570・410件）の実データ検証を実施。マーカー・本文タグ・日付書式が
  既存 `kscrr1p9` パーサーと一致し、日付前の固定ラベル「投稿日：」も抽出に影響なし。
  警告0・欠落なしで全件パース成功のため、新規Parser追加は不要と判断。

## 2026-08-02

### 変更
- Parser名を `zantei` → `kscrr1p9` に改名（entry_point名・namespace文字列
  `legacy-bbs-toolkit.parser.zantei` → `legacy-bbs-toolkit.parser.kscrr1p9`・
  クラス名 `ZanteiParser` → `Kscrr1p9Parser`・ファイル名
  `parsers/zantei.py` → `parsers/kscrr1p9.py`）。
  対象スクリプト自体（zantei20070218/zbbs.cgi）の名称・実装内容に変更はなし。
  「なぞ」系統（jirou.s58.xrea.com bbs.cgi、投稿本文のタグ開放が特徴）の
  実データ3ファイルを構造検証した結果、テンプレート構造が一致するため
  同Parserでそのままカバー可能と確認（新規Parser追加は不要と判断）。

## 2026-08-01

### 追加
- hr境界系4Parser（マーカーを持たず`<hr>`のみで投稿を区切る系列向け）を実装。
  共通基底クラス `HrBoundaryParserBase`（src/legacy_bbs_toolkit/parsers/hr_boundary.py）に
  タグ名（`<b>`/`<strong>`）・タイムスタンプ書式（スラッシュ年あり／漢字年あり／漢字年なし）
  をパラメータ化し、4系統をサブクラスとして登録:
  - `legacy-bbs-toolkit.parser.remix`（リミックス系統、スラッシュ日付）
  - `legacy-bbs-toolkit.parser.mizuiro`（みずいろ／ダーザイン系統、漢字日付・年あり）
  - `legacy-bbs-toolkit.parser.meiso`（メイソ系統、`<strong>`タグ・UTF-8）
  - `legacy-bbs-toolkit.parser.ariake`（有明／MINIBBS系統、漢字日付・年なし）
- 投稿番号マーカーを持たない系統向けに、post_idをファイル内連番として合成する方式を導入。
- ksphp_plus向けユニットテスト一式（tests/test_basic.py、実データ経由のCLI検証のみだったものを補完）。
- hr境界系4Parserの相互排他性・zantei/ksphp_plusとの非衝突を確認する回帰テスト一式
  （6Parser全登録での選択テストを含む）。

### 修正
- hr境界系Parserのタグ照合にre.IGNORECASEを使用していたため、zantei系の大文字`<B>`テンプレートを
  誤検出する不具合を修正（タグ名部分のみ大文字小文字を区別する実装に変更）。
- AriakeParser（年なし日付）の否定後読みが不十分で、年ありパターン
  （例:「2023年08月01日」）の一部を年なし日付として部分一致誤検出する不具合を修正
  （実データ202308.htmlの検証で発見）。

### 検証
- 実データ（202608.html／202308.html／202510.html／有明ソース埋め込みログ／202607.html／201009.html等）
  で全6Parserの検出・抽出を確認。テストは合計53件全パス。
- ksphp-rc12（2026-08-01リリース分）のテンプレート出力構造をksphp_plus.pyの前提と再照合し、
  一致を確認（パーサー側の修正不要）。

### ドキュメント
- README.mdに「使用スクリプト言語」「対象範囲」節を新設（前回セッションから引き続き）。

## 2026-07-27

### 追加
- Parser Plugin Namespace契約のentry_points登録（registry.py）を実装。
- ng-check（PHP）連携ブリッジ（ng_check_bridge.py）を実装、実際のng-check.php CLI仕様に合わせて確定。
- src-layoutパッケージ構成に再編（src/legacy_bbs_toolkit/、console script `legacy-bbs-toolkit`）。
- ksphp-plus形式（kuzuha-scriptPHP+系列）向けParser（`legacy-bbs-toolkit.parser.ksphp_plus`）を実装。
- DISCLAIMER.md / ETHICS.md を作成。

### 修正
- zantei.pyの本文抽出正規表現を貪欲マッチに変更（本文中の文字通りの`</PRE>`で本文が
  途中で切れる不具合の対策）。
- ブロック終了マーカー欠落・post_id重複時に警告を出すよう修正（黙って捨てない）。

### 検証
- 実データ2ファイル（2002年、計12,015投稿）でzanteiパーサーを検証、0エラー。
- 実データ1ファイル（2026年、1131投稿）でksphp_plusパーサーを検証、0エラー。

## 2026-07-中旬〜下旬（Phase 1〜2）

- Phase 1（Design Principles）確定・凍結。
- Phase 2（Specification）: spec/principles.md, spec/parser-api.md,
  spec/intermediate.schema.json, spec/misuse-cases.md, spec/glossary.md を策定。
- zantei20070218形式向けParserの初期実装（Detection契約実装、抽出ロジックは実データ検証待ちのTODO）。
- GitHubリポジトリ公開（public、MIT License）。
