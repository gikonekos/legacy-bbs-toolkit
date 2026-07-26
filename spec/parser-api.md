# Parser API

## Detection

Derived from: Selectable Specification

契約:
- Parserは対応可否を真偽値として返さなければならない
- 確信度（Capability）は任意で追加報告できる
- 確信度の有無や値はSelectionの契約に影響しない

## Selection

Derived from: Archive First / Selectable Specification / Separation of Specification and Implementation

契約:
- 同一入力・同一Parser集合に対し常に同じParserを選ぶ（決定性）
- 複数対応可能でも最終的に一つだけ選ぶ
- 利用者は自動選択結果を、明示的に指定した単一の代替Parserへの置き換え
  として上書きできる（unless the user explicitly overrides the selection）
- 何を根拠に選ぶかはResolution Policyの責務とする

## Resolution Policy

Derived from: Selectable Specification

契約:
- 複数の比較基準が利用可能な場合であっても、適用順序は決定的でなければ
  ならない
- 具体的にどの判定情報をどの順序で用いるかは、本仕様では定めない

実施要項（任意・非拘束、別ファイル想定）:
- 既定の推奨実装: 1. confidence比較 → 2. priority比較 → 3. 登録順

## User Override

Derived from: Selectable Specification, Separation of Specification and Implementation

契約:
1. 利用者は、Selectionが自動決定したParserを、明示的に指定した単一の
   代替Parserへの置き換えとして上書きできる
2. User Override有効時、Resolution Policyによる比較は適用されない
3. Overrideで指定されたParserがDetectionにおいて対応不可（false）を
   自己申告した場合、そのOverrideはエラーとして拒否される
   （Detectionの結果はParser自身が宣言する能力の契約であり、
   User Overrideによってこれを無効化してはならない）
4. 処理開始時点において、有効なOverrideは高々1つである。複数の指定
   手段からどのように1つに決定されるかは本仕様では定めない
5. Overrideの具体的な指定手段自体もImplementationの裁量とする
6. Overrideが行われた事実は、Provenanceに記録されなければならない

## Provenance

Derived from: Archive First, Separation of Specification and Implementation

契約:
1. 各処理対象について、最終的なParserの選択結果と、その選択経路
   （Selectionによる自動決定か、User Overrideによる明示的指定か）を
   記録しなければならない
2. 選択経路がSelection（自動決定）による場合、Resolution Policyが
   どの比較基準によって確定に至ったかを記録しなければならない
3. User Overrideが行われた場合、Override前のSelection結果を含め、
   選択経路が検証可能となる情報を記録しなければならない
4. Provenanceは、記録内容が事後に検証可能でなければならない
5. 保存形式・改訂方式（上書き禁止・追記のみ許可等）は、本契約の
   範囲外とする（意図的な保留。仕様策定の途中で上書きルールを
   固定するとコスト過多になるため、Phase 2完了後に別途検討する）

## Parser Plugin Namespace

契約:
- Parserプラグインは、一意な識別子を持たなければならない
- レジストリはプラグイン登録時に名前空間の一意性を検証しなければ
  ならない
- 重複する名前空間の登録は拒否しなければならない

実施要項（任意・非拘束）:
- 推奨形式: `legacy-bbs-toolkit.parser.<name>`
- Python entry_pointsグループ: `legacy_bbs_toolkit.parsers`

## Timestamp Handling

契約:
1. 元のタイムスタンプ文字列は、変更せず保存しなければならない
2. タイムゾーンが暗黙的である場合、変換時に前提としたタイムゾーンを
   UTCオフセット形式（例: +09:00）でProvenanceに記録しなければならない
3. 既定値として前提とする具体的なタイムゾーンは、本仕様の範囲外とし
   実施要項に委ねる

実施要項（任意・非拘束）:
- 推奨既定値: Asia/Tokyo

※ 本節のファイル配置（parser-api.md内に置くか、別ファイルに分離するか）
は編集上の保留（未確定）。

## Non-Guarantees

1. Detectionが対応可能（true）と自己申告したことは、実際の解析結果の
   正確性を保証しない
2. Provenanceに記録された選択経緯は、解析結果自体の妥当性・正当性を
   保証するものではない
3. 破損・欠損したアーカイブデータの修復を保証しない
