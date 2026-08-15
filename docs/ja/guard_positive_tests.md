# ガードの陽性テスト台帳（2026-07-30 起票）

> **由来**: 同日に「書いたガードが発火しない」が 2 件出た
> （水位ガードの死んだ比較 / 検出器の fail-OPEN が KeyError を飲む）。
> これは新しい規律ではなく、**既存の規律（leak_check の「まず FAIL 側を確認してから
> PASS 側を確認」2026-07-28）が新規ガードに適用されていなかった**だけである。
> 規律 17 の走査対象に「ガード・検査を追加する箇所」を加え、本台帳で管理する。
>
> **原則: ガードを足したら、発火する側のテストを先に通す。発火を見ていないガードは
> 存在しないものとして扱う。**

## 走査結果（2026-07-30。発火側の確認状況）

| ガード | 発火の確認 | 方法 |
|---|---|---|
| offsite_freshness: stale | ✅ | 実運用で発火（incierge 未 push） |
| offsite_freshness: blocked (transcripts) | ✅ | 実運用で発火 |
| offsite_freshness: views-registry（未登録派生物） | ✅ | 陽性テスト（未登録ファイル設置） |
| offsite_daily: 再試行ゲート stale 側 | ✅ | 実測（rc=1 で即実行） |
| offsite_daily: gap (rc=3) 側 | ✅ | 実測（skip に従う） |
| data_backup: 母集団 読み戻し照合 NG | ✅ | 実運用で発火（metrology→views 移動時） |
| data_backup: tar 失敗 | ✅ | 陽性テスト（RUNTIME_DATA_ROOT=/nonexistent） |
| transcript_backup: SRC 不在 (exit 2) | ✅ | 陽性テスト |
| burn_population_rate: 水位ガード | ✅ | 陽性テスト（水位改変 → 500 件損失を検出） |
| burn_population_rate: require_registered | ✅ | 陽性テスト（conf から 1 行除去） |
| burn_population_rate: verify_hook_patterns | ✅ | 陽性テスト（別 regex の hook を注入） |
| burn_population_rate: Quantity 単位不一致 | ✅ | 陽性テスト（record vs session → ValueError） |
| feasibility_scan: 閾値正本が読めない → SystemExit | ✅ | 陽性テスト（凍結ファイル退避） |
| check_feature_side: 検査5 FAIL | ✅ | 陽性テスト（初回発話に経過時間を注入） |
| check_feature_side: 検査6 FAIL | ✅ | 陽性テスト（完全分離特徴 AUROC 1.0） |
| credential_exposure hook: 検出 | ✅ | 陽性テスト（AKIA 文字列） |
| credential_exposure hook: fail-closed (rc=2) | ✅ | 陽性テスト（パターン正本を破壊） |

## 未検証（発火を一度も見ていない。**存在しないものとして扱う**）

| ガード | 理由 |
|---|---|
| transcript_backup: VERIFY_FAILED (exit 4) 集合照合 | 発火には tar と find の**間**に変更を挟む必要があり、単体では再現しにくい |
| data_backup: 読み戻し DL 失敗 | upload 成功 → DL 失敗 の順が必要で、ネットワーク断の注入が要る |
| data_backup: 実行時データ側の sha 不一致 | 同上（転送破損の注入） |
| burn_population_rate: rc=3（走査対象が空）/ rc=4（TRIGGER 0 件） | 実データを退避すれば試せるが未実施 |
| triage / locate: root 不在 (rc=2) | 軽微。未実施 |

## 追記（2026-08-09 / S009 Verify。arm-F 検査器の赤側対照）

> S027 教訓「検査器には偽陽性の対照も要る」の適用。緑の記録だけだった点は
> Review 周1 P2 が指摘 (対照実験の未実施・未記録)。以下は本 sprint で実測した赤側。

| ガード | 発火の確認 | 方法 |
|---|---|---|
| test_armf_artifact: artifact digest 不一致 | ✅ rc=1 | 陽性テスト（scratch 複製の model に 1 byte 注入 → FAIL digest 不一致） |
| test_armf_artifact: 既知応答 id 列不一致 | ✅ rc=1 | 陽性テスト（golden 1 id を 9999 に改変した複製を実行 → FAIL 既知応答 [3]） |
| test_armf_artifact: venv 実在だが sentencepiece 破損 | ✅ rc=1 / loop なし | 陽性テスト（spm 無し python への symlink venv。修理前は無限 re-exec = Review 実測 8 秒 361 回。修理後は 1 回で fail-closed） |
| build_measurement_package: pin 済み doc の事後改変 | ✅ rc=1 | 実運用で発火（prereg への Review 追記後、旧 package の `--verify` が mismatch 1 を返した — 「黙って変えられない」が実際に働いた実例） |
| run_armf_eval: evidence md の内容が変わる上書き | ✅ rc=4 | `--force` なし再実行で拒否（fail(4) 経路） |

### 同日追記 (S011。計器① selfsim_probe — 自動検査 `test_selfsim_probe.py` 9 本)

| ガード | 発火の確認 | 方法 |
|---|---|---|
| selfsim_probe: cross-session 近傍の検出 | ✅ 率 ≥0.9 | 陽性テスト (同一テキストを別 session に注入) |
| selfsim_probe: 3 日連続超過 → inbox 外乱注入 item | ✅ | 陽性テスト (fake threshold + 3 点超過) |
| selfsim_probe: 2 日連続では発火しない | ✅ | 偽陽性対照 |
| selfsim_probe: 相異なるテキストで率が低い | ✅ ≤0.05 | 偽陽性対照 |
| selfsim_probe: 窓 < 50 は insufficient rc=2 | ✅ | 陽性テスト (0 件を緑にしない) |
| selfsim_probe: 同日再実行で点も item も増えない | ✅ | 冪等テスト |
| offsite_daily の計器① 配線 | ✅ 実 lane 発火 | 2026-08-09 全経路 run の完了行に「計器①: 本日分は記録済み (skip)」 |

## 発見（この走査で出た欠陥）

1. **offsite_freshness の `checked==0` 分岐（L194/L207）は到達不能** —
   `checked` は 7 対象で無条件加算されるため常に ≥7。
   将来のリファクタ保険として残すが、**「このガードがあるから安心」とは読めない**。
2. **水位ガードの初版 `if before > len(rows)` は死んだ比較だった** —
   merge は集合の和なので恒偽。ファイル削除では before=0 になり検出不能。
   → 外部の最高水位ファイルに置き換え、両分岐を実測（上表）。
3. **credential_exposure 初版は fail-OPEN が KeyError を飲み、
   何も検出しないまま rc=0 を返していた** — 陽性テストで発覚。fail-closed に変更。
