from flask import Flask, render_template, request, redirect, session, send_from_directory, render_template_string, send_file, flash
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
    last_mining_time INTEGER DEFAULT 0
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
cursor.execute("SELECT COUNT(*) as count FROM miners")
miner_count = cursor.fetchone()['count']
if miner_count == 0:
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
    
    cursor.execute("SELECT tokens, level, is_admin, last_mining_time FROM users WHERE username = ?", (username,))
    user_data = cursor.fetchone()

    if user_data is None:
        return redirect('/login')

    tokens, level, is_admin, last_mining_time = user_data
    tokens_needed = tokens_for_next_level(level)

    cursor.execute('''
        SELECT m.production_rate 
        FROM user_miners um 
        JOIN miners m ON um.miner_id = m.id 
        WHERE um.username = ?
    ''', (username,))
    user_miners = cursor.fetchall()

    total_production_rate = sum([miner['production_rate'] for miner in user_miners])

    current_time = int(time.time())
    if current_time - last_mining_time >= 60:
        tokens += total_production_rate
        cursor.execute("UPDATE users SET tokens = ?, last_mining_time = ? WHERE username = ?", (tokens, current_time, username))
        conn.commit()

    return render_template('index.html', tokens=tokens, level=level, tokens_needed=tokens_needed, is_admin=is_admin)

# Маршрут для регистрации
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if not username or not password:
            flash('Имя пользователя и пароль обязательны.')
            return redirect('/register')

        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        existing_user = cursor.fetchone()

        if existing_user:
            flash('Это имя пользователя уже занято. Попробуйте другое.')
            return redirect('/register')

        try:
            cursor.execute("INSERT INTO users (username, password, tokens, level, last_mining_time) VALUES (?, ?, ?, ?, ?)", 
                           (username, password, 49, 1, int(time.time())))
            conn.commit()
        except sqlite3.IntegrityError:
            flash('Ошибка при регистрации. Попробуйте снова.')
            return redirect('/register')

        flash('Вы успешно зарегистрировались! Теперь войдите в систему.')
        return redirect('/login')

    return render_template('register.html')

# Маршрут для входа в систему
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        cursor.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
        user = cursor.fetchone()

        if user:
            if user['is_banned']:
                flash('Вы заблокированы.')
                return redirect('/login')
            
            session['username'] = username
            return redirect('/')
        else:
            flash('Неправильное имя пользователя или пароль.')
            return redirect('/login')

    return render_template('login.html')

# Маршрут для выхода из системы
@app.route('/logout', methods=['GET', 'POST'])
def logout():
    session.pop('username', None)
    return redirect('/login')

# Маршрут для получения токенов
@app.route('/get_token', methods=['POST'])
def get_token():
    if 'username' not in session:
        return redirect('/login')

    username = session['username']

    cursor.execute("SELECT tokens, last_mining_time FROM users WHERE username = ?", (username,))
    user_data = cursor.fetchone()

    if user_data is None:
        return redirect('/login')

    tokens, last_mining_time = user_data['tokens'], user_data['last_mining_time']

    current_time = int(time.time())
    time_difference = current_time - last_mining_time

    if time_difference >= 60:
        tokens += 1
        cursor.execute("UPDATE users SET tokens = ?, last_mining_time = ? WHERE username = ?", 
                       (tokens, current_time, username))
        conn.commit()

    return redirect('/')

