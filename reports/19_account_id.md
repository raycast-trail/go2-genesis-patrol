# T19 報告: 公開する表記を Omnicampus アカウント ID「3164」に切り替える

本報告では、旧アカウント名の表記を「旧表記」、それを探す正規表現を `$OLD_NAME_PATTERN`、旧動画 ID を `$OLD_VIDEO_ID`、T16 以来の個人情報の検査パターンを `$PII_PATTERN` と書く。どれも実際の語はリポジトリに置かない(ローカルでだけ使う)。

- 新しい動画: https://youtu.be/uhSM8Q9onhM(タイトル `PAI最終課題_3164`)
- 公開リポジトリ: main = `bd91a06`、タグ `v1.0-submission` → `bd91a06`(付け直し)

> 注意: 履歴を再度 `git filter-repo` で書き換えたため、`reports/01〜18` に書かれたコミットハッシュは無効になった。旧報告に書かれたファイル名も、置換で新しい名前(`PAI最終課題_3164.mp4`、`report.pdf`)になっている。

## 受け入れ条件の判定

| 条件 | 判定 | 根拠 |
|---|---|---|
| 段階 A: 旧表記のない新しい動画ができ、C0 が `PAI最終課題_3164`。人間に依頼して止まった | ✅ | 168.8 s。C0 とコンタクトシートを目視。コミット・push せずに止まり、アップロードを依頼した |
| 段階 B: HEAD と全履歴で旧表記・旧動画 ID が 0 件、作者は raycast-trail のみ | ✅ | 下記「履歴の検証」 |
| 公開リポジトリの main とタグ v1.0-submission が新しい履歴を指している | ✅ | `git ls-remote`: main・タグとも `bd91a06` |
| `gh` は元のアカウントに戻っている | ✅ | 元のアカウントが active、raycast-trail は active でない |
| `reports/19_account_id.md`(日本語。旧表記そのものは書かない) | ✅ | 本ファイル(旧表記・旧動画 ID・`$PII_PATTERN` の語はどれも書いていない) |

## 段階 A: 動画の作り直し

| 変更 | 内容 |
|---|---|
| `scripts/make_cards.py` | C0 の表記を `PAI最終課題_3164` に。ほかのカード・バナーには旧表記なし |
| `scripts/make_video.py` | 出力の既定値と docstring を `videos/final/PAI最終課題_3164.mp4` に |
| カード | 画像が変わったのは C0 だけ。`check_margins.py` all OK |
| 動画 | `videos/final/PAI最終課題_3164.mp4`: 168.8 s、1280×720、30 fps、H.264、5.1 MB。T17 と同じ 21 ショット・同じ長さ。メタデータにタイトルのタグなし |
| 旧ファイル | 旧表記の mp4 を `git rm` |

```bash
python scripts/make_cards.py && python scripts/check_margins.py
python scripts/make_video.py --v1-seed28-start 14 --v2-seed28-start 6 --v3-seed28-start 9.7
ffmpeg -i "videos/final/PAI最終課題_3164.mp4" -vf "fps=1/5,scale=320:-1,tile=6x6" -frames:v 1 results/t10_contact.png
```

C0 とコンタクトシートを目視で確認し、画面に旧表記が出ていないことを確かめた。そのうえで、YouTube へのアップロードを人間に依頼して止まった。

## 段階 B

### 1. 作業フォルダの整理

人間が置いた `docs/report/report.pdf`(12 ページ、Title = 説明資料_PAI最終課題_3164、Author なし)と `report.html`(動画 URL は新しいもののみ、旧表記 0 件)は、内容を変えずにコミットした。旧表記のファイル名の PDF は、新しい `report.pdf` があることを確かめてから `git rm` した。

- **README**:
  - 動画は新しい URL にした(英語の行、サムネイルリンク、日本語の「提出動画」)
  - レポートは `docs/report/report.pdf` へのリンクにした
  - 「提出ファイル名・動画タイトル」の行は「動画タイトル: `PAI最終課題_3164`(Omnicampus アカウント ID)」にした
