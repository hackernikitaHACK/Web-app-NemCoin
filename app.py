from flask import Flask, render_template, request, redirect, session, send_from_directory, render_template_string, send_file
import sqlite3
import os
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
    tokens INTEGER DEFAULT 49,
    level INTEGER DEFAULT 1,
    is_admin INTEGER DEFAULT 0,
    is_banned INTEGER DEFAULT 0,
    last_mining_time INTEGER DEFAULT 0  -- Новое поле для хранения времени последнего начисления
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
    ('Basic Miner', 49, 1),
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

# Маршрут для главной страницы
@app.route('/')
def home():
    if 'username' not in session:
        return redirect('/login')

    username = session['username']
    
    # Получаем данные пользователя
    cursor.execute("SELECT tokens, level, is_admin, last_mining_time FROM users WHERE username = ?", (username,))
    user_data = cursor.fetchone()

    if user_data is None:
        return redirect('/login')

    tokens, level, is_admin, last_mining_time = user_data
    tokens_needed = tokens_for_next_level(level)

    # Получаем список всех майнеров, которыми владеет пользователь
    cursor.execute('''
        SELECT m.production_rate 
        FROM user_miners um 
        JOIN miners m ON um.miner_id = m.id 
        WHERE um.username = ?
    ''', (username,))
    user_miners = cursor.fetchall()

    # Суммируем производительность всех майнеров
    total_production_rate = sum([miner['production_rate'] for miner in user_miners])

    # Проверяем, прошло ли больше 60 секунд с последнего начисления токенов
    current_time = int(time.time())  # Текущее время в секундах
    if current_time - last_mining_time >= 60:
        # Начисляем токены пользователю за все майнеры
        tokens += total_production_rate
        
        # Обновляем время последнего начисления и количество токенов в базе данных
        cursor.execute("UPDATE users SET tokens = ?, last_mining_time = ? WHERE username = ?", (tokens, current_time, username))
        conn.commit()

    return render_template('index.html', tokens=tokens, level=level, tokens_needed=tokens_needed, is_admin=is_admin)

# Маршрут для регистрации
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Проверка, что поля не пустые
        if not username or not password:
            flash('Имя пользователя и пароль обязательны.')
            return redirect('/register')

        # Проверка на существующего пользователя
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        existing_user = cursor.fetchone()

        if existing_user:
            flash('Это имя пользователя уже занято. Попробуйте другое.')
            return redirect('/register')

        # Добавление нового пользователя без хеширования пароля
        cursor.execute("INSERT INTO users (username, password, tokens, level, last_mining_time) VALUES (?, ?, ?, ?, ?)", 
                       (username, password, 49, 1, int(time.time())))
        conn.commit()

        flash('Вы успешно зарегистрировались! Теперь войдите в систему.')
        return redirect('/login')

    return render_template('register.html')

# Маршрут для получения токенов
@app.route('/get_token', methods=['POST'])
def get_token():
    if 'username' not in session:
        return redirect('/login')

    username = session['username']

    # Получаем данные пользователя
    cursor.execute("SELECT tokens, last_mining_time FROM users WHERE username = ?", (username,))
    user_data = cursor.fetchone()

    if user_data is None:
        return redirect('/login')

    tokens, last_mining_time = user_data['tokens'], user_data['last_mining_time']

    current_time = int(time.time())
    time_difference = current_time - last_mining_time

    print(f"Текущие токены: {tokens}, последнее начисление: {last_mining_time}, текущая разница: {time_difference} секунд")

    # Проверяем, прошло ли больше 60 секунд с последнего начисления токенов
    if time_difference >= 60:
        tokens += 1
        cursor.execute("UPDATE users SET tokens = ?, last_mining_time = ? WHERE username = ?", 
                       (tokens, current_time, username))
        conn.commit()
        print(f"Токены обновлены! Новое количество токенов: {tokens}")
    else:
        print(f"Прошло недостаточно времени для начисления токенов. Осталось {60 - time_difference} секунд.")

    return redirect('/')
    
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
    
