# T11: 構成図の作り直し + 動画 v2.1 + README 仕上げ + クリーンクローン検証

## 目的
1. 構成図 `figs/arch.png` の矢印とラベルの重なり(人間のレビュー指摘: 矢印とテキストの重なり、矢印のつながりが不自然)を解消する。**新しい描画スクリプト `scripts/make_arch.py` は作業者(人間側)が用意して置いてある**ので、それを使う。設計: 矢印はすべて直交、ラベルは矢印の脇、姿勢のフィードバックは「経路追従」と「占有格子」の両方に入る
2. 構成図を差し替えた提出動画(v2.1)を再生成する
3. README を提出版に仕上げる(結果・再現手順・構成・v1/v2/v3 の切替)
4. `docs/report/`(人間が更新した PDF・HTML・図)を含めてコミット
5. **クリーンクローンから動くこと**を確認する(チェックポイント・シーン JSON・スクリプトの不足がないか)

## 手順

### 1. 構成図
- `python scripts/make_arch.py`(`figs/arch.png` を上書き)。ヒラギノで描くと Noto より文字幅が変わるので、出力を開いてラベルが箱や矢印に重なっていないか目視する。重なる場合は `make_arch.py` の該当ラベルの座標か fontsize を調整してよい(箱の配置は変えない)
- `scripts/make_figs.py` の `arch()` は削除し、`main` から `make_arch.main("figs/arch.png")` を呼ぶ(import)か、docstring で「構成図は make_arch.py」と案内する。どちらでもよいが、`python scripts/make_figs.py` を実行しても古い構成図で上書きされないこと
- `scripts/check_margins.py` の検査対象に `figs/arch.png` を追加(左右余白 ≥ 100 px)

### 2. 動画 v2.1
- `python scripts/make_video.py`(T10 と同じ引数)で `videos/final/PAI最終課題_3164.mp4` を上書き。長さ 129 s 前後、1280×720、60〜180 s
- `results/t10_contact.png` を更新(ファイル名はそのまま上書きでよい)
- 構成図以外のカット・カード・文言は **変更しない**

### 3. README.md(提出版)
構成(見出し順)。数値は `results/eval_50/summary.md` と `reports/` から転記し、推測を書かない:
1. タイトルと 1 段落の概要(何を作り、何を示したか)。**動画・レポートの行は `(提出後に URL を記載)` のプレースホルダ**にしておく(人間が後で埋める)
2. **結果**: 45 配置 × 4 条件の表(成功率 [95% CI]、接触率、所要、経路効率)と `results/eval_50/summary.png`。v3 vs v1/v2 の所要時間の対応あり比較(p 値)を 1〜2 行
3. **構成図** `figs/arch.png` と 3 層の説明(各 3 行以内)。v1/v2/v3 の違いを 1 表に
4. **環境構築**(既存の内容を残す。`requirements.txt`、conda、Apple Silicon は Metal で学習・CPU で評価、Linux + CUDA でも動く想定だが未検証と明記)
5. **再現手順**(コマンド列。既存の 1〜5 を更新): 学習(10 分、省略可: `checkpoints/go2-patrol/model_299.pt` 同梱)、台本録画、巡回(`--avoid-version v1|v2|v3`、`--camera`、`--mcap`)、評価(`eval/run_eval.py` → `eval/summarize.py --compare3`)、Foxglove(既存の説明)、動画の再生成(`make_figs.py` → `make_arch.py` → `make_cards.py` → `make_video.py`)
6. **リポジトリ構成**の表(既存を更新: `checkpoints/`, `figs/`, `scripts/`, `docs/report/` を追加)
7. **既知の制約・限界**(真の姿勢を使用 / 静止障害物 / CPU バックエンドの非決定性 / 2D LiDAR に簡略化 / Metal は 1 env で遅い)を箇条書き
8. **開発ログ**: `tasks/NN` と `reports/NN` の対応表(T01〜T11、1 行ずつ)
9. **ライセンス・使用 OSS**(既存)
- 氏名・所属・メールは書かない。Omnicampus アカウント名(`PAI最終課題_3164` というファイル名・動画タイトル)への言及は可
- `.gitignore` に `.vscode/` を追加。`videos/t01_square_baseline.mp4` は追加しない(未追跡のまま)

### 4. クリーンクローン検証
```bash
git clone --depth 1 file://$(pwd) /tmp/go2-clone && cd /tmp/go2-clone
conda activate py311_genesis   # 既存環境を流用(インストール手順の検証はしない)
python go2_patrol.py -e go2-patrol --ckpt 299 --backend cpu --no-video --seed 10 --avoid --avoid-version v3 --summary-csv ""
python eval/summarize.py --compare3 results/eval_50/episodes.csv --scenes 5-49 --out-dir /tmp/go2-clone-summary
python scripts/check_margins.py
```
- `go2_patrol.py` が `checkpoints/` のモデルを読んで 4/4 完走すること(非決定性があるので 1 回で可。到達数と所要時間を記録)。**`logs/` が無い状態で動くこと**が確認点。`logs/` を前提にしているなら `checkpoints/` を探すように直す
- `summarize.py` の出力が `results/eval_50/summary.md` と一致すること
- 検証後に `/tmp/go2-clone` を削除

### 5. コミット
- `docs/report/`(更新済みの PDF・HTML・`figs/arch_crop.png`)、`scripts/make_arch.py`、更新した図・動画・README・`.gitignore` を 1 コミットに。push

## 受け入れ条件
- [ ] `figs/arch.png`: ラベルが矢印・箱に重ならず、矢印が箱の辺に接続している(目視。報告に画像を貼る)。左右余白 ≥ 100 px
- [ ] `videos/final/PAI最終課題_3164.mp4` が再生成され 60〜180 s、構成図以外は T10 と同一(ショット表の長さが一致)
- [ ] README に結果表・構成・環境・再現手順・構成表・限界・開発ログ・ライセンスがあり、個人情報なし(grep)
- [ ] クリーンクローンで `go2_patrol.py`(v3、seed 10)が動く
- [ ] `git status` がクリーン(`.vscode/` と `videos/t01_square_baseline.mp4` を除く)、push 済み
- [ ] `reports/11_arch_readme.md`: 構成図の前後比較、README の章立て、クリーンクローン検証の出力、変更ファイル

## 調整候補(最大 2 つ)
1. ヒラギノでラベルがはみ出す場合: `make_arch.py` の該当 fontsize を 1 下げる
2. クリーンクローンで `checkpoints/` を読めない場合: `go2_patrol.py` に `--ckpt-dir` 引数を足し、既定で `logs/<exp>` → 無ければ `checkpoints/<exp>` の順に探す

## 成果物
- `scripts/make_arch.py`(作業者提供、必要なら微調整)、`scripts/make_figs.py`、`scripts/check_margins.py`、`figs/arch.png`
- `videos/final/PAI最終課題_3164.mp4`、`results/t10_contact.png`
- `README.md`、`.gitignore`
- `docs/report/`(更新)
- `reports/11_arch_readme.md`
