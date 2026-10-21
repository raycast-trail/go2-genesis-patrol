# T14: Foxglove 3D 点群の画面収録を動画に追加(動画 v4)+ docs/report のコミット

## 目的
人間が Foxglove で `results/mcap/t12_3d_seed103.mcap` を再生し、QuickTime で画面収録した動画を提出動画に入れる。3D 点群(高さで色分け、減衰 60 s で積み上がる)が低い箱の上面・テーブルの天板・円柱の側面をなぞる様子を見せる。あわせて、人間が更新した `docs/report/`(レポート v3)をコミットする。

## 素材
- `videos/raw/画面収録 2026-10-21 19.28.05.mov`(人間が収録。2802×1860、60 fps、H.264、29.75 s、45 MB)
  - 先頭・末尾に再生前後の静止区間が 1 s 程度ある。上端に Foxglove のパネル見出しバー(「3D」の文字と右上のアイコン)、右端に縦のツールアイコン列が映り込んでいる

## 手順

### 1. 素材の整形
- ファイル名を `videos/raw/foxglove_3d_seed103.mov` に変える(`git mv` ではなく通常の mv。.mov はコミットしない)
- 見出しバーと右端のアイコン列を切り落とす: 先頭フレームを PNG に書き出して画素で境界を測り、`crop` で除く(目安: 上端 70〜80 px、右端 90〜110 px。実測値を報告に書く)。左端・下端に枠線があれば 2〜4 px 削る
- 再生前後の静止区間を除く: フレーム差分(`ffmpeg -vf "select='gt(scene,0.001)'"` か、`freezedetect`)で動き出し・止まりの時刻を求め、その区間だけ使う
- 1280×720 に **アスペクト比を保って縮小し、余白は背景色 `0x141820` でパディング**(T08 の `hstack_clips` と同じ背景色)。60 → 30 fps。H.264 CRF 23、音声なし
- 成果物 `videos/raw/foxglove_3d_seed103.mp4`(コミットする。5 MB 以下を目安)。`.gitignore` に `*.mov` を追加

### 2. 動画 v4(`scripts/make_cards.py`, `scripts/make_video.py`)
- **新ショット 12f** を **12d(3D: 迂回、完走)の直後**、12e(30 配置の結果カード)の前に挿入:
  - 素材: `videos/raw/foxglove_3d_seed103.mp4` の全区間を **2 倍速**(約 14 s)
  - バナー **B12f**(2 倍速表示あり): 「Foxglove: 3D 点群を高さで色分け。低い箱の上面・天板・円柱の側面を検出(seed 103)」。長ければ「Foxglove: 3D 点群(高さで色分け)が低い箱・天板・円柱をなぞる(seed 103)」程度に短縮。バナーは映像の上端に重ねる(既存のバナーと同じ)
- **ショット 9(2D の Foxglove 静止画)を 6 s → 4 s** に短縮
- 合計は約 157 − 2 + 14 = **169 s 前後**(≤ 180 s)。`make_video.py` の引数に素材が無い場合は 12f を飛ばす分岐を入れる(クリーンクローンでも動画再生成が止まらないように)
- `videos/final/PAI最終課題_3164.mp4` を上書き、`results/t10_contact.png` を更新、`scripts/check_margins.py` に B12f を追加

### 3. 図(レポート用)
- 収録の **末尾付近(点群が積み上がった状態)のフレーム**を、手順 1 の crop を適用した原寸(縮小・パディングなし)で `results/t14_foxglove3d_seed103.png` に書き出す。レポートは人間が更新する

### 4. README
- 「3D LiDAR」の節に 1 行と画像: `results/t14_foxglove3d_seed103.png`、「Foxglove での 3D 点群の表示(`/lidar/points` を z で色分け、減衰 60 s。`/lidar/points3d` で毎ステップの全点群)」
- Foxglove の手順に 3D の表示設定を追記(表示フレーム world、フォローモード 固定、`/lidar/points` のカラーマップ Turbo・カラーフィールド z・最小 0 / 最大 0.5・減衰 60 s、`/lidar/points3d` 減衰 0・ポイントサイズ 2、`/map` フラット色・半透明、変換のラベル オフ・軸のスケール 0.6)
- 開発ログに T14 の行

### 5. コミット
- `docs/report/`(人間が更新したレポート v3: PDF・report.html・`figs/lidar3d_test_crop.png`・`figs/traj_3d_seed103.png`・`figs/map_3d_seed103.png`)を **内容を変えずに** 含める
- 1 コミットで push。`videos/raw/foxglove_3d_seed103.mov` と `videos/t01_square_baseline.mp4` は未追跡のまま

## 受け入れ条件
- [ ] `foxglove_3d_seed103.mp4`: 1280×720、見出しバーとアイコン列が映っていない、静止区間なし(先頭・末尾のフレームを報告に貼る)
- [ ] 動画 v4: 60〜180 s、12f が 12d と 12e の間にあり「2倍速」表示、ショット 9 が 4 s、余白検査 OK、個人情報 grep 0 件。コンタクトシートで確認
- [ ] `results/t14_foxglove3d_seed103.png` がある
- [ ] README 更新、`docs/report/` を含めて push 済み、`git status` は上記 2 ファイル以外クリーン
- [ ] `reports/14_foxglove3d_video.md`: crop の実測値、使った区間、ショット表 v4、変更ファイル

## 調整候補(最大 2 つ)
1. 合計が 180 s を超える場合: 12f を 2 倍速のまま先頭 12 s に切る
2. 2 倍速で点の積み上がりが速すぎて読めない場合: 12f を 1.5 倍速・先頭 14 s に

## 成果物
- `videos/raw/foxglove_3d_seed103.mp4`、`.gitignore`
- `scripts/make_cards.py`(B12f)、`scripts/make_video.py`(12f、ショット 9 の長さ)、`scripts/check_margins.py`
- `videos/final/PAI最終課題_3164.mp4`、`results/t10_contact.png`、`results/t14_foxglove3d_seed103.png`
- `README.md`、`docs/report/`(追跡済みファイルの更新)
- `reports/14_foxglove3d_video.md`
