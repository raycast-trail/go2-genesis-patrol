# T18: 提出版の確定(YouTube URL の記入と v1.0-submission タグ)

## 目的
提出動画を YouTube に公開した(`https://youtu.be/uhSM8Q9onhM`、タイトル `PAI最終課題_3164`)。README の URL のプレースホルダを埋め、人間が更新したレポート(冒頭に動画 URL を記入済み)をコミットし、提出時点の状態に `v1.0-submission` タグを付ける。

## 手順
1. README の「(提出後に URL を記載)」をすべて置き換える:
   - 冒頭の英語の行: `🎬 Full video: [YouTube](https://youtu.be/uhSM8Q9onhM)`
   - 日本語の「提出動画」: `https://youtu.be/uhSM8Q9onhM`
   - 日本語の「レポート」: リポジトリ内の PDF への相対リンク `docs/report/report.pdf`(HTML も同じフォルダ)
   - 冒頭の hero GIF の直下に、YouTube のサムネイル画像から動画へのリンクを 1 つ置く: `[![Full video](https://img.youtube.com/vi/uhSM8Q9onhM/hqdefault.jpg)](https://youtu.be/uhSM8Q9onhM)`(幅が大きすぎる場合は `<a><img width="480"></a>` の HTML で)
   - `grep -n "提出後に URL" README.md` が 0 件になること
2. `docs/report/`(人間が更新した PDF・report.html)は **内容を変えずに** 含める
3. 個人情報の検査(T16 手順 1-6 と同じ grep)が 0 件であること
4. 1 コミット(`T18: submission version (YouTube URL, report final)`)。push の前だけ `gh auth switch -u raycast-trail`
5. 注釈つきタグ `git tag -a v1.0-submission -m "Physical AI 2026 応用編1 最終課題 提出版"` を付けて `git push origin v1.0-submission`。push 後に元のアカウントへ戻す
6. ログインなしで確認: `curl -s https://api.github.com/repos/raycast-trail/go2-genesis-patrol/tags | grep v1.0-submission`、README の生ファイル(`https://raw.githubusercontent.com/raycast-trail/go2-genesis-patrol/main/README.md`)に `uhSM8Q9onhM` が入っていること

## 受け入れ条件
- [ ] README のプレースホルダ 0 件、動画リンクとサムネイルリンクがある
- [ ] `docs/report/` が人間の版のままコミットされている
- [ ] 個人情報の検査 0 件
- [ ] `v1.0-submission` タグが公開リポジトリで見える
- [ ] `gh` が元のアカウントに戻っている、旧リポジトリには触れていない
- [ ] `reports/18_submission.md`(日本語)
