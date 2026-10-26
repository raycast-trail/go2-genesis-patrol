# T20 報告: レポートの最終修正の反映(図 11 の再作図とタグの付け直し)

## 受け入れ条件の判定

| 条件 | 判定 | 根拠 |
|---|---|---|
| 段階 A: 図 11 の四辺の文字が切れていない、数値は T12 と同じ、止まって人間に伝えた | ✅ | 下の画像。余白は上 32・下 36・左 33・右 32 px。数値は下表。コミットせずに止まった |
| 段階 B: コミット・タグの付け直し・push 済み、個人情報 0 件、`gh` は元のアカウント | ✅ | main とタグがどちらも `3f274f4` を指す。検査は 0 件。元のアカウントが active |
| `reports/20_report_fixes.md` | ✅ | 本ファイル |

## 段階 A: 図 11(`results/t12_lidar3d_test.png`)

`eval/lidar3d_test.py` の作図部分だけを直した(計算は変えていない)。

- 図の大きさを `figsize=(15, 5)` から `(15, 5.6)` に
- 極座標 2 枚のタイトルに `pad=18`(目盛りの 0° と重ならないように)
- 保存を `fig.savefig(args.out, dpi=130, bbox_inches="tight", pad_inches=0.25)` に(下端の 180° が切れないように)

```bash
python eval/lidar3d_test.py --backend cpu --mode 3d --out results/t12_lidar3d_test.png
```

![lidar3d](../results/t12_lidar3d_test.png)

| 方向 | 2D スキャン [m] | 3D 投影 [m] | T12 |
|---|---|---|---|
| 正面(低い箱) | 5.00 | 1.34 | 同じ |
| 右(テーブルの縁) | 5.00 | 1.79 | 同じ |
| 左(高い箱) | 1.50 | 1.50 | 同じ |

3 m 以内の分類別の点数(凡例): 地面 354・胴体帯 26・頭上 3・自機 65。T12 の図と同じ。3D の追加コストは今回 +0.89 ms/step(T12 は +0.67〜0.75)。実行時間の計測値なので回ごとに揺れる。

1970×750 px の画像を目視し、四辺に文字の切れがないこと、上端に切れ端がないこと、凡例が点群に重ならないことを確かめた。

## 段階 B: コミットとタグ

`3f274f4` T20: report final fixes (refs, page numbers, figures) and fig 11 redraw(作者 raycast-trail)。人間が置いたファイルは中身を変えていない。

| ファイル | 内容 |
|---|---|
| `docs/report/report.pdf`(13 ページ)、`report.html` | 人間の最終版(表の右罫線、ページ番号、参考文献 18 件と引用番号、図 2・図 6・図 11) |
| `docs/report/figs/astar_explain.png`(更新)、`lidar3d_test.png`(新規。`results/t12_lidar3d_test.png` と同一)、`traj_t03_seed0_crop.png`(新規) | 人間の版 |
| `scripts/make_astar_explain.py` | 人間の版(1 行の変更) |
| `eval/lidar3d_test.py`、`results/t12_lidar3d_test.png` | 段階 A |
| `tasks/20_report_fixes.md` | タスク定義 |

個人情報の検査:

| 検査 | 結果 |
|---|---|
| `$PII_PATTERN`(旧表記・旧動画 ID を含む)で全追跡ファイルを `grep -a -i` | none |
| 括弧と `\` を除いた形での氏名の断片 | 0 件 |
| PDF の本文(`pdftotext`) | 0 件 |
| PDF の Author | なし |
| 新しい PNG の `strings` | 0 件 |

```bash
gh auth switch -u raycast-trail
git push origin :refs/tags/v1.0-submission     # - [deleted]
git push origin main                           # f0a444c..3f274f4
git tag -a v1.0-submission -m "Physical AI 2026 応用編1 最終課題 提出版"
git push origin v1.0-submission                # * [new tag]
gh auth switch -u <元のアカウント>
```

## ログインなしでの確認

| 確認 | 結果 |
|---|---|
| `/tags` | `v1.0-submission` → `3f274f4` |
| `docs/report/report.pdf` | ページ 200、生ファイル 200(3,622,873 bytes) |
| README | 公開中の生ファイルのハッシュ `ebd5f91` が、ひとつ前の main と同じ(変化なし) |
| コミットのメール | noreply のみ |

本報告は、タグの後のコミットとして main に追加した。
