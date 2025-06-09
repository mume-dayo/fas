
# Discord OAuth2認証システム

このアプリケーションはDiscord OAuth2を使用してユーザー認証を行い、指定されたロールを付与するWebサイトとBotです。

## 機能

- Discord OAuth2による認証
- 認証されたユーザーへの自動ロール付与
- ユーザーのID、メールアドレス、IPアドレスの取得・表示
- 認証済みユーザー一覧の表示
- Discord Botコマンド

## セットアップ手順

### 1. Discord Applicationの作成

1. [Discord Developer Portal](https://discord.com/developers/applications)にアクセス
2. "New Application"をクリックして新しいアプリケーションを作成
3. OAuth2 > General設定:
   - Client IDとClient Secretをコピー
   - Redirects に `https://your-repl-url.replit.dev/callback` を追加
4. Bot設定:
   - Botを作成してTokenを取得
   - 必要な権限を設定（Manage Roles, Send Messages等）

### 2. 環境変数の設定

Replitのsecrets機能または.envファイルで以下を設定:

```
DISCORD_CLIENT_ID=あなたのクライアントID
DISCORD_CLIENT_SECRET=あなたのクライアントシークレット
DISCORD_REDIRECT_URI=https://your-repl-url.replit.dev/callback
DISCORD_BOT_TOKEN=あなたのボットトークン
GUILD_ID=あなたのサーバーID
ROLE_ID=付与するロールのID
FLASK_SECRET_KEY=ランダムな文字列
```

### 3. Botをサーバーに招待

以下のURLでBotをサーバーに招待（CLIENT_IDを置き換え）:
```
https://discord.com/api/oauth2/authorize?client_id=CLIENT_ID&permissions=268435456&scope=bot
```

### 4. 実行

```bash
python main.py
```

## 使用方法

1. Webサイトにアクセス
2. "Discordでログイン"をクリック
3. Discord認証を完了
4. 自動的にロールが付与される
5. `/users`エンドポイントで全ユーザー表示

## Botコマンド

- `!users` - 認証済みユーザー一覧表示（管理者のみ）
- `!role @user` - 指定ユーザーにロール付与（管理者のみ）

## API エンドポイント

- `GET /` - ホームページ
- `GET /login` - Discord認証開始
- `GET /callback` - OAuth2コールバック
- `GET /users` - ユーザー一覧表示
- `GET /api/users` - JSON形式でユーザーデータ取得
- `GET /logout` - ログアウト
