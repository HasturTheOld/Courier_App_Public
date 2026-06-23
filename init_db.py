# init_db.py
from app import app, db
from werkzeug.security import generate_password_hash
import os

with app.app_context():
    print("🔧 Создание таблиц...")
    db.create_all()
    print("✅ Таблицы созданы")
    
    # Импортируем модели после создания таблиц
    from app import Courier
    
    # Создаем администратора
    login = os.environ.get('ADMIN_LOGIN', 'The_Best_Admin')
    password = os.environ.get('ADMIN_PASSWORD', 'HG10P4NC91')
    
    admin = Courier.query.filter_by(is_admin=True).first()
    if not admin:
        hashed_password = generate_password_hash(password)
        admin = Courier(
            first_name='Admin',
            last_name=login,
            city='System',
            password=hashed_password,
            is_admin=True
        )
        db.session.add(admin)
        db.session.commit()
        print(f"✅ Администратор создан: {login}")
    else:
        print(f"✅ Администратор уже существует: {admin.last_name}")
    
    print("✅ Инициализация завершена")
