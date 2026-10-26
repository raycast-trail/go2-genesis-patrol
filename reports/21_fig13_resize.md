# T21 報告: レポート最終版(表現の修正・図の配置、12 ページ)の反映

## 受け入れ条件の判定

| 条件 | 判定 | 根拠 |
|---|---|---|
| コミット・タグの付け直し・push 済み、個人情報 0 件、`gh` は元のアカウント | ✅ | main とタグがどちらも `e6b2c03` を指す。検査は 0 件。元のアカウントが active |
| 公開 PDF(main・タグ)の md5 = `6b4d42c394ec27e3dd7849b9f9d4acff` | ✅ | ログインなしで取得した 2 つとも一致 |
| `reports/21_fig13_resize.md` | ✅ | 本ファイル |

## 実施内容

- 手元の `docs/report/report.pdf` の md5 が `6b4d42c394ec27e3dd7849b9f9d4acff` であることを確かめた(12 ページ、Author なし)。`git diff --stat` で、変更は `report.html`・`report.pdf` の 2 つだけだった
- `e6b2c03` T21: report final wording and layout (12 pages)。中身を変えずにコミットした。人間の指示で `tasks/21_fig13_resize.md` も同じコミットに含めた。未追跡の `videos/t01_square_baseline.mp4` は含めていない
- 個人情報の検査:

  | 検査 | 結果 |
  |---|---|
  | `$PII_PATTERN`(旧表記・旧動画 ID を含む)で全追跡ファイルを `grep -a -i` | 0 件 |
  | 括弧と `\` を除いた形での氏名の断片 | 0 件 |
  | PDF の本文 | 0 件 |
  | PDF の Author | なし |

- タグの付け直し: 旧タグを削除 → `git push origin main`(`b9bffdf..e6b2c03`)→ `git tag -f -a v1.0-submission …` → `git push origin v1.0-submission`。push の前だけ raycast-trail に切り替え、終わったら元のアカウントに戻した

## ログインなしでの確認

| 確認 | 結果 |
|---|---|
| `/tags` | `v1.0-submission` → `e6b2c035186d1a3c138312922ecab79a086f30a0` |
| main の生の `docs/report/report.pdf` | HTTP 200、md5 `6b4d42c394ec27e3dd7849b9f9d4acff` |
| タグの生の `docs/report/report.pdf` | HTTP 200、md5 `6b4d42c394ec27e3dd7849b9f9d4acff` |
| README | 公開中の生ファイルのハッシュ `ebd5f91` が、ひとつ前の main と同じ(変化なし) |

本報告は、タグの後のコミットとして main に追加した。旧リポジトリには触れていない。
