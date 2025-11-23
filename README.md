# Molecule Renumber

分子構造ビューアーと原子番号の再割り当てツール

## 開発環境のセットアップ

### 必要な環境

- Python 3.x
- Node.js (TypeScriptコンパイル用)
- uv (Pythonパッケージマネージャー)

### インストール

```bash
# Pythonの依存関係をインストール
uv sync

# TypeScriptコンパイラをインストール
npm install --save-dev typescript
```

## TypeScriptのコンパイル

NGL Viewerのコードは TypeScript で記述されています。変更を加えた場合は、以下のコマンドでコンパイルしてください。

### 手動コンパイル

```bash
npx tsc
```

このコマンドは `src/ngl_viewer.ts` を `src/ngl_viewer.js` にコンパイルします。

**注意**: `uv run task build` を実行すると、TypeScriptのコンパイルは自動的に実行されます。

### 自動コンパイル（ウォッチモード）

開発中は、ファイルの変更を監視して自動的にコンパイルするウォッチモードが便利です：

```bash
npx tsc --watch
```

### TypeScript設定

TypeScriptの設定は `tsconfig.json` で管理されています：

- **ターゲット**: ES2017
- **モジュール**: ES2015
- **出力先**: `./src`
- **厳格な型チェック**: 有効

## アプリケーションの実行

```bash
# Pythonアプリケーションを起動
uv run python src/main.py
```

## ビルド

実行可能ファイル（.exe）をビルドするには：

```bash
uv run task build
```

このコマンドは以下を自動的に実行します：

1. TypeScriptのコンパイル（`npx tsc`）
2. PyInstallerによる実行可能ファイルの作成

ビルドされた実行可能ファイルは `dist/molecule-renumber.exe` に生成されます。

## プロジェクト構成

```
molecule_renumber/
├── src/
│   ├── main.py              # メインアプリケーション
│   ├── pdb_file.py          # PDBファイル処理
│   ├── ngl_viewer.html      # NGL Viewerのテンプレート
│   ├── ngl_viewer.ts        # NGL ViewerのTypeScriptコード
│   ├── ngl_viewer.js        # コンパイル済みJavaScript（自動生成）
│   └── ngl.js               # NGL ライブラリ
├── tsconfig.json            # TypeScript設定
├── pyproject.toml           # Python依存関係
└── README.md                # このファイル
```

## 開発ワークフロー

1. TypeScriptコードを編集: `src/ngl_viewer.ts`
2. コンパイル: `npx tsc`
3. アプリケーションを実行: `uv run python src/main.py`

**注意**: `src/ngl_viewer.js` は自動生成されるファイルなので、直接編集しないでください。
