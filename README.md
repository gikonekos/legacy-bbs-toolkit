# Legacy Japanese BBS Archival Preprocessing Toolkit（仮）

1999〜2002年頃の日本語BBS過去ログ（あやしいわーるど等）を対象とした、
デジタル文化資産の前処理基盤。

## 製作方針

速く、軽く、確実に。

## 最上位原則

アーカイブは弄らない。
利用者の利益最大。

詳細は [spec/principles.md](spec/principles.md) を参照。

はじめて使う方は [QUICKSTART.md](QUICKSTART.md)（インストール〜基本的な使い方）をどうぞ。

## 仕様

- [spec/principles.md](spec/principles.md) — 設計原則
- [spec/parser-api.md](spec/parser-api.md) — Parser API仕様
- [spec/intermediate.schema.json](spec/intermediate.schema.json) — IR（中間表現）スキーマ
- [spec/misuse-cases.md](spec/misuse-cases.md) — 想定される誤用ケース
- [spec/glossary.md](spec/glossary.md) — 用語集

## 使用スクリプト言語

| 用途 | 言語 | 備考 |
|---|---|---|
| 本体（本ツールキット） | Python 3.9+ | CLI・Parser・Registry・IR生成 |
| 解析対象①：zantei20070218系 | Perl | zbbs.cgi等。あやしいわーるど＠暫定コミュニティによる改造版 |
| 解析対象②：ksphp-plus系 | PHP | kuzuha-scriptPHP+によるBBS出力 |
| 解析対象③：hr境界系（remix/mizuiro/meiso/ariake） | Perl | くずはすくりぷと亜種・MINIBBS系列、いずれもPerl製CGI |
| サニタイズ連携：ng-check | PHP | 別リポジトリ [ng-check-php](https://github.com/gikonekos/ng-check-php) をサブプロセス呼び出し |
| IR（中間表現）形式 | JSON / JSON Lines | [spec/intermediate.schema.json](spec/intermediate.schema.json)、出力は.jsonl |

対応する掲示板系列が増えるごとに、本体はPythonのまま解析対象言語のみ増える設計（Parser Plugin Namespace契約、詳細は[spec/parser-api.md](spec/parser-api.md)参照）。

## 対象範囲

対象は掲示板が出力した**HTML形式のログ**（ユーザーが保存・共有可能な公開ページ）です。
サーバー管理者のみが保有する生ログ（CSV/.dat/.log等の内部保存形式）はスコープ外です。
一般に流通するのはHTML形式のみであるため。

## 対応系統一覧

| namespace | 系統 | ブロック境界 | タイムスタンプ書式 | post_id |
|---|---|---|---|---|
| `legacy-bbs-toolkit.parser.kscrr1p9` | zantei20070218（あやしいわーるど＠暫定・II等） | `<!-- N -->`〜`<!-- -->` | スラッシュ・年あり | 原文の投稿番号 |
| `legacy-bbs-toolkit.parser.ksphp_plus` | kuzuha-scriptPHP+ | `<div class="m" id="mN">` | スラッシュ・年あり | 原文の投稿番号 |
| `legacy-bbs-toolkit.parser.remix` | リミックス | `<hr>`のみ | スラッシュ・年あり | ファイル内連番（合成） |
| `legacy-bbs-toolkit.parser.mizuiro` | みずいろ／ダーザイン（じょしあな+Team MIZUIRO） | `<hr>`のみ | 漢字・年あり | ファイル内連番（合成） |
| `legacy-bbs-toolkit.parser.meiso` | メイソ | `<hr>`のみ | 漢字・年あり（`<strong>`タグ） | ファイル内連番（合成） |
| `legacy-bbs-toolkit.parser.ariake` | 有明（MINIBBS系列） | `<hr>`のみ | 漢字・**年なし** | ファイル内連番（合成） |

投稿番号マーカーを持たない系統はpost_idをファイル内連番として合成する。
有明系統は原文に年情報が無いため`parsed_timestamp`はNone（ISO 8601化不能、推測補完はしない）。



Python 3.9+ パッケージとして提供。

```
pip install -e .
legacy-bbs-toolkit <ログファイル> [--out 出力.jsonl] [--from auto|utf-8|cp932|euc_jp]
                    [--ng-check-php php] [--ng-check-hashes hashes-txt.gz]
                    [--summary-only]
```

## 依存コンポーネント

サニタイズ機能は [ng-check](https://github.com/gikonekos/ng-check-php) を利用します。
NG辞書（hashes-txt.gz形式）は本リポジトリに現在運用中の実データ（SHA-256ハッシュ化済み）を含みます。

文字コード自動判定のロジックは [to-utf8-php](https://github.com/gikonekos/-to-utf8-php) と同方針で実装しています。

## 状態

Phase 1（Design Principles）：完了・凍結済み。

Phase 2（Specification）：コア仕様確定。DISCLAIMER.md / ETHICS.md 追加済み。
Provenanceの保存形式・改訂方式は実装側の運用方針に委任（意図的な保留継続）。

Phase 3（Implementation）：6系統のParserを実装・実データ検証済み（zantei / ksphp_plus /
remix / mizuiro / meiso / ariake）。詳細は「対応系統一覧」を参照。テスト53件全パス。
変更履歴は [CHANGELOG.md](CHANGELOG.md) を参照。

## License

MIT License — [LICENSE.md](LICENSE.md) を参照。
