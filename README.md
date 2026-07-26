# Legacy Japanese BBS Archival Preprocessing Toolkit（仮）

1999〜2002年頃の日本語BBS過去ログ（あやしいわーるど等）を対象とした、
デジタル文化資産の前処理基盤。

## 製作方針

速く、軽く、確実に。

## 最上位原則

アーカイブは弄らない。
利用者の利益最大。

詳細は [spec/principles.md](spec/principles.md) を参照。

## 仕様

- [spec/principles.md](spec/principles.md) — 設計原則
- [spec/parser-api.md](spec/parser-api.md) — Parser API仕様
- [spec/intermediate.schema.json](spec/intermediate.schema.json) — IR（中間表現）スキーマ
- [spec/misuse-cases.md](spec/misuse-cases.md) — 想定される誤用ケース
- [spec/glossary.md](spec/glossary.md) — 用語集

## 実装

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

Phase 3（Implementation）：zantei20070218形式（あやしいわーるど＠暫定系列）向け
Parserを実装・検証済み。IR全件のJSON Schema検証通過確認済み。

## License

MIT License — [LICENSE.md](LICENSE.md) を参照。
