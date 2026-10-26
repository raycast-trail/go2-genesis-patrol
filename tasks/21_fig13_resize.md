# T21: レポート最終版(表現の修正・図の配置)を反映(docs/report のコミットとタグの付け直し)

## 背景
図 13(Foxglove の 3D 表示)を `max-width:78%` → `60%` に縮小し、キャプションごと前のページ(10 ページ目)に収めた。あわせて §13 参考文献の前の改ページを外し、12 ページ目に収めた。さらに誤解をまねく表現の修正(自己位置は真値である旨、経路効率が 1 を超える理由、非決定性の表現など)と、重複・重要度の低い記述の削除を行い、§3 の表はページをまたいで分割(見出し行を繰り返す)、図 2 を 90% に縮小した。総ページ数は 13 → **12**。人間が `docs/report/report.html` と `report.pdf` を差し替え済み(`report.pdf` の md5 は `6b4d42c394ec27e3dd7849b9f9d4acff`)。

## 手順
1. `md5 docs/report/report.pdf` が上の値と一致することを確認。`git diff --stat` で変更が `docs/report/report.html`・`report.pdf` の 2 つだけであること(未追跡の `videos/t01_square_baseline.mp4` は含めない)
2. 2 ファイルを **中身を変えずに** 1 コミット(`T21: report final wording and layout (12 pages)`)
3. 個人情報の検査(`$PII_PATTERN`、T16・T19・T20 と同じ)が 0 件
4. タグ `v1.0-submission` を付け直す(T20 と同じ手順): push の前だけ `gh auth switch -u raycast-trail` → `git push origin :refs/tags/v1.0-submission` → `git push origin main` → `git tag -f -a v1.0-submission -m "Physical AI 2026 応用編1 最終課題 提出版"` → `git push origin v1.0-submission` → 元のアカウントに戻す
5. ログインなしで確認: タグがこのコミットを指す、main とタグの生の `docs/report/report.pdf` の md5 が上の値と一致、README に変化なし
6. 旧リポジトリには一切触れない

## 受け入れ条件
- [ ] コミット・タグ付け直し・push 済み、個人情報 0 件、`gh` は元のアカウント
- [ ] 公開 PDF(main・タグ)の md5 = `6b4d42c394ec27e3dd7849b9f9d4acff`
- [ ] `reports/21_fig13_resize.md`(日本語、短く)
