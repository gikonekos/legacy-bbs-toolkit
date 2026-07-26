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
- [spec/misuse-cases.md](spec/misuse-cases.md) — 想定される誤用ケース
- [spec/glossary.md](spec/glossary.md) — 用語集

## 状態

Phase 1（Design Principles）：完了・凍結済み。

Phase 2（Specification）：コア仕様は概ね確定。Parser Plugin NamespaceおよびTimestamp Handlingの内容を反映済み。DISCLAIMER.md / ETHICS.mdは未着手、Provenance保存形式・改訂方式、Timestamp Handlingの配置先、glossary更新は意図的保留事項。

## License

MIT License — [LICENSE.md](LICENSE.md) を参照。
