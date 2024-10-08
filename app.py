from flask import Flask, render_template, request, redirect, session, send_from_directory, render_template_string
import sqlite3
import os
import threading
import time

app = Flask(__name__)
app.secret_key = 'supersecretkey'

# Подключение к базе данных
conn = sqlite3.connect('users.db', check_same_thread=False)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Создание таблицы пользователей (если её ещё нет)
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    tokens INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1,
    is_admin INTEGER DEFAULT 0,
    is_banned INTEGER DEFAULT 0
)
''')
conn.commit()

# Создание таблицы майнеров (если её ещё нет)
cursor.execute('''
CREATE TABLE IF NOT EXISTS miners (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    price INTEGER NOT NULL,
    production_rate INTEGER NOT NULL
)
''')
conn.commit()

# Создание таблицы для хранения майнеров, купленных пользователями
cursor.execute('''
CREATE TABLE IF NOT EXISTS user_miners (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    miner_id INTEGER NOT NULL,
    FOREIGN KEY (username) REFERENCES users(username),
    FOREIGN KEY (miner_id) REFERENCES miners(id)
)
''')
conn.commit()

# Добавление майнеров в базу данных (если их ещё нет)
miners = [
    ('Basic Miner', 100, 1),
    ('Advanced Miner', 500, 5),
    ('Pro Miner', 1000, 10)
]
cursor.executemany('''
INSERT INTO miners (name, price, production_rate) VALUES (?, ?, ?)
''', miners)
conn.commit()

# Функция для расчета, сколько токенов нужно для следующего уровня
def tokens_for_next_level(current_level):
    return 50 * current_level

# Функция для начисления токенов за майнеров
def generate_tokens_for_miners():
    cursor.execute('SELECT username FROM users')
    users = cursor.fetchall()

    for user in users:
        username = user['username']

        # Получаем майнеров пользователя
        cursor.execute('''
            SELECT SUM(m.production_rate) AS total_rate 
            FROM user_miners um
            JOIN miners m ON um.miner_id = m.id
            WHERE um.username = ?
        ''', (username,))
        total_rate = cursor.fetchone()['total_rate'] or 0

        # Начисляем токены пользователю
        if total_rate > 0:
            cursor.execute('UPDATE users SET tokens = tokens + ? WHERE username = ?', (total_rate, username))
    
    conn.commit()

# Запуск начисления токенов каждые N секунд
def start_token_generation():
    def token_loop():
        while True:
            generate_tokens_for_miners()
            time.sleep(60)  # Начисление токенов каждые 60 секунд

    thread = threading.Thread(target=token_loop)
    thread.daemon = True
    thread.start()

start_token_generation()

# Маршрут для главной страницы
@app.route('/')
def home():
    if 'username' not in session:
        return redirect('/login')

    username = session['username']
    
    cursor.execute("SELECT tokens, level, is_admin FROM users WHERE username = ?", (username,))
    user_data = cursor.fetchone()

    if user_data is None:
        return redirect('/login')

    tokens, level, is_admin = user_data
    tokens_needed = tokens_for_next_level(level)

    return render_template('index.html', tokens=tokens, level=level, tokens_needed=tokens_needed, is_admin=is_admin)

# Маршрут для входа
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()

        if user is None:
            return "Пользователь не найден", 404

        # Проверяем, забанен ли пользователь
        if user['is_banned'] == 1:
            return "Вы забанены", 403

        stored_password = user['password']

        if password != stored_password:
            return "Неверный пароль", 403

        # Успешный вход
        session['username'] = username
        return redirect('/')
    
    return render_template('login.html')

# Маршрут для регистрации
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        try:
            cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
            conn.commit()
            return redirect('/login')
        except sqlite3.IntegrityError:
            return "Имя пользователя уже занято"

    return render_template('register.html')

# Магазин майнеров
@app.route('/shop', methods=['GET', 'POST'])
def shop():
    if 'username' not in session:
        return redirect('/login')

    username = session['username']
    
    if request.method == 'POST':
        miner_id = request.form['miner_id']

        # Получаем информацию о выбранном майнере
        cursor.execute("SELECT name, price, production_rate FROM miners WHERE id = ?", (miner_id,))
        miner = cursor.fetchone()

        if miner is None:
            return "Майнер не найден", 404

        miner_name, miner_price, miner_production_rate = miner

        # Получаем текущие токены пользователя
        cursor.execute("SELECT tokens FROM users WHERE username = ?", (username,))
        user_tokens = cursor.fetchone()[0]

        # Проверяем, достаточно ли токенов для покупки
        if user_tokens < miner_price:
            return "Недостаточно токенов для покупки", 403

        # Списываем токены за майнер
        new_token_balance = user_tokens - miner_price
        cursor.execute("UPDATE users SET tokens = ? WHERE username = ?", (new_token_balance, username))
        conn.commit()

        # Добавляем майнер пользователю
        cursor.execute("INSERT INTO user_miners (username, miner_id) VALUES (?, ?)", (username, miner_id))
        conn.commit()

        return redirect('/shop')

    # Получаем список всех майнеров для отображения в магазине
    cursor.execute("SELECT id, name, price, production_rate FROM miners")
    miners = cursor.fetchall()

    return render_template('shop.html', miners=miners)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
    
