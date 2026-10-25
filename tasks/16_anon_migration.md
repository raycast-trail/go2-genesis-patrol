# T16: 匿名アカウント raycast-trail への移行(内容の最終修正 + 履歴の書き換え + 新リポジトリへの push)

## 目的
講義課題として匿名性を担保するため、リポジトリを新しい GitHub アカウント **`raycast-trail`**(GitHub Pro、メール非公開)の **`raycast-trail/go2-genesis-patrol`(public)** に作り直す。旧リポジトリ `<旧アカウント>/go2-genesis-patrol` は Transfer しない(転送リンクで 2 つのアカウントが結びつくため)。旧リポジトリの削除は人間が行う。

- 新しい作者: `raycast-trail <347854740+raycast-trail@users.noreply.github.com>`(作者・コミッターとも)
- 表記 `3164` は Omnicampus のアカウント ID なので**変えない**(動画タイトル・ファイル名・カード・レポート)
- `docs/report/` は人間が更新済み(レポート v3.7、URL は raycast-trail)。**内容を変えずに**コミットする

## 手順

### 0. バックアップ(最初に)
- リポジトリのフォルダ全体(`.git`、`logs/`、未追跡ファイルを含む)を、隣に `go2-genesis-patrol_backup_<旧アカウント>/` としてコピーする。これはローカル専用で、どこにも push しない

### 1. 内容の最終修正(旧履歴の上で通常どおり行う)
1. **構成図**: `scripts/make_arch.py` は人間が「最終形 v3 のみ」の層構造図に書き換え済み。`python scripts/make_arch.py` で `figs/arch.png` を再生成し、ヒラギノでラベルが重ならないか目視(重なる場合のみ fontsize を微調整)。`scripts/check_margins.py` を通す
2. **カードの文言**(`scripts/make_cards.py`)。v1・v2 は「改良の途中経過」ではなく「v3 と比べる対象(地図なしの反応的回避)」という位置づけに変わった
   - **C5**: タイトル「5. 比較: 地図なし(v1・v2)と地図あり(v3)」、本文 3 行「v1 反応的回避: 正面の障害物で振動(成功 91%)」「v2 + コミット区間: 抜けるが遠回り(96%、経路効率 0.81)」「v3 地図による経路計画: 速さと確実さを両立(100%、所要 24.2 s、経路効率 1.05)」
   - **C6**: コードの URL を `github.com/raycast-trail/go2-genesis-patrol` に
   - ほかのカード・バナーで「改良」「系統的改良」「占有格子 + A*」と書いている箇所を grep し、「比較」「地図による経路計画(占有格子 + A*)」の言い方にそろえる(数値は変えない。余白検査が通る長さに)
3. **動画の再生成**: `python scripts/make_video.py`(T14 と同じ引数)で `videos/final/PAI最終課題_3164.mp4` を上書き。ショット構成・長さは T14 と同じ(差し替えはショット 2 の構成図とカードの文言のみ)。`results/t10_contact.png` を更新
4. **README**(v3 を主役、v1・v2 は比較対象に)
   - 日本語の概要文を次の趣旨に書き換える:「…ナビゲーション層の中心は、LiDAR で描いた占有格子地図の上で A* により経路を引き直す地図による経路計画(v3)。乱数配置の 45 シーンで巡回成功率 9% → 100%、接触率 91% → 0%。地図の効果を切り分けるため、地図を持たない反応的回避 2 種(v1・v2)と比較した…」。「(Physical AI 2026 応用編1 最終課題)」と提出用の行(動画・レポート・`PAI最終課題_3164`)は残す
   - 英語要約の 2 項目目を次に差し替える: "The final navigation layer plans on an occupancy grid built from LiDAR and replans with A* every second; ablations against two map-free reactive controllers (v1, v2) show it reaches 100% patrol success with zero contacts over 45 randomized scenes (vs 9% without avoidance) and finishes 3–6 s faster (median, p < 0.0001)."
   - 構成図の説明を「最終形 v3 の層構造」に。v1/v2/v3 の表は「比較」の見出しで残す
   - 旧アカウント名を含むリンク・記述が残っていないこと(手順 1-6 の grep で確認)
