# Molecule Renumber

分子構造ビューアーおよび原子番号再割り当てツール。
Blender の MolecularNodes で `res_id` に基づく着色を行う用途に最適化しています。

## 開発環境

### 必要要件

* Python 3.x
* Node.js（TypeScript コンパイル用）
* uv（Python パッケージマネージャー）

### インストール

```bash
# Python の依存関係
uv sync

# TypeScript コンパイラ
npm install --save-dev typescript
```

## TypeScript コンパイル

NGL Viewer 関連コードは TypeScript で記述されています。編集後は以下の方法でコンパイルしてください。

### 手動コンパイル

```bash
npx tsc
```

`src/ngl_viewer.ts` が `src/ngl_viewer.js` に変換されます。
`uv run task build` 実行時には TypeScript コンパイルも自動的に行われます。

### ウォッチモード

開発中は自動コンパイルが便利です。

```bash
npx tsc --watch
```

### TypeScript 設定

設定は `tsconfig.json` に定義されています。

* Target: ES2017
* Module: ES2015
* Output: `./src`
* Strict モード: 有効

## アプリケーション実行

```bash
uv run python src/main.py
```

## ビルド

実行可能ファイル（.exe）を生成する場合：

```bash
uv run task build
```

この処理には以下が含まれます。

1. TypeScript のコンパイル
2. PyInstaller による実行ファイル生成

ビルド済みファイルは `dist/molecule-renumber.exe` に配置されます。

## プロジェクト構成

```
molecule_renumber/
├── src/
│   ├── main.py              # メインアプリケーション
│   ├── pdb_file.py          # PDB処理ロジック
│   ├── ngl_viewer.html      # NGL Viewer テンプレート
│   ├── ngl_viewer.ts        # TypeScript ソース
│   ├── ngl_viewer.js        # コンパイル済み JavaScript（自動生成）
│   └── ngl.js               # NGL ライブラリ
├── tsconfig.json            # TypeScript 設定
├── pyproject.toml           # Python 依存関係
└── README.md
```

## 開発フロー

1. TypeScript を編集（`src/ngl_viewer.ts`）
2. コンパイル（`npx tsc`）
3. アプリケーション起動（`uv run python src/main.py`）

`src/ngl_viewer.js` は自動生成ファイルのため、直接編集しないこと。