- **tasks/・reports/**: 旧表記は `3164` に置換し、ファイル名の言及は新しい名前にした(下の置換ルール)
- **tasks/19 自身**: 検査パターンが本文にそのまま書かれていて、0 件の検査に自分自身がヒットするため、`$OLD_NAME_PATTERN`・`$OLD_VIDEO_ID` の表記に直した

#### タスク外の追加作業(人間の承認済み)

T16 以来、tasks/16 と reports/16〜18 に載せていた個人情報の検査パターンは `dee[p]…` のような括弧つきの書き方だった。grep にはヒットしないが、**人が読めば氏名の断片・旧アカウント名だと分かる**ことに気づいた。履歴の書き換えをもう一度行う今回が、消すのに最も安い機会なので、着手前に人間に確認し、承認を得て一緒に除いた。

- 検査パターンは `"$PII_PATTERN"` という表記に置き換えた(実際の語はローカルでだけ持つ)
- reports/16・17 の説明文にあった名の語(括弧つき)は「名の語」「メールアドレスの語」という表記に

#### 置換ルール(作業ツリーと filter-repo の `--replace-text` に同じものを使用)

| # | 置換前 | 置換後 |
|---|---|---|
| 1 | reports/16 の説明文「正規表現を(括弧つきのパターン)のように括弧で書き換え」 | 「正規表現を、ファイル自身にはマッチしない書き方に書き換え」 |
| 2〜4 | 括弧つきの検査パターン(3 種類の書き方) | `"$PII_PATTERN"` / `` `$PII_PATTERN` `` |
| 5〜7 | 名の語を括弧つきで挙げていた説明文(3 か所) | 「メールアドレスの語」「名の語(旧表記を除く)」「旧表記以外の名の語」 |
| 8 | `docs/report/説明資料_PAI最終課題_<旧表記>.pdf` | `docs/report/report.pdf` |
| 9 | `説明資料_PAI最終課題_<旧表記>.pdf` | `report.pdf` |
| 10 | 旧表記 | `3164` |
| 11 | 旧動画 ID | `uhSM8Q9onhM` |

作業ツリーの検査(コミット前):

| 検査 | 結果 |
|---|---|
| `git grep -n -E "$OLD_NAME_PATTERN"` | 0 件 |
| `git grep -n "$OLD_VIDEO_ID"` | 0 件 |
| 括弧と `\` を取り除いた「人が読める形」で、氏名・旧アカウント名・所属の語を全追跡テキストから検索(scratchpad のスクリプト) | 0 件 |
| `git ls-files -z \| xargs -0 grep -a -i -l -E "$PII_PATTERN"`(名の語は大文字小文字を区別しない) | none |
| 全 mp4・png・gif・jpg・pdf・mcap・pt・pkl を `strings` で同じ語と旧動画 ID について | 0 件 |

### 2. コミット

`2c4b877`(書き換え後は `bd91a06`)T19: switch public identifier to Omnicampus account ID 3164 (video, report, docs)。作者は `git config --local` の raycast-trail。

### 3. 履歴の書き換え

```bash
git clone --no-local go2-genesis-patrol go2-genesis-patrol_anon
cd go2-genesis-patrol_anon
git filter-repo --replace-text t19_replace.txt --replace-message t19_replace.txt --strip-blobs-with-ids t19_strip_ids.txt
```

- 作者は T16 で raycast-trail だけになっていたので、mailmap は使っていない
- `--path-rename` は使わなかった。旧表記のファイル名の PDF と mp4 は、全バージョンが HEAD 以外の blob なので、`--strip-blobs-with-ids` で除くとパスごと履歴から消える(タスクの「削除扱いでよい」に該当)
- コミットメッセージの旧表記 2 件(旧 T10・T08 の本文にあった動画のファイル名)は `--replace-message` で置換した

#### 除いた blob(7 個。HEAD の版は残した)

| パス | 除いた数 | HEAD |
|---|---|---|
| `docs/report/説明資料_PAI最終課題_<旧表記>.pdf` | 2(全バージョン) | なし(パスごと消えた) |
| `videos/final/PAI最終課題_<旧表記>.mp4` | 2(全バージョン) | なし(パスごと消えた) |
| `figs/cards/C0.png` | 1 | 残した |
| `results/t10_contact.png` | 2 | 残した |
| `docs/report/report.pdf`、`videos/final/PAI最終課題_3164.mp4` | 0 | HEAD の 1 版のみ |

調整候補 1(HEAD の版の再コミット)は不要だった。

#### 履歴の検証(書き換え後)

| 検証 | 結果 |
|---|---|
| 全リビジョンで `git grep -I -E "$OLD_NAME_PATTERN\|$OLD_VIDEO_ID"` | 0 件 |
| `git log --all --format=%B` の同じ検索 | 0 |
| 作者・コミッター(`sort -u`) | `raycast-trail <347854740+raycast-trail@users.noreply.github.com>` の 1 行 |
| `git rev-list --all --objects \| grep -E "\.(pdf\|mp4)$"`(raw と videos/t* を除く) | `docs/report/report.pdf` と `videos/final/PAI最終課題_3164.mp4` の 2 つだけ |
| 全 blob をバイナリ込みで `grep -a -i`(旧表記・旧動画 ID・`$PII_PATTERN` の語・括弧つきの書き方・所属の語) | 0 件 |
| 除いた 7 blob の残存 | 0 |
| ツリーのハッシュ(手順 2 のコミット vs 書き換え後の HEAD) | どちらも `a809385…`(一致) |
| コミット数 | 23 |

### 4. 作業フォルダの切り替え

```bash
cp -a .git ../go2-genesis-patrol_backup_t18_git/.git     # 書き換え前の .git(HEAD 2c4b877)
rm -rf .git && mv ../go2-genesis-patrol_anon/.git .git && rm -rf ../go2-genesis-patrol_anon
git tag -d v1.0-submission            # 書き換えで移った旧タグ(付け直すので削除)
git remote add origin https://raycast-trail@github.com/raycast-trail/go2-genesis-patrol.git
git config --local user.name raycast-trail
git config --local user.email 347854740+raycast-trail@users.noreply.github.com
git config --local http.postBuffer 524288000
```

`git status` は `videos/t01_square_baseline.mp4`(未追跡)のみ。

### 5. 公開リポジトリへの反映

```bash
gh auth switch -u raycast-trail
git push origin :refs/tags/v1.0-submission     # - [deleted] v1.0-submission
git push --force origin main                   # + 58b3b4f...bd91a06 main -> main (forced update)
git tag -a v1.0-submission -m "Physical AI 2026 応用編1 最終課題 提出版"
git push origin v1.0-submission                # * [new tag]
gh auth switch -u <元のアカウント>
```

force push は拒否されなかった(調整候補 2 は不要)。

### 6. ログインなしでの検証

| 確認 | 結果 |
|---|---|
| README の生ファイル: 旧表記・旧動画 ID | 0 行 |
| README の生ファイル: 新しい動画 ID | 3 行(サムネイル行・英語の行・日本語の行) |
| `api.github.com/.../tags` | `v1.0-submission`、sha `bd91a06…` |
| リポジトリのページ | 200 |
| `docs/report/report.pdf` のページ | 200 |
| 旧表記のファイル名の PDF のページ(main) | 404 |
| コミットのメール | `347854740+raycast-trail@users.noreply.github.com` のみ(23 件) |
| contributors | raycast-trail のみ |

## 未解決: 書き換え前のコミットが SHA の直接指定でまだ見える

書き換え前の旧 main(`58b3b4f`)は、`https://api.github.com/repos/raycast-trail/go2-genesis-patrol/commits/58b3b4f…` で**まだ 200 が返る**(ログインなし)。GitHub は、どのブランチ・タグからも参照されなくなったコミットをすぐには削除しない。そのため、SHA を知っている人は、旧表記を含む T16〜T18 の版(旧 PDF・旧動画・括弧つきの検査パターン)を見られる。ブランチ・タグ・README・ファイル一覧からはたどれない。

対処の候補(人間の判断):

1. **リポジトリを作り直す**(Settings で削除 → 同じ名前で空のリポジトリを作成 → 今の履歴を push)。旧オブジェクトは確実に消える。スター・トピック・説明・Social preview は設定し直しになる
2. GitHub Support に、参照されなくなったコミットの削除(キャッシュの除去と GC)を依頼する。リポジトリはそのまま残せるが、時間がかかる

なお、T16 以前のコミット(旧アカウント時代)はこのリポジトリに push したことがないので、ここには存在しない。

## 変更したファイル

| ファイル | 理由 |
|---|---|
| `scripts/make_cards.py`, `scripts/make_video.py` | 表記 3164、出力ファイル名 |
| `figs/cards/C0.png`, `results/t10_contact.png` | 再生成 |
| `videos/final/PAI最終課題_3164.mp4`(新規)、旧表記の mp4(削除) | 動画の作り直し |
| `docs/report/report.pdf`(新規)、`docs/report/report.html`、旧表記の PDF(削除) | 人間が用意した版をそのまま |
| `README.md` | 新しい URL、レポートのリンク、動画タイトルの行 |
| `tasks/08〜18`、`reports/08〜18` | 置換ルールの適用 |
| `tasks/19_account_id.md` | タスク定義(検査パターンを `$OLD_NAME_PATTERN` 等の表記に) |

## うまくいかなかったこと

- 上記のとおり、書き換え前のコミットが GitHub 上で SHA の直接指定によりまだ取得できる。こちらからは消せない

## 次タスクへの申し送り・人間に残す作業

- **旧コミットの扱いを決める**(上の候補 1 か 2)。作り直す場合は、push は今の作業フォルダから `git push -u origin main` と `git push origin v1.0-submission` でよい
- Omnicampus に提出する PDF(要項どおりのファイル名)は、手元で用意する(リポジトリには入れない)
- 検査パターン `$PII_PATTERN`・`$OLD_NAME_PATTERN` の実際の語は、ローカルの手順メモで管理する(リポジトリには書かない)
- バックアップ `../go2-genesis-patrol_backup_t18_git/`(書き換え前の .git)と `../go2-genesis-patrol_backup_<旧アカウント>/` は旧表記などを含むので、公開しないこと