5. **CLAUDE.md**: git の規則を次に置き換える:「このリポジトリのコミットはリポジトリ固有の設定 `user.name = raycast-trail`、`user.email = 347854740+raycast-trail@users.noreply.github.com` で行う(`git config --local`)。グローバル設定は変えない。push の前に `gh auth switch -u raycast-trail`、終わったら元のアカウントに戻す」
6. **ファイルの中身の検査**(HEAD の全追跡ファイル、バイナリ含む):
   ```bash
   git ls-files -z | xargs -0 grep -a -i -l -E "$PII_PATTERN" || echo "none"
   ```
   ヒットしたら内容を確認して除去する(`tasks/` `reports/` の 旧アカウント名は `raycast-trail` に置換してよい)。ほかに:
   - mp4・gif・png のメタデータ(`ffprobe -show_format`、`exiftool` があれば)にユーザー名・ホスト名・位置情報がないこと。`videos/raw/foxglove_3d_seed103.mp4` は QuickTime 由来なので特に確認し、あれば `-map_metadata -1` で作り直す
   - `results/mcap/*.mcap`、`checkpoints/**`(`.pt`、`.pkl`)を `strings` で上の語・ホームディレクトリのパス・ホスト名が無いか確認
   - PDF は `pdfinfo` で Author が空であること
7. ここまでを旧履歴の上で 1 コミットにする(作者はまだ旧設定でよい。手順 2 で書き換わる)。`docs/report/`(PDF・HTML・`figs/` の新規 3 枚)、`scripts/make_astar_explain.py`・`make_evolution.py`・`make_rl_explain.py` を含める。`videos/t01_square_baseline.mp4` は含めない。**この時点では push しない**

### 2. 履歴の書き換え(新しいクローンで)
`git filter-repo` を使う(無ければ `pip install git-filter-repo` または `brew install git-filter-repo`)。
```bash
cd ..
git clone --no-local go2-genesis-patrol go2-genesis-patrol_anon
cd go2-genesis-patrol_anon
```
1. **作者・コミッターの置換**: 全コミットの作者・コミッターを `raycast-trail <347854740+raycast-trail@users.noreply.github.com>` に(`--mailmap` または `--name-callback`/`--email-callback`)
2. **テキストの置換**(`--replace-text`): 旧アカウント名 → `raycast-trail`、旧メールアドレス → noreply アドレス。コミットメッセージも対象にする(`--replace-message`)
3. **画像・PDF・動画に旧 URL が焼き込まれた古い版の除去**: 次のパスについて、**HEAD 以外の全バージョンの blob** を `--strip-blobs-with-ids` で履歴から除く(HEAD の版は新しい URL なので残す)
   - `videos/final/*.mp4`、`figs/cards/C6*.png`、`results/t10_contact.png`、`docs/report/*.pdf`、`docs/report/report.html` の古い版はテキスト置換で済むが、PDF は圧縮されているため blob ごと除く
   - blob ID の求め方の例: `git rev-list --all --objects -- <path>` で全バージョンを列挙し、`git rev-parse HEAD:<path>` を除く
4. **検証**(すべて満たすこと):
   ```bash
   git log --all --format='%an <%ae> | %cn <%ce>' | sort -u            # raycast-trail の 1 行だけ
   git rev-list --all | xargs -I{} git grep -I -i -l -E "$PII_PATTERN" {} | head   # 0 件
   git log --all --format=%B | grep -i -c -E "$PII_PATTERN"   # 0
   git rev-list --all --objects | grep -c "\.pdf$"                      # 1(HEAD の版だけ)
   ```
   HEAD の作業ツリーが元のフォルダの HEAD と同一であること(`git diff --stat <元の HEAD>` 相当で比較。ツリーのハッシュが一致すれば可)

### 3. 作業フォルダの切り替え
元のフォルダ(`go2-genesis-patrol/`)の `.git` を、書き換え済みのものに置き換える:
```bash
cd ../go2-genesis-patrol
rm -rf .git && mv ../go2-genesis-patrol_anon/.git .git
git status   # videos/t01_square_baseline.mp4 以外クリーンであること
git remote remove origin 2>/dev/null; git remote -v   # 何も無いこと
git config --local user.name raycast-trail
git config --local user.email 347854740+raycast-trail@users.noreply.github.com
```
`go2-genesis-patrol_anon/` は削除してよい。`go2-genesis-patrol_backup_<旧アカウント>/` は残す

