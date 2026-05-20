from flask import Flask, render_template, request, jsonify, Response
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import random

app = Flask(__name__)

# Полный и правильный URL базы данных из Render
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://admin:EVwq9lS8WmCbqQkjgdb57pLvZc1YT5B4@dpg-d862i10jo89c7384a9ug-a.frankfurt-postgres.render.com/clicker_db_t59u')


def get_db_connection():
    # Если запускаем локально (переменной среды нет), жестко задаем utf8 кодировку для Windows
    if not os.environ.get('DATABASE_URL'):
        conn = psycopg2.connect(DATABASE_URL, client_encoding='utf8')
    else:
        conn = psycopg2.connect(DATABASE_URL)
    return conn


def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS players (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            clicks BIGINT DEFAULT 0,
            multiplier INT DEFAULT 1,
            auto_clickers INT DEFAULT 0,
            name_color TEXT DEFAULT '#28a745'
        );
    ''')

    try:
        cur.execute("ALTER TABLE players ADD COLUMN IF NOT EXISTS name_color TEXT DEFAULT '#28a745';")
    except Exception:
        pass

    conn.commit()
    cur.close()
    conn.close()


# Запускаем создание таблиц
init_db()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    if not username:
        return jsonify({"success": False, "message": "Имя не может быть пустым!"}), 400

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Ищем игрока в базе данных
    cur.execute('SELECT * FROM players WHERE username = %s', (username,))
    player = cur.fetchone()

    if player:
        if player['password'] == password:
            cur.close()
            conn.close()
            return jsonify({"success": True, "data": player})
        cur.close()
        conn.close()
        return jsonify({"success": False, "message": "Неверный пароль!"}), 401

    # Если игрока нет — регистрируем нового
    cur.execute('''
        INSERT INTO players (username, password, clicks, multiplier, auto_clickers)
        VALUES (%s, %s, 0, 1, 0) RETURNING *
    ''', (username, password))

    new_player = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"success": True, "data": new_player})


@app.route('/click', methods=['POST'])
def click():
    data = request.json
    username = data.get('username')
    if not username:
        return jsonify({"error": "No username"}), 400

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute('SELECT clicks, multiplier FROM players WHERE username = %s', (username,))
    player = cur.fetchone()

    if player:
        # --- ЛОГИКА КРИТИЧЕСКОГО КЛИКА ---
        is_crit = random.random() < 0.08  # Шанс 8% на критический клик
        bonus = player['multiplier']

        if is_crit:
            bonus = player['multiplier'] * 10  # Крит дает х10 от твоего клика!

        new_clicks = player['clicks'] + bonus
        cur.execute('UPDATE players SET clicks = %s WHERE username = %s', (new_clicks, username))
        conn.commit()

        cur.close()
        conn.close()
        return jsonify({"clicks": new_clicks, "is_crit": is_crit, "bonus": bonus})

    cur.close()
    conn.close()
    return jsonify({"error": "User not found"}), 44


@app.route('/get_profile', methods=['POST'])
def get_profile():
    data = request.json
    username = data.get('username')
    if not username:
        return jsonify({"success": False, "message": "Не указан ник"})

    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute('SELECT clicks, multiplier, auto_clickers FROM players WHERE username = %s', (username,))
        player = cur.fetchone()
        cur.close()
        conn.close()

        if player:
            return jsonify({"success": True, "data": player})
        return jsonify({"success": False, "message": "Игрок не найден"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@app.route('/autoclick_server', methods=['POST'])
def autoclick_server():
    username = request.json.get('username')
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Проверяем, сколько автокликеров у игрока
    cur.execute('SELECT auto_clickers FROM players WHERE username = %s', (username,))
    player = cur.fetchone()

    if player and player['auto_clickers'] > 0:
        auto_count = player['auto_clickers']
        # Начисляем клики
        cur.execute('''
            UPDATE players 
            SET clicks = clicks + %s 
            WHERE username = %s 
            RETURNING clicks
        ''', (auto_count, username))

        result = cur.fetchone()
        conn.commit()
        print(f"--- Автоклик: {username} +{auto_count} (Итого: {result['clicks']})")

        cur.close()
        conn.close()
        return jsonify({"success": True, "clicks": result['clicks']})

    cur.close()
    conn.close()
    return jsonify({"success": False})


@app.route('/buy', methods=['POST'])
def buy():
    data = request.json
    username = data.get('username')
    item = data.get('item')

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('SELECT clicks, multiplier, auto_clickers FROM players WHERE username = %s', (username,))
    player = cur.fetchone()

    if not player:
        cur.close()
        conn.close()
        return jsonify({"success": False, "message": "User not found"})

    clicks = player['clicks']

    if item == 'double':
        cost = 100 * player['multiplier']
        if clicks >= cost:
            cur.execute('UPDATE players SET clicks = clicks - %s, multiplier = multiplier + 1 WHERE username = %s',
                        (cost, username))
            conn.commit()
        else:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Недостаточно кликов!"})

    elif item == 'auto':
        cost = 50 * (player['auto_clickers'] + 1)
        if clicks >= cost:
            cur.execute(
                'UPDATE players SET clicks = clicks - %s, auto_clickers = auto_clickers + 1 WHERE username = %s',
                (cost, username))
            conn.commit()
        else:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Недостаточно кликов!"})

    elif item == 'color_red':
        cost = 1000
        if clicks >= cost:
            cur.execute("UPDATE players SET clicks = clicks - %s, name_color = '#ff4757' WHERE username = %s",
                        (cost, username))
            conn.commit()
        else:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Нужно 1,000 очков для Красного ника!"})

    elif item == 'color_gold':
        cost = 5000
        if clicks >= cost:
            cur.execute("UPDATE players SET clicks = clicks - %s, name_color = '#ffa500' WHERE username = %s",
                        (cost, username))
            conn.commit()
        else:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Нужно 5,000 очков для Золотого ника!"})

    cur.execute('SELECT clicks, multiplier, auto_clickers FROM players WHERE username = %s', (username,))
    updated = cur.fetchone()
    cur.close()
    conn.close()
    return jsonify({"success": True, "clicks": updated['clicks'], "multiplier": updated['multiplier'],
                    "auto": updated['auto_clickers']})


@app.route('/top', methods=['GET'])
def get_top():
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute('SELECT username, clicks, name_color FROM players ORDER BY clicks DESC LIMIT 10;')
        top_players = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(top_players)
    except Exception:
        return jsonify([])


@app.route('/chat', methods=['GET', 'POST'])
def chat():
    conn = get_db_connection()

    if request.method == 'POST':
        user_msg = request.json.get('username', 'Аноним')
        text_msg = request.json.get('text', '').strip()
        if text_msg:
            cur = conn.cursor()
            cur.execute('''
                INSERT INTO chat (username, text, time) 
                VALUES (%s, %s, %s)
            ''', (user_msg, text_msg, datetime.now().strftime("%H:%M")))
            conn.commit()
            cur.close()
        conn.close()
        return jsonify({"success": True})

    # GET запрос: соединяем таблицу чата с таблицей игроков (JOIN), чтобы забрать цвет каждого автора
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('''
        SELECT chat.username as user, chat.text, chat.time, COALESCE(players.name_color, '#28a745') as color
        FROM chat
        LEFT JOIN players ON chat.username = players.username
        ORDER BY chat.id DESC LIMIT 15
    ''')
    messages = cur.fetchall()
    cur.close()
    conn.close()

    return jsonify(list(reversed(messages)))


@app.route('/admin')
def admin():
    auth = request.authorization
    if not auth or not (auth.username == 'admin' and auth.password == 'qwerty1234'):
        return Response('Admin only', 401, {'WWW-Authenticate': 'Basic realm="Login"'})

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('SELECT * FROM players')
    all_players = cur.fetchall()
    cur.close()
    conn.close()

    players_dict = {p['username']: p for p in all_players}
    return render_template('admin.html', players=players_dict)


@app.route('/admin/clear_chat', methods=['POST'])
def admin_clear_chat():
    # Проверяем пароль админа, как и на самой странице админки
    auth = request.authorization
    if not auth or not (auth.username == 'admin' and auth.password == 'qwerty1234'):
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # Очищаем таблицу чата полностью
        cur.execute('DELETE FROM chat;')
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"success": True, "message": "Чат успешно очищен!"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/support', methods=['GET', 'POST'])
def support():
    conn = get_db_connection()

    if request.method == 'POST':
        data = request.json
        user_msg = data.get('username')
        text_msg = data.get('text', '').strip()
        sender = data.get('sender', user_msg)

        if text_msg and user_msg:
            cur = conn.cursor()
            cur.execute('''
                INSERT INTO support_messages (username, sender, text, time) 
                VALUES (%s, %s, %s, %s)
            ''', (user_msg, sender, text_msg, datetime.now().strftime("%H:%M")))
            conn.commit()
            cur.close()

        conn.close()
        return jsonify({"success": True})

    # GET запрос (все эти строки должны быть внутри функции!)
    username = request.args.get('username')
    if not username:
        conn.close()
        return jsonify([])

    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('''
        SELECT sender, text, time FROM support_messages 
        WHERE username = %s ORDER BY id ASC
    ''', (username,))
    messages = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(messages)


@app.route('/admin/support_chats', methods=['GET'])
def admin_support_chats():
    auth = request.authorization
    if not auth or not (auth.username == 'admin' and auth.password == 'qwerty1234'):
        return jsonify({"success": False}), 401

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    try:
        # Берем просто список всех уникальных ников, кто вообще когда-либо писал
        cur.execute('SELECT DISTINCT username FROM support_messages;')
        chats = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(chats)
    except Exception as e:
        print("Ошибка при получении списка чатов в админке:", e)
        if conn:
            conn.close()
        return jsonify([])


def init_db():
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Создаем таблицу для техподдержки
        cur.execute('''
            CREATE TABLE IF NOT EXISTS support_messages (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) NOT NULL,
                sender VARCHAR(50) NOT NULL,
                text TEXT NOT NULL,
                time VARCHAR(10) NOT NULL,
                is_read BOOLEAN DEFAULT FALSE
            );
        ''')

        conn.commit()
        cur.close()
        conn.close()
        print("База данных успешно проверена и обновлена!")
    except Exception as e:
        print("Ошибка при создании таблицы поддержки:", e)


if __name__ == '__main__':
    init_db()
    app.run(debug=True)
    app.run(host='0.0.0.0', port=5000)