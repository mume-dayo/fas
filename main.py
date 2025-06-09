import os
import json
import asyncio
import threading
from datetime import datetime
from flask import Flask, request, redirect, session, render_template_string, jsonify
import requests
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

# Flask app setup
app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'your-secret-key-here')

# Discord OAuth2 settings
DISCORD_CLIENT_ID = os.environ.get('DISCORD_CLIENT_ID')
DISCORD_CLIENT_SECRET = os.environ.get('DISCORD_CLIENT_SECRET')
DISCORD_REDIRECT_URI = os.environ.get('DISCORD_REDIRECT_URI', 'https://your-repl-url.replit.dev/callback')
DISCORD_BOT_TOKEN = os.environ.get('DISCORD_BOT_TOKEN')
GUILD_ID = int(os.environ.get('GUILD_ID', '0')) if os.environ.get('GUILD_ID', '0').isdigit() else 0
ROLE_ID = int(os.environ.get('ROLE_ID', '0')) if os.environ.get('ROLE_ID', '0').isdigit() else 0

def get_auto_guild_and_role():
    """Botが参加しているサーバーから自動的にGUILD_IDとROLE_IDを取得"""
    if not bot.is_ready():
        return None, None
    
    # 環境変数で指定されている場合はそれを優先
    if GUILD_ID and GUILD_ID != 0 and ROLE_ID and ROLE_ID != 0:
        return GUILD_ID, ROLE_ID
    
    # Botが参加している最初のサーバーを取得
    if bot.guilds:
        guild = bot.guilds[0]
        # そのサーバーの@everyone以外の最初のロールを取得
        for role in guild.roles:
            if role.name != "@everyone" and not role.managed:
                print(f"自動選択: サーバー '{guild.name}' (ID: {guild.id}), ロール '{role.name}' (ID: {role.id})")
                return guild.id, role.id
        
        # 適切なロールが見つからない場合はサーバーIDのみ返す
        print(f"自動選択: サーバー '{guild.name}' (ID: {guild.id}), ロールなし")
        return guild.id, None
    
    return None, None

# サーバー選択用のデータ
server_data = {}

# Discord Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Store user data
user_data = {}

# 管理者認証情報
ADMIN_USERNAME = "Yukikitada"
ADMIN_PASSWORD = "Yuki6174314"

def check_admin_auth():
    """管理者認証をチェック"""
    auth = request.authorization
    if auth and auth.username == ADMIN_USERNAME and auth.password == ADMIN_PASSWORD:
        return True
    return False

def require_admin_auth():
    """管理者認証を要求"""
    return request.authorization and check_admin_auth()

def get_bot_guilds():
    """Botが参加しているサーバー一覧を取得"""
    if not bot.is_ready():
        return []

    guilds_info = []
    for guild in bot.guilds:
        # そのサーバーのロール一覧も取得
        roles_info = []
        for role in guild.roles:
            if role.name != "@everyone":  # @everyoneロールは除外
                roles_info.append({
                    'id': role.id,
                    'name': role.name,
                    'color': str(role.color)
                })

        guilds_info.append({
            'id': guild.id,
            'name': guild.name,
            'member_count': guild.member_count,
            'roles': roles_info
        })

    return guilds_info

async def assign_role_to_user(user_id, access_token, guild_id=None, role_id=None):
    """ユーザーにロールを付与する非同期関数"""
    # パラメータで指定されない場合は自動検出または環境変数を使用
    if guild_id is None or role_id is None:
        auto_guild_id, auto_role_id = get_auto_guild_and_role()
        target_guild_id = guild_id or auto_guild_id or GUILD_ID
        target_role_id = role_id or auto_role_id or ROLE_ID
    else:
        target_guild_id = guild_id
        target_role_id = role_id

    if not target_guild_id or target_guild_id == 0:
        print("GUILD_IDが設定されておらず、自動検出もできないため、ロール付与をスキップします")
        return "スキップ"

    try:
        guild = bot.get_guild(target_guild_id)
        if not guild:
            print("指定されたギルドが見つかりません")
            return False

        # ユーザーをサーバーに追加（既に参加している場合はスキップ）
        try:
            await bot.http.add_user_to_guild(target_guild_id, user_id, access_token)
        except discord.HTTPException:
            pass  # 既に参加している場合やその他のHTTPエラー
        except Exception as e:
            print(f"サーバー追加エラー: {e}")

        # 少し待ってからメンバーを取得
        await asyncio.sleep(1)

        member = guild.get_member(int(user_id))
        if member:
            role = guild.get_role(target_role_id) if target_role_id and target_role_id != 0 else None
            if role:
                await member.add_roles(role)
                print(f"ロール '{role.name}' を {member.name} に付与しました")
                return True
            else:
                print("指定されたロールが見つかりません")
        else:
            print("メンバーが見つかりません")
    except Exception as e:
        print(f"ロール付与処理エラー: {e}")

    return False

