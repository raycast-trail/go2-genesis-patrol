# T19: 公開する表記を Omnicampus アカウント ID「3164」に切り替える

## 背景と方針
Omnicampus の **アカウント ID は `3164`**、アカウント名は旧表記(以下「旧表記」と書く。`git grep` で `$OLD_NAME_PATTERN` にヒットするもの)である。旧表記は個人名を含むため、要項の注記「個人名をアカウント名に使用している方は、アカウント ID をタイトルにご活用ください」に従い、**公開されるすべての場所の表記を `3164` にする**。

- 動画タイトル: `PAI最終課題_3164`
- 動画ファイル: `videos/final/PAI最終課題_3164.mp4`
- リポジトリ内のレポート: `docs/report/report.pdf`(中立な名前。中身の表記も 3164)
- Omnicampus に提出する PDF は要項どおりのファイル名(旧表記入り)にするが、**これはリポジトリに入れない**(人間が手元で用意する)
- 履歴からも旧表記を除く(T16 と同じ要領)。タグ `v1.0-submission` は付け直す

この作業は **人間の操作(YouTube への再アップロード)を挟んで 2 段階**で行う。

---

## 段階 A: 動画の作り直し(ここで止まる)
1. `scripts/make_cards.py`・`scripts/make_video.py` の旧表記を `3164` に置き換える(タイトルカード C0 の表記、出力ファイル名)。ほかのカード・バナーに旧表記があれば同様に
2. カードと動画を再生成: 出力は `videos/final/PAI最終課題_3164.mp4`。構成・長さは T17 と同じ(約 168.8 s)。余白検査、コンタクトシート `results/t10_contact.png` を更新
3. 旧ファイル `videos/final/` の旧表記の mp4 は作業フォルダから削除(`git rm`)
4. 検査: 生成物(カード画像、動画のコンタクトシート)を目視し、旧表記が画面に出ていないこと
5. **コミットも push もせずに止まり**、人間に次を依頼して待つ:「`videos/final/PAI最終課題_3164.mp4` を YouTube(Raycast Trail チャンネル)にタイトル `PAI最終課題_3164` でアップロードし、URL を知らせてください」

## 段階 B: 人間が URL とレポートを用意したあと
人間が「完了」と新しい URL を伝え、`docs/report/report.pdf` と `docs/report/report.html`(表記 3164・新 URL に更新済み)を置いたら再開する。
1. **作業フォルダの整理**
   - `docs/report/` の旧表記のファイル名の PDF を `git rm`(新しい `report.pdf` が置かれていることを確認してから)
   - README: 旧表記と旧 URL をすべて置き換える。動画は新 URL(英語の行、サムネイルリンク、日本語の「提出動画」)、レポートは `docs/report/report.pdf`、「提出ファイル名・動画タイトル」の行は「動画タイトル: `PAI最終課題_3164`(Omnicampus アカウント ID)」に
   - `tasks/`・`reports/` の旧表記は `3164` に置換(ファイル名の言及は新しいファイル名に)
   - `git grep -n -E "$OLD_NAME_PATTERN"` が 0 件、旧動画 ID も 0 件
2. 1 コミット(作者は `git config --local` の raycast-trail)
3. **履歴の書き換え**(T16 と同じく別クローンで `git filter-repo`):
   - `--replace-text`: 旧表記 → `3164`、旧動画 ID → 新動画 ID。`--replace-message` も
   - `--path-rename`: 旧表記の PDF のパス → 削除扱いでよい(古い版は blob ごと除く)。旧表記の mp4 も同様
   - **旧表記が画像として焼き込まれた古い版の blob を除く**: `figs/cards/C0*.png`、`videos/final/*.mp4`、`results/t10_contact.png`、`docs/report/*.pdf` の **HEAD 以外の全バージョン**(`--strip-blobs-with-ids`)
   - 検証: 全リビジョンで `git grep -I -E "$OLD_NAME_PATTERN|$OLD_VIDEO_ID"` が 0 件、`git log --all --format=%B` も 0 件、作者は raycast-trail のみ、`git rev-list --all --objects | grep -E "\.(pdf|mp4)$"` で PDF は `docs/report/report.pdf` の 1 つ、mp4 の final は新ファイル名の 1 つだけ(raw の mp4 は除く)
   - ツリーのハッシュが手順 2 のコミットと一致すること
4. 作業フォルダの `.git` を書き換え済みのものに差し替え(T16 手順 3 と同じ。直前に `.git` のバックアップを `../go2-genesis-patrol_backup_t18_git/` に取る)。remote と `git config --local` を再設定
5. **公開リポジトリへの反映**(push の前だけ `gh auth switch -u raycast-trail`):
   - 旧タグをリモートから消す: `git push origin :refs/tags/v1.0-submission`
   - `git push --force origin main`
   - タグを付け直す: `git tag -a v1.0-submission -m "Physical AI 2026 応用編1 最終課題 提出版"` → `git push origin v1.0-submission`
   - 終わったら元のアカウントに戻す
6. **ログインなしでの検証**:
   - README の生ファイルに旧表記と旧動画 ID が無く、新動画 ID がある
   - `https://api.github.com/repos/raycast-trail/go2-genesis-patrol/tags` に v1.0-submission
   - リポジトリのページ・`docs/report/report.pdf` のページが 200
   - コミットのメールは noreply のみ
7. 旧リポジトリには一切触れない

## 受け入れ条件
- [ ] 段階 A: 新しい動画(旧表記なし、C0 は `PAI最終課題_3164`)ができ、人間に依頼して止まった
- [ ] 段階 B: HEAD と全履歴で旧表記・旧動画 ID が 0 件、作者は raycast-trail のみ
- [ ] 公開リポジトリの main とタグ v1.0-submission が新しい履歴を指している
- [ ] `gh` は元のアカウントに戻っている
- [ ] `reports/19_account_id.md`(日本語。旧表記そのものは書かず「旧表記」と書く)

## 調整候補(最大 2 つ)
1. `--strip-blobs-with-ids` で HEAD の版まで消えた場合: 書き換え後に HEAD の版を再コミット
2. force push が保護設定などで拒否された場合: 理由を報告して止める(人間が設定を確認する)
