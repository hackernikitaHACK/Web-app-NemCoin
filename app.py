from flask import Flask, render_template, request, redirect, session, send_from_directory, render_template_string
import sqlite3
import os

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

# Функция для расчета, сколько токенов нужно для следующего уровня
def tokens_for_next_level(current_level):
    return 50 * current_level

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


# Маршрут для выхода
@app.route('/logout', methods=['POST'])
def logout():
    session.pop('username', None)
    return redirect('/login')

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

# Получение токенов (увеличение токенов и проверка уровня)
@app.route('/get_token', methods=['POST'])
def get_token():
    if 'username' not in session:
        return redirect('/login')

    username = session['username']
    
    # Получаем текущие токены и уровень пользователя
    cursor.execute("SELECT tokens, level FROM users WHERE username = ?", (username,))
    user_data = cursor.fetchone()
    current_tokens, current_level = user_data
    
    # Увеличиваем количество токенов
    new_tokens = current_tokens + 1
    
    # Проверяем, нужно ли повысить уровень
    tokens_needed = tokens_for_next_level(current_level)
    
    if new_tokens >= tokens_needed:
        # Увеличиваем уровень и сбрасываем токены
        current_level += 1
        new_tokens = 0
    
    # Обновляем пользователя в базе данных
    cursor.execute("UPDATE users SET tokens = ?, level = ? WHERE username = ?", (new_tokens, current_level, username))
    conn.commit()

    return redirect('/')

# Панель администратора
@app.route('/admin')
def admin_panel():
    if 'username' not in session:
        return redirect('/login')

    username = session['username']
    cursor.execute("SELECT is_admin FROM users WHERE username = ?", (username,))
    is_admin = cursor.fetchone()[0]

    if is_admin == 1:
        return render_template('admin.html')
    else:
        return "Доступ запрещен", 403

# Выдать админку
@app.route('/grant_admin', methods=['GET', 'POST'])
def grant_admin():
    if 'username' not in session:
        return redirect('/login')
    
    username = session['username']
    cursor.execute("SELECT is_admin FROM users WHERE username = ?", (username,))
    is_admin = cursor.fetchone()[0]

    if is_admin == 1:
        if request.method == 'POST':
            user_to_grant = request.form['username']
            cursor.execute("UPDATE users SET is_admin = 1 WHERE username = ?", (user_to_grant,))
            conn.commit()
            return redirect('/admin')
        
        return render_template('grant_admin.html')
    else:
        return "Доступ запрещен", 403

# Разжаловать администратора
@app.route('/revoke_admin', methods=['POST'])
def revoke_admin():
    if 'username' not in session:
        return redirect('/login')

    username = session['username']
    cursor.execute("SELECT is_admin FROM users WHERE username = ?", (username,))
    is_admin = cursor.fetchone()[0]

    if is_admin == 1:
        user_to_revoke = request.form['username']
        cursor.execute("UPDATE users SET is_admin = 0 WHERE username = ?", (user_to_revoke,))
        conn.commit()
        return redirect('/admin')
    else:
        return "Доступ запрещен", 403

# Маршрут для отображения списка пользователей
@app.route('/users', methods=['GET'])
def list_users():
    cursor.execute("SELECT id, username, level, tokens FROM users")
    users = cursor.fetchall()

    html = '''
    <h1>Список пользователей</h1>
    <table border="1">
        <tr>
            <th>ID</th>
            <th>Имя пользователя</th>
            <th>Уровень</th>
            <th>Токены</th>
        </tr>
        {% for user in users %}
        <tr>
            <td>{{ user['id'] }}</td>
            <td>{{ user['username'] }}</td>
            <td>{{ user['level'] }}</td>
            <td>{{ user['tokens'] }}</td>
        </tr>
        {% endfor %}
    </table>
    '''
    return render_template_string(html, users=users)

# Скачать файл
@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory('directory_with_files', filename)

# Маршрут для таблицы лидеров
@app.route('/leaderboard', methods=['GET'])
def leaderboard():
    # Получаем всех пользователей, сортируя по количеству токенов или уровню
    cursor.execute("SELECT id, username, level, tokens FROM users ORDER BY tokens DESC, level DESC")
    users = cursor.fetchall()

    # HTML-шаблон для отображения таблицы лидеров
    html = '''
    <h1>Таблица лидеров</h1>
    <table border="1">
        <tr>
            <th>Место</th>
            <th>Имя пользователя</th>
            <th>Уровень</th>
            <th>Токены</th>
        </tr>
        {% for index, user in enumerate(users, start=1) %}
        <tr>
            <td>{{ index }}</td>
            <td>{{ user['username'] }}</td>
            <td>{{ user['level'] }}</td>
            <td>{{ user['tokens'] }}</td>
        </tr>
        {% endfor %}
    </table>
    '''
    return render_template_string(html, users=users)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
    