# Маршрут для магазина майнеров
@app.route('/shop', methods=['GET', 'POST'])
def shop():
    if 'username' not in session:
        return redirect('/login')

    username = session['username']
    
    if request.method == 'POST':
        miner_id = request.form.get('miner_id')

        if not miner_id:
            return "Ошибка: не выбран майнер", 400

        cursor.execute("SELECT name, price, production_rate FROM miners WHERE id = ?", (miner_id,))
        miner = cursor.fetchone()

        if miner is None:
            return "Майнер не найден", 404

        miner_name, miner_price, miner_production_rate = miner

        cursor.execute("SELECT tokens FROM users WHERE username = ?", (username,))
        user_tokens = cursor.fetchone()[0]

        if user_tokens < miner_price:
            return "Недостаточно токенов для покупки", 403

        new_token_balance = user_tokens - miner_price
        cursor.execute("UPDATE users SET tokens = ? WHERE username = ?", (new_token_balance, username))
        conn.commit()

        cursor.execute("INSERT INTO user_miners (username, miner_id) VALUES (?, ?)", (username, miner_id))
        conn.commit()

        flash(f'Вы успешно приобрели {miner_name}!')
        return redirect('/shop')

    cursor.execute("SELECT id, name, price, production_rate FROM miners")
    miners = cursor.fetchall()

    return render_template('shop.html', miners=miners)

# Админ панель и управление пользователями
@app.route('/admin')
def admin_panel():
    if 'username' not in session:
        return redirect('/login')

    username = session['username']
    cursor.execute("SELECT is_admin FROM users WHERE username = ?", (username,))
    is_admin = cursor.fetchone()[0]

    if is_admin == 1:
        cursor.execute("SELECT id, username, is_admin, is_banned FROM users")
        users = cursor.fetchall()
        return render_template('admin.html', users=users)
    else:
        return "Доступ запрещен", 403

# Выдать админку
@app.route('/grant_admin', methods=['POST'])
def grant_admin():
    if 'username' not in session:
        return redirect('/login')
    
    current_username = session['username']
    cursor.execute("SELECT is_admin FROM users WHERE username = ?", (current_username,))
    is_admin = cursor.fetchone()[0]

    if is_admin == 1:
        user_to_grant = request.form['username']
        cursor.execute("UPDATE users SET is_admin = 1 WHERE username = ?", (user_to_grant,))
        conn.commit()
        flash(f'Пользователь {user_to_grant} теперь администратор.')
        return redirect('/admin')
    else:
        return "Доступ запрещен", 403

# Разжаловать администратора
@app.route('/revoke_admin', methods=['POST'])
def revoke_admin():
    if 'username' not in session:
        return redirect('/login')

    current_username = session['username']
    cursor.execute("SELECT is_admin FROM users WHERE username = ?", (current_username,))
    is_admin = cursor.fetchone()[0]

    if is_admin == 1:
        user_to_revoke = request.form['username']
        cursor.execute("UPDATE users SET is_admin = 0 WHERE username = ?", (user_to_revoke,))
        conn.commit()
        flash(f'Пользователь {user_to_revoke} больше не администратор.')
        return redirect('/admin')
    else:
        return "Доступ запрещен", 403

# Забанить пользователя
@app.route('/ban_user', methods=['POST'])
def ban_user():
    if 'username' not in session:
        return redirect('/login')

    current_username = session['username']
    cursor.execute("SELECT is_admin FROM users WHERE username = ?", (current_username,))
    is_admin = cursor.fetchone()[0]

    if is_admin == 1:
        user_to_ban = request.form['username']
        cursor.execute("UPDATE users SET is_banned = 1 WHERE username = ?", (user_to_ban,))
        conn.commit()
        flash(f'Пользователь {user_to_ban} заблокирован.')
        return redirect('/admin')
    else:
        return "Доступ запрещен", 403

# Разбанить пользователя
@app.route('/unban_user', methods=['POST'])
def unban_user():
    if 'username' not in session:
        return redirect('/login')

    current_username = session['username']
    cursor.execute("SELECT is_admin FROM users WHERE username = ?", (current_username,))
    is_admin = cursor.fetchone()[0]

    if is_admin == 1:
        user_to_unban = request.form['username']
        cursor.execute("UPDATE users SET is_banned = 0 WHERE username = ?", (user_to_unban,))
        conn.commit()
        flash(f'Пользователь {user_to_unban} разблокирован.')
        return redirect('/admin')
    else:
        return "Доступ запрещен", 403

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=port)
           