### 4. 新しいアカウントで公開(**人間の操作が 1 回必要**)
1. `gh auth login` を実行し、GitHub.com / HTTPS / ブラウザでログイン を選ぶ。**表示された 8 文字のコードは、raycast-trail でログインしているシークレットウィンドウに入力する**(既定のブラウザは旧アカウントでログイン中なので、そちらで承認しないこと)。ここは人間が行うので、Claude Code はコマンドを案内して待つ
2. `gh auth status` で raycast-trail が追加され active であることを確認。`gh auth setup-git` で git の認証を gh に任せる
3. 公開:
   ```bash
   gh repo create raycast-trail/go2-genesis-patrol --public --source . --remote origin --push \
     --description "Unitree Go2 patrol in Genesis: RL locomotion + 2D/3D LiDAR navigation (occupancy grid + A*), evaluated on randomized scenes. Runs on a Mac."
   gh repo edit raycast-trail/go2-genesis-patrol --add-topic unitree-go2 --add-topic genesis --add-topic reinforcement-learning --add-topic legged-robots --add-topic lidar --add-topic navigation --add-topic occupancy-grid --add-topic foxglove --add-topic physical-ai --add-topic robotics
   ```
4. **ログインしていない状態での見え方の検証**(新規アカウントは自動のスパム判定で他人から見えないことがある):
   ```bash
   curl -s -o /dev/null -w "%{http_code}\n" https://github.com/raycast-trail/go2-genesis-patrol      # 200
   curl -s https://api.github.com/repos/raycast-trail/go2-genesis-patrol/contributors | grep '"login"'  # raycast-trail のみ
   curl -s "https://api.github.com/repos/raycast-trail/go2-genesis-patrol/commits?per_page=100" | grep -o '"email": *"[^"]*"' | sort -u  # noreply のみ
   ```
   404 になる場合は報告して止める(人間が GitHub サポートに問い合わせる)
5. 最後に `gh auth switch` で元のアカウントに戻し、`gh auth status` の結果を報告に書く

### 5. やらないこと
- 旧リポジトリ `<旧アカウント>/go2-genesis-patrol` の削除・Transfer・設定変更(人間が新リポジトリを確認してから行う)
- `--force` での旧リポジトリへの push(旧リポジトリには一切 push しない)
- バックアップフォルダの push・削除

## 受け入れ条件
- [ ] 構成図(v3 のみ)・カード(C5 の比較、C6 の新 URL)・動画が再生成され、余白検査 OK、動画 60〜180 s
- [ ] README が v3 主役・v1/v2 比較の書き方になり、英語要約が差し替わっている
- [ ] HEAD の全追跡ファイルの検査(手順 1-6)が 0 件、メタデータに個人情報なし
- [ ] 書き換え後の履歴: 作者は raycast-trail の 1 種類のみ、全リビジョンで `$PII_PATTERN` が 0 件、PDF の blob は 1 つ
- [ ] `raycast-trail/go2-genesis-patrol` が public で、ログインなしで 200、contributors は raycast-trail のみ、コミットのメールは noreply のみ
- [ ] 作業フォルダの remote が新リポジトリだけを指し、`git config --local` が設定済み、`gh` は元のアカウントに戻っている
- [ ] `reports/16_anon_migration.md`(**日本語で**): 変更した文言の一覧、検査コマンドの出力、filter-repo の実行内容、除いた blob の数、検証結果、人間に残した作業。旧レポートに書かれたコミットハッシュは書き換えで無効になる旨を 1 行

## 調整候補(最大 2 つ)
1. `--strip-blobs-with-ids` で HEAD の版まで消えた場合: 書き換え後に HEAD の版をコミットし直す(作者は新設定)
2. `gh repo create --push` が認証で失敗する場合: `git remote set-url origin https://raycast-trail@github.com/raycast-trail/go2-genesis-patrol.git` にしてから `git push -u origin main`

## 人間に残す作業(報告の最後に列挙)
- シークレットウィンドウ(ログアウト状態)で新リポジトリの表示を確認する
- 旧リポジトリ `<旧アカウント>/go2-genesis-patrol` を削除する(Settings → Danger Zone → Delete this repository)
- 新リポジトリの Settings → Social preview に `docs/media/social_preview.png` を登録する