# HTML templates
LOGIN_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Discord OAuth2 認証</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; background-color: #f8f9fa; }
        .container { background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .btn { 
            display: inline-block; 
            padding: 15px 30px; 
            background: #5865F2; 
            color: white; 
            text-decoration: none; 
            border-radius: 8px; 
            font-size: 16px;
            font-weight: bold;
            transition: background 0.3s;
            margin: 10px 0;
        }
        .btn:hover { background: #4752C4; }
        .auth-section { text-align: center; margin: 30px 0; }
        h1 { color: #5865F2; text-align: center; }
        p { color: #666; line-height: 1.6; }
        .discord-icon { width: 20px; height: 20px; margin-right: 10px; vertical-align: middle; }
        .server-selection { margin: 20px 0; text-align: left; }
        .server-card { 
            border: 1px solid #ddd; 
            border-radius: 8px; 
            padding: 15px; 
            margin: 10px 0; 
            background: #f9f9f9;
            cursor: pointer;
            transition: background 0.3s;
        }
        .server-card:hover { background: #e9ecef; }
        .server-card.selected { background: #e3f2fd; border-color: #5865F2; }
        .role-list { margin-top: 10px; }
        .role-tag { 
            display: inline-block; 
            padding: 2px 8px; 
            margin: 2px; 
            border-radius: 12px; 
            font-size: 12px;
            background: #e9ecef;
            color: #495057;
        }
        select { padding: 10px; margin: 10px 0; border-radius: 5px; border: 1px solid #ddd; }
    </style>
    <script>
        let selectedGuildId = null;
        let selectedRoleId = null;

        function selectServer(guildId) {
            document.querySelectorAll('.server-card').forEach(card => {
                card.classList.remove('selected');
            });
            document.getElementById('server-' + guildId).classList.add('selected');
            selectedGuildId = guildId;

            // ロール選択を表示
            const roleSelect = document.getElementById('role-select-' + guildId);
            document.querySelectorAll('.role-select').forEach(select => {
                select.style.display = 'none';
            });
            if (roleSelect) {
                roleSelect.style.display = 'block';
            }
        }

        function selectRole(guildId) {
            const roleSelect = document.getElementById('role-select-' + guildId);
            selectedRoleId = roleSelect.value;
        }

        function startLogin() {
            let loginUrl = '/login';
            if (selectedGuildId && selectedRoleId) {
                loginUrl += '?guild_id=' + selectedGuildId + '&role_id=' + selectedRoleId;
            }
            window.location.href = loginUrl;
        }
    </script>
</head>
<body>
    <div class="container">
        <h1>🔐 Discord OAuth2 認証システム</h1>
        <p>Discordアカウントでログインして、指定されたロールを取得してください。</p>

        <div class="auth-section">
            <p><strong>作成者、mumei</strong></p>

            {% if guilds %}
            <div class="server-selection">
                <h3>サーバーとロールを選択してください：</h3>
                {% for guild in guilds %}
                <div class="server-card" id="server-{{ guild.id }}" onclick="selectServer({{ guild.id }})">
                    <h4>{{ guild.name }}</h4>
                    <p>メンバー数: {{ guild.member_count }}</p>
                    <div class="role-list">
                        {% for role in guild.roles[:5] %}
                        <span class="role-tag">{{ role.name }}</span>
                        {% endfor %}
                        {% if guild.roles|length > 5 %}
                        <span class="role-tag">+{{ guild.roles|length - 5 }}個</span>
                        {% endif %}
                    </div>
                    <select class="role-select" id="role-select-{{ guild.id }}" style="display: none;" onchange="selectRole({{ guild.id }})">
                        <option value="">ロールを選択...</option>
                        {% for role in guild.roles %}
                        <option value="{{ role.id }}">{{ role.name }}</option>
                        {% endfor %}
                    </select>
                </div>
                {% endfor %}
            </div>
            {% endif %}

            <div style="margin-top: 30px;">
                <button onclick="startLogin()" class="btn">
                    <svg class="discord-icon" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515a.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0a12.64 12.64 0 0 0-.617-1.25a.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057a19.9 19.9 0 0 0 5.993 3.03a.078.078 0 0 0 .084-.028a14.09 14.09 0 0 0 1.226-1.994a.076.076 0 0 0-.041-.106a13.107 13.107 0 0 1-1.872-.892a.077.077 0 0 1-.008-.128a10.2 10.2 0 0 0 .372-.292a.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127a12.299 12.299 0 0 1-1.873.892a.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028a19.839 19.839 0 0 0 6.002-3.03a.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419c0-1.333.956-2.419 2.157-2.419c1.21 0 2.176 1.096 2.157 2.42c0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419c0-1.333.955-2.419 2.157-2.419c1.21 0 2.176 1.096 2.157 2.42c0 1.333-.946 2.418-2.157 2.418z"/>
                    </svg>
                    Discordでログイン
                </button>
            </div>

            <p style="font-size: 12px; color: #999; margin-top: 20px;">
                ログインすることで、利用規約とプライバシーポリシーに同意したものとみなします。
            </p>
        </div>
    </div>
</body>
</html>
'''

SUCCESS_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>認証完了</title>
    <style>
        body { 
            font-family: Arial, sans-serif; 
            max-width: 600px; 
            margin: 0 auto; 
            padding: 20px; 
            background-color: #f8f9fa;
            text-align: center;
        }
        .success-container { 
            background: white; 
            padding: 40px; 
            border-radius: 15px; 
            box-shadow: 0 4px 20px rgba(0,0,0,0.1);
            margin-top: 50px;
        }
        .success-icon {
            font-size: 4em;
            color: #28a745;
            margin-bottom: 20px;
        }
        h1 { 
            color: #28a745; 
            margin-bottom: 20px;
            font-size: 2.5em;
        }
        .success-message {
            font-size: 1.2em;
            color: #666;
            margin-bottom: 30px;
            line-height: 1.6;
        }
        .btn { 
            display: inline-block; 
            padding: 12px 30px; 
            background: #5865F2; 
            color: white; 
            text-decoration: none; 
            border-radius: 8px;
            font-size: 16px;
            font-weight: bold;
            transition: background 0.3s;
        }
        .btn:hover { background: #4752C4; }
        .role-status {
            background: #e8f5e8;
            color: #2d5016;
            padding: 15px;
            border-radius: 8px;
            margin: 20px 0;
            border-left: 4px solid #28a745;
        }
    </style>
</head>
<body>
    <div class="success-container">
        <div class="success-icon">✅</div>
        <h1>認証完了！</h1>
        <div class="success-message">
            Discord認証が正常に完了しました。<br>
            ようこそ！
        </div>
        
        {% if role_status != "ロール付与に失敗しました" %}
        <div class="role-status">
            {% if role_status == "ロール付与はスキップされました（GUILD_ID未設定）" %}
            ℹ️ ロール付与機能は現在設定されていません
            {% elif role_status == "ロールが正常に付与されました" %}
            🎭 ロールが正常に付与されました
            {% endif %}
        </div>
        {% endif %}
        
        <a href="/logout" class="btn">ログアウト</a>
    </div>
</body>
</html>
'''

ADMIN_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>管理者ページ - 認証済みユーザー一覧</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; background-color: #f8f9fa; }
        .container { background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { color: #dc3545; text-align: center; margin-bottom: 30px; }
        .stats { display: flex; justify-content: space-around; margin: 20px 0; }
        .stat-card { background: #f8f9fa; padding: 20px; border-radius: 8px; text-align: center; min-width: 150px; }
        .stat-number { font-size: 2em; font-weight: bold; color: #5865F2; }
        .stat-label { color: #666; margin-top: 5px; }
        table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        th, td { border: 1px solid #ddd; padding: 12px; text-align: left; }
        th { background-color: #5865F2; color: white; font-weight: bold; }
        tr:nth-child(even) { background-color: #f9f9f9; }
        tr:hover { background-color: #e9ecef; }
        .btn { display: inline-block; padding: 12px 25px; background: #5865F2; color: white; text-decoration: none; border-radius: 8px; margin: 10px 5px; transition: background 0.3s; }
        .btn:hover { background: #4752C4; }
        .btn-danger { background: #dc3545; }
        .btn-danger:hover { background: #c82333; }
        .admin-header { background: linear-gradient(135deg, #dc3545, #c82333); color: white; padding: 20px; border-radius: 10px; margin-bottom: 30px; text-align: center; }
        .no-data { text-align: center; color: #666; font-style: italic; padding: 40px; }
        .user-avatar { width: 32px; height: 32px; border-radius: 16px; margin-right: 8px; vertical-align: middle; }
    </style>
</head>
<body>
    <div class="container">
        <div class="admin-header">
            <h1>🔐 管理者ダッシュボード</h1>
            <p>Discord OAuth2認証システム管理画面</p>
        </div>

        <div class="stats">
            <div class="stat-card">
                <div class="stat-number">{{ users|length }}</div>
                <div class="stat-label">総認証ユーザー数</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{{ bot_guilds|length }}</div>
                <div class="stat-label">参加サーバー数</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{{ online_users }}</div>
                <div class="stat-label">オンラインユーザー</div>
            </div>
        </div>

        {% if users %}
        <h2>認証済みユーザー一覧</h2>
        <table>
            <tr>
                <th>ユーザー名</th>
                <th>Discord ID</th>
                <th>メールアドレス</th>
                <th>IPアドレス</th>
                <th>認証日時</th>
                <th>操作</th>
            </tr>
            {% for user in users %}
            <tr>
                <td>{{ user.username }}</td>
                <td>{{ user.user_id }}</td>
                <td>{{ user.email }}</td>
                <td>{{ user.ip_address }}</td>
                <td>{{ user.timestamp }}</td>
                <td>
                    <a href="/admin/user/{{ user.user_id }}" class="btn" style="padding: 5px 10px; font-size: 12px;">詳細</a>
                </td>
            </tr>
            {% endfor %}
        </table>
        {% else %}
        <div class="no-data">
            <h3>認証済みユーザーがいません</h3>
            <p>まだ誰も認証を完了していません。</p>
        </div>
        {% endif %}

        <div style="text-align: center; margin-top: 30px;">
            <a href="/admin/export" class="btn">📊 データエクスポート</a>
            <a href="/admin/clear" class="btn btn-danger" onclick="return confirm('本当に全データを削除しますか？')">🗑️ 全データ削除</a>
            <a href="/" class="btn">🏠 ホームに戻る</a>
        </div>
    </div>
</body>
</html>
'''

@app.route('/')
def home():
    if 'access_token' in session:
        role_granted = session.get('role_granted')

        if role_granted == "スキップ":
            role_status = "ロール付与はスキップされました（GUILD_ID未設定）"
        elif role_granted:
            role_status = "ロールが正常に付与されました"
        else:
            role_status = "ロール付与に失敗しました"

        return render_template_string(SUCCESS_TEMPLATE, role_status=role_status)

    # Botが参加しているサーバー一覧を取得
    guilds = get_bot_guilds()
    return render_template_string(LOGIN_TEMPLATE, guilds=guilds)

@app.route('/login')
def login():
    # サーバーとロールの選択をセッションに保存
    guild_id = request.args.get('guild_id')
    role_id = request.args.get('role_id')

    if guild_id:
        session['selected_guild_id'] = int(guild_id)
    if role_id:
        session['selected_role_id'] = int(role_id)

    discord_login_url = f"https://discord.com/api/oauth2/authorize?client_id={DISCORD_CLIENT_ID}&redirect_uri={DISCORD_REDIRECT_URI}&response_type=code&scope=identify%20email%20guilds.join"
    return redirect(discord_login_url)

@app.route('/callback')
def callback():
    code = request.args.get('code')
    if not code:
        return "認証に失敗しました", 400

    # Access token取得
    data = {
        'client_id': DISCORD_CLIENT_ID,
        'client_secret': DISCORD_CLIENT_SECRET,
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': DISCORD_REDIRECT_URI
    }

    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    r = requests.post('https://discord.com/api/oauth2/token', data=data, headers=headers)

    if r.status_code != 200:
        return "トークン取得に失敗しました", 400

    token_data = r.json()
    access_token = token_data['access_token']

    # ユーザー情報取得
    headers = {'Authorization': f'Bearer {access_token}'}
    user_response = requests.get('https://discord.com/api/users/@me', headers=headers)

    if user_response.status_code != 200:
        return "ユーザー情報取得に失敗しました", 400

    user_info = user_response.json()
    ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)

    # セッションに保存
    session['access_token'] = access_token
    session['user_info'] = user_info

    # ユーザーデータを保存
    from datetime import datetime
    user_data[user_info['id']] = {
        'username': f"{user_info['username']}#{user_info['discriminator']}",
        'user_id': user_info['id'],
        'email': user_info.get('email', 'N/A'),
        'ip_address': ip_address,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

    # Botを使ってロールを付与（非同期処理）
    role_granted = False
    try:
        # セッションから選択されたサーバーとロールを取得
        selected_guild_id = session.get('selected_guild_id')
        selected_role_id = session.get('selected_role_id')

        # 非同期でロール付与を実行
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        role_granted = loop.run_until_complete(
            assign_role_to_user(user_info['id'], access_token, selected_guild_id, selected_role_id)
        )
        loop.close()
    except Exception as e:
        print(f"ロール付与エラー: {e}")

    session['role_granted'] = role_granted

    return redirect('/')

@app.route('/admin')
def admin_dashboard():
    """管理者ダッシュボード"""
    if not require_admin_auth():
        return ('管理者認証が必要です', 401, {
            'WWW-Authenticate': 'Basic realm="Admin Area"'
        })
    
    users_list = list(user_data.values())
    bot_guilds = get_bot_guilds()
    
    # オンラインユーザー数（簡易実装）
    online_users = len([u for u in users_list if u])  # 実際はDiscord APIで確認
    
    return render_template_string(ADMIN_TEMPLATE, 
                                users=users_list, 
                                bot_guilds=bot_guilds,
                                online_users=online_users)

@app.route('/admin/user/<user_id>')
def admin_user_detail(user_id):
    """ユーザー詳細ページ"""
    if not require_admin_auth():
        return ('管理者認証が必要です', 401, {
            'WWW-Authenticate': 'Basic realm="Admin Area"'
        })
    
    user = user_data.get(user_id)
    if not user:
        return "ユーザーが見つかりません", 404
    
    return jsonify(user)

@app.route('/admin/export')
def admin_export():
    """データエクスポート"""
    if not require_admin_auth():
        return ('管理者認証が必要です', 401, {
            'WWW-Authenticate': 'Basic realm="Admin Area"'
        })
    
    return jsonify({
        'export_date': datetime.now().isoformat(),
        'total_users': len(user_data),
        'users': list(user_data.values())
    })

@app.route('/admin/clear', methods=['POST', 'GET'])
def admin_clear():
    """全データ削除"""
    if not require_admin_auth():
        return ('管理者認証が必要です', 401, {
            'WWW-Authenticate': 'Basic realm="Admin Area"'
        })
    
    if request.method == 'POST':
        user_data.clear()
        return redirect('/admin')
    
    return '''
    <form method="POST">
        <p>本当に全ユーザーデータを削除しますか？</p>
        <button type="submit">削除する</button>
        <a href="/admin">キャンセル</a>
    </form>
    '''

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/api/users')
def api_users():
    return jsonify(list(user_data.values()))

@app.route('/api/guilds')
def api_guilds():
    """利用可能なサーバー一覧をAPIで提供"""
    guilds = get_bot_guilds()
    return jsonify(guilds)

# Discord Bot events
@bot.event
async def on_ready():
    print(f'{bot.user} としてログインしました!')
    print(f'Bot ID: {bot.user.id}')
    
    # 参加しているサーバー一覧を表示
    print(f'参加サーバー数: {len(bot.guilds)}')
    for guild in bot.guilds:
        print(f'  - {guild.name} (ID: {guild.id}, メンバー数: {guild.member_count})')
    
    # 自動検出されたGUILD_IDとROLE_IDを表示
    auto_guild_id, auto_role_id = get_auto_guild_and_role()
    if auto_guild_id:
        guild = bot.get_guild(auto_guild_id)
        role = bot.get_guild(auto_guild_id).get_role(auto_role_id) if auto_role_id else None
        print(f'自動検出: デフォルトサーバー "{guild.name}" (ID: {auto_guild_id})')
        if role:
            print(f'自動検出: デフォルトロール "{role.name}" (ID: {auto_role_id})')
        else:
            print('自動検出: デフォルトロールなし')
    else:
        print('自動検出: サーバーが見つかりません')

@bot.event
async def on_member_join(member):
    print(f'{member.name} がサーバーに参加しました')

@bot.command(name='auth')
async def auth_user(ctx):
    """OAuth2認証を促すボタンを表示"""
    user_info = user_data.get(str(ctx.author.id))

    # サーバーとロール情報を取得
    auto_guild_id, auto_role_id = get_auto_guild_and_role()
    target_guild_id = auto_guild_id or GUILD_ID
    target_role_id = auto_role_id or ROLE_ID

    guild_name = "未設定"
    role_name = "未設定"

    if target_guild_id and target_guild_id != 0:
        guild = bot.get_guild(target_guild_id)
        if guild:
            guild_name = guild.name
            if target_role_id and target_role_id != 0:
                role = guild.get_role(target_role_id)
                if role:
                    role_name = role.name

    embed = discord.Embed(
        title="Discord認証",
        description=f"**{guild_name}**\nMemberの認証ページです",
        color=0x5865F2
    )

    embed.add_field(
        name="サーバー",
        value=guild_name,
        inline=True
    )

    embed.add_field(
        name="ロール",
        value=role_name,
        inline=True
    )

    if user_info:
        embed.add_field(
            name="✅ 認証状態",
            value="認証済み",
            inline=False
        )
        embed.color = 0x00ff00  # 緑色に変更
    else:
        embed.add_field(
            name="❌ 認証状態",
            value="未認証",
            inline=False
        )

    # 認証ボタンを追加
    view = AuthView(guild_name, role_name)
    await ctx.send(embed=embed, view=view)

@bot.command(name='setuprole')
@commands.has_permissions(administrator=True)
async def setup_role_button(ctx, role: discord.Role):
    """管理者が指定したロールを付与するボタンを設置"""
    embed = discord.Embed(
        title="🎭 ロール付与システム",
        description=f"**{role.name}** ロールを取得するには下のボタンをクリックしてください。",
        color=role.color if role.color.value != 0 else 0x5865F2
    )

    embed.add_field(
        name="📋 取得可能ロール",
        value=f"🎭 {role.mention}",
        inline=True
    )

    embed.add_field(
        name="ℹ️ 注意事項",
        value="• ボタンは誰でも押せます\n• 既にロールを持っている場合は何も起こりません\n• 認証不要で即座にロールが付与されます",
        inline=False
    )

    # ロール付与ボタンを追加
    view = RoleAssignView(role.id)
    await ctx.send(embed=embed, view=view)
    await ctx.message.delete()  # 設置コマンドを削除

# 認証ボタンのビュークラス
class AuthView(discord.ui.View):
    def __init__(self, guild_name="未設定", role_name="未設定"):
        super().__init__(timeout=300)  # 5分でタイムアウト
        self.guild_name = guild_name
        self.role_name = role_name

    @discord.ui.button(label='Memberとして認証', style=discord.ButtonStyle.primary)
    async def auth_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Webサイトの認証URLを生成
        auth_url = f"{DISCORD_REDIRECT_URI.replace('/callback', '')}/login"

        embed = discord.Embed(
            title="🔐 OAuth2認証",
            description=f"以下のリンクをクリックして認証を完了してください：\n\n[**🔗 認証サイトへ移動**]({auth_url})",
            color=0x5865F2
        )

        embed.add_field(
            name="🏠 認証先サーバー",
            value=self.guild_name,
            inline=True
        )

        embed.add_field(
            name="🎭 付与されるロール",
            value=self.role_name,
            inline=True
        )

        embed.add_field(
            name="📋 認証手順",
            value="1. 上記リンクをクリック\n2. Discordでログイン\n3. 認証を許可\n4. 自動的にロールが付与されます",
            inline=False
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

# ロール付与ボタンのビュークラス
class RoleAssignView(discord.ui.View):
    def __init__(self, role_id):
        super().__init__(timeout=None)  # 永続的なボタン
        self.role_id = role_id

    @discord.ui.button(label='🎭 ロールを取得', style=discord.ButtonStyle.success, emoji='🎭')
    async def role_assign_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            role = interaction.guild.get_role(self.role_id)
            member = interaction.user

            if not role:
                await interaction.response.send_message(
                    "❌ ロールが見つかりません。管理者にお問い合わせください。",
                    ephemeral=True
                )
                return

            if role in member.roles:
                await interaction.response.send_message(
                    f"✅ あなたは既に **{role.name}** ロールを持っています。",
                    ephemeral=True
                )
                return

            await member.add_roles(role)
            
            embed = discord.Embed(
                title="🎉 ロール付与完了！",
                description=f"**{role.name}** ロールが正常に付与されました。",
                color=role.color if role.color.value != 0 else 0x00ff00
            )

            embed.add_field(
                name="👤 ユーザー",
                value=member.mention,
                inline=True
            )

            embed.add_field(
                name="🎭 付与されたロール",
                value=role.mention,
                inline=True
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ ロールを付与する権限がありません。Botの権限設定を確認してください。",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ エラーが発生しました: {str(e)}",
                ephemeral=True
            )

@bot.command(name='role')
@commands.has_permissions(administrator=True)
async def give_role(ctx, member: discord.Member):
    """指定したメンバーにロールを付与"""
    auto_guild_id, auto_role_id = get_auto_guild_and_role()
    target_role_id = auto_role_id or ROLE_ID
    
    if not target_role_id or target_role_id == 0:
        await ctx.send("ROLE_IDが設定されておらず、自動検出もできないため、ロールを付与できません。")
        return

    role = ctx.guild.get_role(target_role_id)
    if role:
        await member.add_roles(role)
        await ctx.send(f'{member.mention} に {role.name} ロールを付与しました！')
    else:
        await ctx.send("指定されたロールが見つかりません。")

def run_bot():
    """Botを別スレッドで実行"""
    if DISCORD_BOT_TOKEN:
        print(f"Bot Token設定確認: {'設定済み' if DISCORD_BOT_TOKEN else '未設定'}")
        print(f"Bot Token長さ: {len(DISCORD_BOT_TOKEN) if DISCORD_BOT_TOKEN else 0}")
        asyncio.set_event_loop(asyncio.new_event_loop())
        try:
            bot.run(DISCORD_BOT_TOKEN)
        except discord.LoginFailure as e:
            print(f"Discord認証エラー: {e}")
            print("Bot Tokenが無効です。Discord Developer Portalで新しいトークンを生成してください。")
        except Exception as e:
            print(f"Bot実行エラー: {e}")
    else:
        print("DISCORD_BOT_TOKENが設定されていません")

def run_flask():
    """Flaskアプリを実行"""
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

if __name__ == '__main__':
    print("Discord OAuth2認証システムを開始しています...")
    print("環境変数確認:")
    print(f"- DISCORD_CLIENT_ID: {'設定済み' if DISCORD_CLIENT_ID else '未設定'}")
    print(f"- DISCORD_CLIENT_SECRET: {'設定済み' if DISCORD_CLIENT_SECRET else '未設定'}")
    print(f"- DISCORD_BOT_TOKEN: {'設定済み' if DISCORD_BOT_TOKEN else '未設定'}")
    print(f"- DISCORD_REDIRECT_URI: {DISCORD_REDIRECT_URI}")
    print(f"- GUILD_ID: {GUILD_ID if GUILD_ID else '未設定'}")
    print(f"- ROLE_ID: {ROLE_ID if ROLE_ID else '未設定'}")
    print()
    
    if not DISCORD_BOT_TOKEN:
        print("❌ DISCORD_BOT_TOKENが設定されていません。")
        print("Render.comのダッシュボードで環境変数を設定してください。")
    
    if not GUILD_ID or GUILD_ID == 0:
        print("注意: GUILD_IDが設定されていません。")
        print("Botが参加しているサーバーから自動的に検出を試みます。")
    else:
        print(f"設定済み: GUILD_ID={GUILD_ID}, ROLE_ID={ROLE_ID}")

    # Botを別スレッドで開始
    if DISCORD_BOT_TOKEN:
        bot_thread = threading.Thread(target=run_bot, daemon=True)
        bot_thread.start()
        print("Discord Bot started in background")

    # Flaskアプリを開始
    run_flask()
