# T18 報告: 提出版の確定(YouTube URL の記入と v1.0-submission タグ)

提出動画: https://youtu.be/uhSM8Q9onhM(タイトル `PAI最終課題_3164`)
提出版のタグ: [`v1.0-submission`](https://github.com/raycast-trail/go2-genesis-patrol/releases/tag/v1.0-submission)(注釈つき。コミット `05fb3ed` を指す)

## 受け入れ条件の判定

| 条件 | 判定 | 根拠 |
|---|---|---|
| README のプレースホルダ 0 件、動画リンクとサムネイルリンクがある | ✅ | `grep -n "提出後に URL" README.md` → 0 件。公開中の README の生ファイルでも 0 件、`uhSM8Q9onhM` を含む行は 3 行 |
| `docs/report/` が人間の版のままコミットされている | ✅ | 作業フォルダの `git hash-object` とタグのツリーの blob が一致(下表) |
| 個人情報の検査 0 件 | ✅ | T16 手順 1-6 の grep → none。PDF の本文(`pdftotext`)も 0 件、Author なし |
| `v1.0-submission` タグが公開リポジトリで見える | ✅ | ログインなしの API `/tags` に出ている。タグのページは 200 |
| `gh` が元のアカウントに戻っている、旧リポジトリには触れていない | ✅ | push の後で元のアカウントが active。push 先は `raycast-trail/go2-genesis-patrol` だけ |
| `reports/18_submission.md`(日本語) | ✅ | 本ファイル |

## README の変更

| 場所 | 変更前 | 変更後 |
|---|---|---|
| hero GIF の直下(新規) | — | `[![Full video](https://img.youtube.com/vi/uhSM8Q9onhM/hqdefault.jpg)](https://youtu.be/uhSM8Q9onhM)` |
| 冒頭の英語の行 | 🎬 Full video: (提出後に URL を記載) | 🎬 Full video: [YouTube](https://youtu.be/uhSM8Q9onhM) |
| 日本語「提出動画」 | `(提出後に URL を記載)` | https://youtu.be/uhSM8Q9onhM |
| 日本語「レポート」 | `(提出後に URL を記載)`(`docs/report/` に PDF・HTML) | [docs/report/report.pdf](../docs/report/report.pdf)(HTML も同じフォルダ) |

サムネイル `hqdefault.jpg` は 480×360(取得して確認: HTTP 200、image/jpeg、8 KB)なので大きすぎない。タスクにある HTML の `width="480"` 指定は使わず、Markdown のまま置いた。

## docs/report/(人間の版をそのままコミット)

人間の変更は `report.html` の 1 行(冒頭の動画 URL)と、それを反映した PDF(3,613,402 → 3,611,062 bytes、12 ページ)。どちらも中身には手を加えていない。

| ファイル | 作業フォルダの `git hash-object` | タグ `v1.0-submission` の blob |
|---|---|---|
| `docs/report/report.html` | `7134e0c` | `7134e0c` |
| `docs/report/report.pdf` | `180351a` | `180351a` |

`report.html` に含まれる YouTube の URL は `youtu.be/uhSM8Q9onhM` だけで、README と一致する。

## 個人情報の検査

```bash
git ls-files -z | xargs -0 grep -a -i -l -E "$PII_PATTERN" || echo "none"
# → none
pdftotext docs/report/report.pdf - | grep -i -c -E "<上の語>|@"
# → 0
pdfinfo docs/report/report.pdf
# Title: 説明資料_PAI最終課題_3164 / Creator: Chromium / Author 行なし
```

## コミット・タグ・push

```bash
git commit -m "T18: submission version (YouTube URL, report final)"      # 05fb3ed
git tag -a v1.0-submission -m "Physical AI 2026 応用編1 最終課題 提出版"
gh auth switch -u raycast-trail
git push origin main                 # bbe77f7..05fb3ed
git push origin v1.0-submission      # * [new tag]
gh auth switch -u <元のアカウント>
```

- コミットの作者・コミッターとタグの tagger は、どれも `raycast-trail <347854740+raycast-trail@users.noreply.github.com>`
- `git ls-remote origin`: `refs/heads/main` = `05fb3ed`、`refs/tags/v1.0-submission` = `47b636d`(タグのオブジェクト)→ `05fb3ed`
- タグに含めたのは T18 の提出版のコミットまで。本報告はタグの後のコミットとして main に追加した(タスクの手順どおり、報告は確定後に書くため)

## ログインなしでの確認

```bash
curl -s https://api.github.com/repos/raycast-trail/go2-genesis-patrol/tags | grep v1.0-submission
#     "name": "v1.0-submission",   (zipball_url / tarball_url も)
curl -s https://raw.githubusercontent.com/raycast-trail/go2-genesis-patrol/main/README.md | grep -c uhSM8Q9onhM
# 3   (サムネイル行・英語の行・日本語の行)
curl -s https://raw.githubusercontent.com/raycast-trail/go2-genesis-patrol/main/README.md | grep -c "提出後に URL"
# 0
curl -s -o /dev/null -w "%{http_code}" https://github.com/raycast-trail/go2-genesis-patrol/releases/tag/v1.0-submission
# 200
curl -s "https://api.github.com/repos/raycast-trail/go2-genesis-patrol/commits?per_page=100" | grep -o '"email": *"[^"]*"' | sort -u
# "email": "347854740+raycast-trail@users.noreply.github.com"
```

push の後の `gh auth status`: 元のアカウントが active、raycast-trail は active でない(ログインは残っている)。

## 変更したファイル

| ファイル | 理由 |
|---|---|
| `README.md` | YouTube URL・サムネイルリンク・レポートへの相対リンク |
| `docs/report/report.html`, `docs/report/report.pdf` | 人間の更新(動画 URL の記入)をそのままコミット |
| `tasks/18_submission.md` | タスク定義(未追跡だったのでコミット) |

## うまくいかなかったこと

特になし。

## 次タスクへの申し送り・人間に残す作業

- 提出版は `v1.0-submission` で固定した。これ以降に main を更新しても、提出時点の状態はタグで参照できる
- GitHub の Release(リリースノート)は作っていない(タスクの範囲外)。必要なら人間が `v1.0-submission` から作成する
- `videos/t01_square_baseline.mp4` は引き続き未追跡のまま
