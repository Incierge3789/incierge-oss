# ARCHITECTURE — 層モデル

```
incierge（器）
├── org-ops/        組織層：複数主体で運用するための配布形・合意機構（accord/opskit）
├── agent-ops/      個人層：自走オペレーション OS（sprint 工程・gate・hook・受入）
│   └── ops-meta/   個人層の編集点：hook / policy / doctrine / schema の正本
├── unk0/           正準状態層：正本（canon）と観測 state の突合エンジン
└── metrology/      計測層：LM スタック（コーパス衛生 → トークナイザ → 極小 LM）
```

## 層の責任分界

- **org-ops（組織層）**: 個人層で成立した運用 OS を、単一機・単一人依存を除去して
  配布可能にする形。合意（agreement）の突合と配布物のパッケージングを持つ。
- **agent-ops（個人層）**: 実行主体。sprint 工程、品質 gate、自走 loop、受入検証。
  運用データ（beads・ログ・トレース）は**この monorepo には持ち込まない**
  （原本は元 repo bundle と実機に残る。ここに入るのはコード・文書層のみ）。
- **ops-meta（個人層の編集点）**: agent-ops が参照する hook・policy・doctrine の正本。
  agent-ops 配下に物理配置することで「編集点は 1 箇所」を器の構造として固定する。
- **unk0（正準状態層）**: 「今の正本は何か」に答える層。canon 承認・staleness 表示・
  観測 repo head の突合。他層から read-only で照会される。
- **metrology（計測層）**: 計測・学習の層。データ本体は git 外
  （計測層のデータ配置規約を参照）。

## 依存方向

org-ops → agent-ops → ops-meta、全層 → unk0（read-only 照会）。
metrology は他層のトレースを git 外パス経由で読むのみで、逆流しない。
