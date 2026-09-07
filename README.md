# マイレシピ本

外食で美味しかった料理を「再現レシピ」として1ファイルずつ残し、
写真つきのHTMLサイト（＋必要ならPDF/Word）にまとめる個人プロジェクト。

## フォルダ構成

```
my-recipe-book/
├── README.md                このファイル
├── CLAUDE.md                Claudeが写真からレシピを作るときの手順
├── レシピ雛形.md             新しいレシピを手で書くときのコピー元
├── recipes/
│   ├── 2026-09-06_ガスパチョ.md   レシピ本体（1料理1ファイル）
│   ├── inbox/                     スマホから上げた写真の受信箱（処理後は空になる）
│   └── 画像/                      料理写真（Markdownと同じ名前）
├── build/
│   ├── build.py             全レシピを結合してPDF/Wordを生成
│   ├── サイト生成.py         全レシピからHTMLサイトを docs/ に生成
│   └── 自動レシピ生成手順.md  夜間エージェントが従う手順書
├── docs/                    公開サイト（GitHub Pagesの配信元。自動更新）
└── 出力/                    PDF/Word（gitには入れない。build.pyで作り直せる）
```

ファイル名は **`日付_料理名.md`** 形式（例: `2026-09-06_ガスパチョ.md`）。
先頭が日付なので、並べると自動的に訪問日順になる。

## しくみ

```
スマホのSafariで GitHubの「Upload files」ページを開き、料理写真をコミット
（→ recipes/inbox/ に入る）
      ↓
毎晩4時、クラウドの定期エージェントが:
  ・recipes/inbox/ の写真を1枚ずつ見る
  ・レシピの下書きを作成（材料・作り方は推定）
  ・画像を recipes/画像/ へ移動
  ・build/サイト生成.py で docs/ のサイトを作り直す
  ・main に commit & push
      ↓
GitHub Pages が docs/ を配信 → URLでいつでも最新版が見られる
```

## レシピの追加方法

### 方法1：スマホから写真をアップ（おすすめ）

1. Safariで開く（ブックマーク推奨）：
   `https://github.com/DAICHITANIMOTO/my-recipe-book/upload/main/recipes/inbox`
2. **「choose your files」** → **「フォトライブラリ」** → 料理写真を選ぶ（複数可）
3. 下にスクロールして緑の **「Commit changes」**

料理名・店名は入力不要（写真から推定）。翌朝までにレシピとサイトへ自動反映される。
このページをホーム画面に追加すると次回から1タップで開ける。

※ GitHubの「Issue」に写真を貼る方法は使わない（夜間の自動処理がIssue添付画像を
取得できないため）。写真は必ず上のUploadページから入れる。

### 方法2：PCで手書きする

1. `レシピ雛形.md` をコピーして `recipes/日付_料理名.md` にリネーム
2. 料理写真を `recipes/画像/日付_料理名.jpg` に置く（同じ名前にする）
3. frontmatter（title / date / restaurant / category）と各見出しを埋める
4. `python3 build/サイト生成.py`（サイト更新）
5. `git add -A && git commit -m "レシピ追加: 料理名" && git push`

## 見る

### HTMLサイト（メイン）

GitHub Pages を「main ブランチ / `docs` フォルダ」に設定すると、
`https://daichitanimoto.github.io/my-recipe-book/` で最新のレシピ本が見られる。
スマホ可・アカウント不要。検索避け（noindex ＋ robots.txt）済み。
パートナーにはこのURLを渡す。

### PDF / Word（手渡し用）

```
brew install pandoc typst      # 初回だけ
python3 build/build.py         # 出力/マイレシピ本.pdf ＋ .docx
```

表紙・目次が自動で付く。写真が無いレシピは「（写真未登録）」と表示され、
あとで `recipes/画像/` に同名で写真を置けば次のビルドから反映される。

## 材料・作り方について

各レシピの材料・作り方は **写真と料理名からの推定** で、お店の本物のレシピではない。
実際に作って気づいた調整点は各レシピの「調整メモ」に書き足していく。作るたびに精度が上がる。
