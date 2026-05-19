from flask import Flask, render_template, request, jsonify, Response
import json
import os
from datetime import datetime

app = Flask(__name__)

DATA_FILE = 'database.json'
CHAT_FILE = 'chat.json'

def load_data(file):
    if not os.path.exists(file):
        return [] if file == CHAT_FILE else {}
    try:
        with open(file, 'r', encoding='utf-8') as f:
            data = f.read().strip()
            return json.loads(data) if data else ([] if file == CHAT_FILE else {})
    except:
        return [] if file == CHAT_FILE else {}

def save_data(file, data):
    with open(file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    players = load_data(DATA_FILE)
    if username in players:
        if players[username].get('password') == password:
            return jsonify({"success": True, "data": players[username]})
        return jsonify({"success": False, "message": "Неверный пароль!"}), 401
    players[username] = {"clicks": 0, "password": password, "multiplier": 1, "auto_clickers": 0}
    save_data(DATA_FILE, players)
    return jsonify({"success": True, "data": players[username]})

@app.route('/click', methods=['POST'])
def click():
    username = request.json.get('username')
    players = load_data(DATA_FILE)
    if username in players:
        players[username]['clicks'] += players[username].get('multiplier', 1)
        save_data(DATA_FILE, players)
        return jsonify({"success": True, "clicks": players[username]['clicks']})
    return jsonify({"success": False}), 404

# ВОТ ЭТА ФУНКЦИЯ ТЕПЕРЬ РАБОТАЕТ ПО-НАСТОЯЩЕМУ
@app.route('/autoclick_server', methods=['POST'])
def autoclick_server():
    username = request.json.get('username')
    players = load_data(DATA_FILE)
    if username in players:
        auto_count = players[username].get('auto_clickers', 0)
        if auto_count > 0:
            players[username]['clicks'] += auto_count
            save_data(DATA_FILE, players)
            print(f"--- Автоклик: {username} +{auto_count} (Итого: {players[username]['clicks']})")
            return jsonify({"success": True, "clicks": players[username]['clicks']})
    return jsonify({"success": False})

@app.route('/buy', methods=['POST'])
def buy():
    data = request.json
    username, item = data.get('username'), data.get('item')
    players = load_data(DATA_FILE)
    p = players.get(username)
    if not p: return jsonify({"success": False})
    if item == 'double':
        cost = 100 * p.get('multiplier', 1)
        if p['clicks'] >= cost:
            p['clicks'] -= cost
            p['multiplier'] = p.get('multiplier', 1) + 1
        else: return jsonify({"success": False, "message": "Мало кликов!"})
    elif item == 'auto':
        cost = 50 * (p.get('auto_clickers', 0) + 1)
        if p['clicks'] >= cost:
            p['clicks'] -= cost
            p['auto_clickers'] = p.get('auto_clickers', 0) + 1
        else: return jsonify({"success": False, "message": "Мало кликов!"})
    save_data(DATA_FILE, players)
    return jsonify({"success": True, "clicks": p['clicks'], "multiplier": p['multiplier'], "auto": p['auto_clickers']})

@app.route('/chat', methods=['GET', 'POST'])
def chat():
    messages = load_data(CHAT_FILE)
    if request.method == 'POST':
        user_msg = request.json.get('username', 'Аноним')
        text_msg = request.json.get('text', '').strip()
        if text_msg:
            messages.append({"user": user_msg, "text": text_msg, "time": datetime.now().strftime("%H:%M")})
            save_data(CHAT_FILE, messages[-15:])
        return jsonify({"success": True})
    return jsonify(messages)

@app.route('/admin')
def admin():
    auth = request.authorization
    if not auth or not (auth.username == 'admin' and auth.password == 'qwerty1234'):
        return Response('Admin only', 401, {'WWW-Authenticate': 'Basic realm="Login"'})
    return render_template('admin.html', players=load_data(DATA_FILE))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

# npx localtunnel --port 5000
#.\ngrok http 5000
#109.196.69.125