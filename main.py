from flask import Flask, render_template, request, jsonify, Response
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

app = Flask(__name__)

# Берём URL базы данных из настроек Render. Если запускаем локально — можно вписать внутренний или внешний URL
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://admin:EVwq9lS8WmCbqQkjgdb57pLvZc1YT5B4@dpg-d862i10jo89c7384a9ug-a/clicker_db_t59u')


def get_db_connection():
    # Функция для быстрого подключения к базе данных
    conn = psycopg2.connect(DATABASE_URL)
    return conn


def init_db():
    # Эта функция сама создаст нужные таблицы в базе данных при старте приложения
    conn = get_db_connection()
    cur = conn.cursor()

    # Таблица для игроков
    cur.execute('''
        CREATE TABLE IF NOT EXISTS players (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            clicks BIGINT DEFAULT 0,
            multiplier INT DEFAULT 1,
            auto_clickers INT DEFAULT 0
        );
    ''')

    # Таблица для чата
    cur.execute('''
        CREATE TABLE IF NOT EXISTS chat (
            id SERIAL PRIMARY KEY,
            username TEXT NOT NULL,
            text TEXT NOT NULL,
            time TEXT NOT NULL
        );
    ''')

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
    username = request.json.get('username')
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Обновляем клики: прибавляем текущий multiplier игрока
    cur.execute('''
        UPDATE players 
        SET clicks = clicks + multiplier 
        WHERE username = %s 
        RETURNING clicks
    ''', (username,))

    result = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()

    if result:
        return jsonify({"success": True, "clicks": result['clicks']})
    return jsonify({"success": False}), 404


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
    username, item = data.get('username'), data.get('item')

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute('SELECT clicks, multiplier, auto_clickers FROM players WHERE username = %s', (username,))
    p = cur.fetchone()

    if not p:
        cur.close()
        conn.close()
        return jsonify({"success": False})

    if item == 'double':
        cost = 100 * p['multiplier']
        if p['clicks'] >= cost:
            cur.execute('''
                UPDATE players 
                SET clicks = clicks - %s, multiplier = multiplier + 1 
                WHERE username = %s 
                RETURNING clicks, multiplier, auto_clickers
            ''', (cost, username))
        else:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Мало кликов!"})

    elif item == 'auto':
        cost = 50 * (p['auto_clickers'] + 1)
        if p['clicks'] >= cost:
            cur.execute('''
                UPDATE players 
                SET clicks = clicks - %s, auto_clickers = auto_clickers + 1 
                WHERE username = %s 
                RETURNING clicks, multiplier, auto_clickers
            ''', (cost, username))
        else:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Мало кликов!"})

    updated_p = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()

    return jsonify({
        "success": True,
        "clicks": updated_p['clicks'],
        "multiplier": updated_p['multiplier'],
        "auto": updated_p['auto_clickers']
    })


@app.route('/top', methods=['GET'])
def get_top():
    conn = get_db_connection()
    cur = conn.cursor()


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

    # GET запрос: возвращаем последние 15 сообщений
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('SELECT username as user, text, time FROM chat ORDER BY id DESC LIMIT 15')
    messages = cur.fetchall()
    cur.close()
    conn.close()

    # Разворачиваем список, чтобы старые сообщения были сверху, а новые снизу
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

    # Превращаем список игроков обратно в словарь для админки
    players_dict = {p['username']: p for p in all_players}
    return render_template('admin.html', players=players_dict)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)