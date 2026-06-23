# Courier App

Веб-приложение для управления почтовыми курьерами.

## 🚀 Функционал

- Регистрация и вход курьеров
- Панель администратора
- Создание папок для курьеров
- Загрузка и сжатие фотографий
- Поиск и фильтрация курьеров

## 📦 Установка

```bash
# 1. Клонировать репозиторий
git clone <your-repo-url>
cd CourierApp_Final

# 2. Создать виртуальное окружение
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# 3. Установить зависимости
pip install -r requirements.txt

# 4. Создать файл .env из шаблона
cp .env.example .env

# 5. Сгенерировать секретный ключ
python -c "import secrets; print(secrets.token_hex(32))"
# Вставить полученный ключ в .env в SECRET_KEY

# 6. Запустить
python app.py