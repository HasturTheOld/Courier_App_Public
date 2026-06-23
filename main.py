from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import secrets
import json
import shutil
import logging
import traceback
import sys
import signal
import time
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from dotenv import load_dotenv

# ============================================
# ЗАГРУЗКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ
# ============================================
load_dotenv()

# ============================================
# НАСТРОЙКА КОДИРОВКИ ДЛЯ WINDOWS
# ============================================
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except:
        pass
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    os.environ['PYTHONUTF8'] = '1'

# ============================================
# СОЗДАНИЕ ПРИЛОЖЕНИЯ
# ============================================
app = Flask(__name__)

# ============================================
# ЗАГРУЗКА НАСТРОЕК ИЗ .env
# ============================================

# Секретный ключ
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))

# Настройки базы данных
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///couriers.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Настройки загрузки
app.config['UPLOAD_FOLDER'] = os.environ.get('UPLOAD_FOLDER', 'static/uploads')
app.config['MAX_CONTENT_LENGTH'] = int(os.environ.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# Режим отладки
DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'

# Данные администратора из .env
ADMIN_LOGIN = os.environ.get('ADMIN_LOGIN', 'admin')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')

# ============================================
# НАСТРОЙКА ЛОГИРОВАНИЯ
# ============================================
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

try:
    handler = logging.FileHandler('app.log', encoding='utf-8')
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    print("[OK] Логирование настроено")
except Exception as e:
    print(f"[WARN] Не удалось создать файл логов: {e}")

# ============================================
# ОБРАБОТЧИКИ СИГНАЛОВ
# ============================================
def safe_exit_handler(signum, frame):
    """Безопасный выход при сигнале"""
    try:
        logger.info("[STOP] Получен сигнал завершения, безопасный выход...")
        db.session.close()
    except:
        pass
    sys.exit(0)

try:
    signal.signal(signal.SIGINT, safe_exit_handler)
    signal.signal(signal.SIGTERM, safe_exit_handler)
except:
    pass

def check_for_recursion():
    """Проверка на рекурсию"""
    import sys
    if sys.getrecursionlimit() < 10000:
        sys.setrecursionlimit(10000)

check_for_recursion()

# ============================================
# ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ
# ============================================
try:
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    logger.info(f"[OK] Папка загрузок создана: {app.config['UPLOAD_FOLDER']}")
except Exception as e:
    logger.error(f"[ERROR] Ошибка создания папки загрузок: {e}")

db = SQLAlchemy(app)

# ============================================
# МОДЕЛИ
# ============================================
class Courier(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False, unique=True)
    city = db.Column(db.String(100), nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    photos = db.relationship('Photo', backref='courier', lazy=True, cascade='all, delete-orphan')
    folders = db.relationship('CourierFolder', backref='courier', lazy=True, cascade='all, delete-orphan')

class Folder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    city = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    photos = db.relationship('Photo', backref='folder', lazy=True, cascade='all, delete-orphan')
    couriers = db.relationship('CourierFolder', backref='folder', lazy=True, cascade='all, delete-orphan')

class CourierFolder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    courier_id = db.Column(db.Integer, db.ForeignKey('courier.id'), nullable=False)
    folder_id = db.Column(db.Integer, db.ForeignKey('folder.id'), nullable=False)
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('courier_id', 'folder_id', name='unique_courier_folder'),)

class Photo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    filepath = db.Column(db.String(500), nullable=False)
    courier_id = db.Column(db.Integer, db.ForeignKey('courier.id'), nullable=False)
    folder_id = db.Column(db.Integer, db.ForeignKey('folder.id'), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    compressed = db.Column(db.Boolean, default=False)

# ============================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================
def allowed_file(filename):
    try:
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']
    except Exception as e:
        logger.error(f"Error in allowed_file: {e}")
        return False

def serialize_folder(folder):
    try:
        return {
            'id': folder.id,
            'name': folder.name,
            'city': folder.city,
            'created_at': folder.created_at.isoformat() if folder.created_at else None
        }
    except Exception as e:
        logger.error(f"Error serializing folder: {e}")
        return {}

def clean_filename(text):
    try:
        if not text:
            return 'no_name'
        return text.replace(' ', '_').replace('-', '_').replace('/', '_').replace('\\', '_')
    except Exception as e:
        logger.error(f"Error cleaning filename: {e}")
        return 'unknown'

def safe_delete_file(filepath):
    try:
        if filepath and os.path.exists(filepath):
            os.remove(filepath)
            logger.info(f"[OK] Файл удален: {filepath}")
            return True
        return False
    except Exception as e:
        logger.error(f"Error deleting file {filepath}: {e}")
        return False

def safe_create_directory(path):
    try:
        if not os.path.exists(path):
            os.makedirs(path, exist_ok=True)
            logger.info(f"[OK] Папка создана: {path}")
            return True
        return True
    except Exception as e:
        logger.error(f"Error creating directory {path}: {e}")
        return False

def get_safe_courier(courier_id):
    try:
        if not courier_id:
            return None
        courier = Courier.query.get(int(courier_id))
        if not courier:
            logger.warning(f"Courier with id {courier_id} not found")
        return courier
    except (ValueError, TypeError) as e:
        logger.error(f"Invalid courier_id: {courier_id}, error: {e}")
        return None

# ============================================
# СОЗДАНИЕ АДМИНИСТРАТОРА И ТАБЛИЦ (ИСПРАВЛЕНО)
# ============================================
def create_admin_if_not_exists():
    """Создает администратора из .env если его нет"""
    try:
        # Проверяем, существует ли таблица courier
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        if not inspector.has_table('courier'):
            logger.info("[WARN] Таблица courier не найдена, создаем все таблицы...")
            db.create_all()
            logger.info("[OK] Все таблицы созданы")
        
        admin = Courier.query.filter_by(is_admin=True).first()
        if not admin:
            hashed_password = generate_password_hash(ADMIN_PASSWORD)
            admin = Courier(
                first_name='Admin',
                last_name=ADMIN_LOGIN,
                city='System',
                password=hashed_password,
                is_admin=True
            )
            db.session.add(admin)
            db.session.commit()
            logger.info(f"[OK] Администратор создан: {ADMIN_LOGIN}")
            print(f"[OK] Администратор создан: {ADMIN_LOGIN}")
            return True
        return False
    except Exception as e:
        logger.error(f"[ERROR] Ошибка создания администратора: {e}")
        return False

# ============================================
# МАРШРУТЫ
# ============================================
@app.route('/')
def index():
    try:
        if 'user_id' in session:
            if session.get('is_admin'):
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('courier_dashboard'))
        return redirect(url_for('login'))
    except Exception as e:
        logger.error(f"Error in index: {e}")
        return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    try:
        admin_exists = Courier.query.filter_by(is_admin=True).first()
        
        if request.method == 'POST':
            last_name = request.form.get('last_name', '').strip()
            password = request.form.get('password', '').strip()
            
            if not last_name or not password:
                return render_template('login.html', error='Заполните все поля')
            
            if not admin_exists:
                # Создаем админа из .env данных
                hashed_password = generate_password_hash(ADMIN_PASSWORD)
                admin = Courier(
                    first_name='Admin',
                    last_name=ADMIN_LOGIN,
                    city='System',
                    password=hashed_password,
                    is_admin=True
                )
                db.session.add(admin)
                db.session.commit()
                
                session['user_id'] = admin.id
                session['last_name'] = admin.last_name
                session['is_admin'] = True
                return redirect(url_for('admin_dashboard'))
            
            user = Courier.query.filter_by(last_name=last_name).first()
            if user and check_password_hash(user.password, password):
                session['user_id'] = user.id
                session['last_name'] = user.last_name
                session['is_admin'] = user.is_admin
                
                if user.is_admin:
                    return redirect(url_for('admin_dashboard'))
                return redirect(url_for('courier_dashboard'))
            
            return render_template('login.html', error='Неверная фамилия или пароль')
        
        return render_template('login.html')
    
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Database error in login: {e}")
        return render_template('login.html', error='Ошибка базы данных')
    except Exception as e:
        logger.error(f"Error in login: {e}")
        logger.error(traceback.format_exc())
        return render_template('login.html', error='Произошла ошибка')

@app.route('/register', methods=['GET', 'POST'])
def register():
    try:
        if request.method == 'POST':
            first_name = request.form.get('first_name', '').strip()
            last_name = request.form.get('last_name', '').strip()
            city = request.form.get('city', '').strip()
            password = request.form.get('password', '').strip()
            
            if not all([first_name, last_name, city, password]):
                return render_template('register.html', error='Заполните все поля')
            
            if len(password) < 4:
                return render_template('register.html', error='Пароль должен быть минимум 4 символа')
            
            existing = Courier.query.filter_by(last_name=last_name).first()
            if existing:
                return render_template('register.html', error='Курьер с такой фамилией уже существует')
            
            hashed_password = generate_password_hash(password)
            new_courier = Courier(
                first_name=first_name,
                last_name=last_name,
                city=city,
                password=hashed_password,
                is_admin=False
            )
            db.session.add(new_courier)
            db.session.commit()
            
            flash('Регистрация успешна! Войдите в систему.', 'success')
            return redirect(url_for('login'))
        
        return render_template('register.html')
    
    except IntegrityError as e:
        db.session.rollback()
        logger.error(f"IntegrityError in register: {e}")
        return render_template('register.html', error='Пользователь с такой фамилией уже существует')
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Database error in register: {e}")
        return render_template('register.html', error='Ошибка базы данных')
    except Exception as e:
        logger.error(f"Error in register: {e}")
        logger.error(traceback.format_exc())
        return render_template('register.html', error='Произошла ошибка')

@app.route('/logout')
def logout():
    try:
        session.clear()
        return redirect(url_for('login'))
    except Exception as e:
        logger.error(f"Error in logout: {e}")
        return redirect(url_for('login'))

@app.route('/courier/dashboard')
def courier_dashboard():
    try:
        if 'user_id' not in session or session.get('is_admin'):
            return redirect(url_for('login'))
        
        courier = Courier.query.get(session['user_id'])
        if not courier:
            session.clear()
            return redirect(url_for('login'))
        
        courier_folders = Folder.query.join(CourierFolder).filter(
            CourierFolder.courier_id == courier.id
        ).all()
        
        folders_with_photos = []
        for folder in courier_folders:
            photos = Photo.query.filter_by(folder_id=folder.id, courier_id=courier.id).all()
            folders_with_photos.append({
                'folder': folder,
                'photos': photos
            })
        
        return render_template('courier_dashboard.html', 
                             courier=courier, 
                             folders=folders_with_photos)
    
    except SQLAlchemyError as e:
        logger.error(f"Database error in courier_dashboard: {e}")
        flash('Ошибка базы данных', 'danger')
        return redirect(url_for('login'))
    except Exception as e:
        logger.error(f"Error in courier_dashboard: {e}")
        logger.error(traceback.format_exc())
        flash('Произошла ошибка', 'danger')
        return redirect(url_for('login'))

@app.route('/courier/upload', methods=['POST'])
def upload_photo():
    try:
        if 'user_id' not in session or session.get('is_admin'):
            return jsonify({'error': 'Unauthorized'}), 401
        
        if 'photo' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['photo']
        folder_id = request.form.get('folder_id')
        
        if file.filename == '':
            return jsonify({'error': 'Empty filename'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'File type not allowed. Use: png, jpg, jpeg, gif, webp'}), 400
        
        if not folder_id:
            return jsonify({'error': 'Folder ID required'}), 400
        
        courier_id = session['user_id']
        
        access = CourierFolder.query.filter_by(
            courier_id=courier_id,
            folder_id=folder_id
        ).first()
        
        if not access:
            return jsonify({'error': 'Access denied'}), 403
        
        courier = Courier.query.get(courier_id)
        folder = Folder.query.get(folder_id)
        
        if not courier or not folder:
            return jsonify({'error': 'Courier or folder not found'}), 404
        
        # Очищаем названия от спецсимволов
        city_clean = clean_filename(courier.city) if courier.city else 'no_city'
        last_name_clean = clean_filename(courier.last_name)
        folder_name_clean = clean_filename(folder.name)
        
        # Создаем путь: город/фамилия/папка/
        upload_path = os.path.join(
            app.config['UPLOAD_FOLDER'],
            city_clean,
            last_name_clean,
            folder_name_clean
        )
        
        # Создаем все необходимые папки
        if not safe_create_directory(upload_path):
            return jsonify({'error': 'Failed to create directory'}), 500
        
        # Формируем имя файла: фамилия_город_время.расширение
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else 'jpg'
        filename = f"{last_name_clean}_{city_clean}_{timestamp}.{file_ext}"
        
        # Полный путь к файлу
        file_path = os.path.join(upload_path, filename)
        
        # Сохраняем файл (БЕЗ КОМПРЕССИИ)
        file.save(file_path)
        
        # Сохраняем путь в БД (относительный)
        db_path = os.path.join(
            'uploads',
            city_clean,
            last_name_clean,
            folder_name_clean,
            filename
        ).replace('\\', '/')
        
        new_photo = Photo(
            filename=filename,
            filepath=db_path,
            courier_id=courier_id,
            folder_id=folder_id,
            compressed=False
        )
        
        db.session.add(new_photo)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Фото загружено в {city_clean}/{last_name_clean}/{folder_name_clean}/',
            'photo_id': new_photo.id,
            'filename': filename,
            'path': db_path
        })
    
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Database error in upload_photo: {e}")
        return jsonify({'error': 'Database error'}), 500
    except Exception as e:
        logger.error(f"Error in upload_photo: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/admin/dashboard')
def admin_dashboard():
    try:
        if 'user_id' not in session or not session.get('is_admin'):
            return redirect(url_for('login'))
        
        city_filter = request.args.get('city', 'all')
        photo_sort = request.args.get('photo_sort', 'date_desc')
        search_query = request.args.get('search', '').strip()
        
        query = Courier.query.filter_by(is_admin=False)
        
        if search_query:
            query = query.filter(Courier.last_name.ilike(f'%{search_query}%'))
            logger.info(f"Поиск: '{search_query}' -> найдено: {query.count()}")
        
        if city_filter != 'all':
            query = query.filter_by(city=city_filter)
        
        query = query.order_by(Courier.last_name)
        
        couriers = query.all()
        folders = Folder.query.all()
        
        cities = []
        for c in Courier.query.filter_by(is_admin=False).distinct(Courier.city).all():
            if c.city not in cities:
                cities.append(c.city)
        
        courier_folders = {}
        for courier in couriers:
            assigned = [cf.folder_id for cf in CourierFolder.query.filter_by(courier_id=courier.id).all()]
            courier_folders[courier.id] = assigned
        
        found_courier = None
        if search_query:
            found_courier = Courier.query.filter(
                Courier.is_admin == False,
                Courier.last_name.ilike(f'%{search_query}%')
            ).first()
            
            if found_courier:
                all_photos = Photo.query.filter_by(courier_id=found_courier.id).all()
                logger.info(f"Найдено фото для курьера {found_courier.last_name}: {len(all_photos)}")
            else:
                all_photos = []
        else:
            all_photos = Photo.query.all()
        
        photos_by_folder = {}
        for photo in all_photos:
            if photo.folder_id not in photos_by_folder:
                photos_by_folder[photo.folder_id] = []
            photos_by_folder[photo.folder_id].append(photo)
        
        for folder_id in photos_by_folder:
            photos = photos_by_folder[folder_id]
            if photo_sort == 'date_asc':
                photos.sort(key=lambda x: x.uploaded_at)
            else:
                photos.sort(key=lambda x: x.uploaded_at, reverse=True)
        
        total_photos = 0
        for folder_id, photos in photos_by_folder.items():
            total_photos += len(photos)
        
        folders_json = json.dumps([serialize_folder(f) for f in folders])
        courier_folders_json = json.dumps(courier_folders)
        
        all_couriers = Courier.query.filter_by(is_admin=False).all()
        couriers_json = json.dumps([{
            'id': c.id,
            'first_name': c.first_name,
            'last_name': c.last_name,
            'city': c.city
        } for c in all_couriers])
        
        return render_template('admin_dashboard.html', 
                             couriers=couriers,
                             folders=folders,
                             cities=cities,
                             courier_folders=courier_folders,
                             photos_by_folder=photos_by_folder,
                             current_city=city_filter,
                             current_photo_sort=photo_sort,
                             search_query=search_query,
                             found_courier=found_courier,
                             total_photos=total_photos,
                             folders_json=folders_json,
                             courier_folders_json=courier_folders_json,
                             couriers_json=couriers_json)
    
    except SQLAlchemyError as e:
        logger.error(f"Database error in admin_dashboard: {e}")
        flash('Ошибка базы данных', 'danger')
        return redirect(url_for('login'))
    except Exception as e:
        logger.error(f"Error in admin_dashboard: {e}")
        logger.error(traceback.format_exc())
        flash('Произошла ошибка', 'danger')
        return redirect(url_for('login'))

@app.route('/admin/create_folder', methods=['POST'])
def create_folder():
    try:
        if 'user_id' not in session or not session.get('is_admin'):
            return jsonify({'error': 'Unauthorized'}), 401
        
        folder_name = request.form.get('folder_name', '').strip()
        folder_city = request.form.get('folder_city', '').strip()
        courier_ids = request.form.getlist('courier_ids[]')
        
        if not folder_name:
            return jsonify({'error': 'Введите название папки'}), 400
        
        if not courier_ids or len(courier_ids) == 0:
            return jsonify({'error': 'Выберите хотя бы одного курьера для назначения папки'}), 400
        
        existing = Folder.query.filter_by(name=folder_name).first()
        if existing:
            return jsonify({'error': 'Папка с таким названием уже существует'}), 400
        
        new_folder = Folder(
            name=folder_name,
            city=folder_city if folder_city else None
        )
        db.session.add(new_folder)
        db.session.commit()
        
        couriers_to_assign = Courier.query.filter(
            Courier.id.in_(courier_ids),
            Courier.is_admin == False
        ).all()
        
        if not couriers_to_assign:
            db.session.delete(new_folder)
            db.session.commit()
            return jsonify({'error': 'Выбранные курьеры не найдены'}), 400
        
        folder_name_clean = clean_filename(folder_name)
        
        for courier in couriers_to_assign:
            cf = CourierFolder(courier_id=courier.id, folder_id=new_folder.id)
            db.session.add(cf)
            
            city_clean = clean_filename(courier.city) if courier.city else 'no_city'
            last_name_clean = clean_filename(courier.last_name)
            
            folder_path = os.path.join(
                app.config['UPLOAD_FOLDER'],
                city_clean,
                last_name_clean,
                folder_name_clean
            )
            safe_create_directory(folder_path)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Папка "{folder_name}" создана',
            'folder_id': new_folder.id,
            'assigned_couriers': len(couriers_to_assign)
        })
    
    except IntegrityError as e:
        db.session.rollback()
        logger.error(f"IntegrityError in create_folder: {e}")
        return jsonify({'error': 'Папка с таким названием уже существует'}), 400
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Database error in create_folder: {e}")
        return jsonify({'error': 'Ошибка базы данных'}), 500
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in create_folder: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/admin/assign_folders', methods=['POST'])
def assign_folders():
    try:
        if 'user_id' not in session or not session.get('is_admin'):
            return jsonify({'error': 'Unauthorized'}), 401
        
        courier_id = request.form.get('courier_id')
        folder_ids = request.form.getlist('folder_ids[]')
        
        if not courier_id:
            return jsonify({'error': 'Courier ID required'}), 400
        
        courier = Courier.query.get(courier_id)
        if not courier:
            return jsonify({'error': 'Courier not found'}), 404
        
        CourierFolder.query.filter_by(courier_id=courier_id).delete()
        
        assigned_count = 0
        for folder_id in folder_ids:
            folder = Folder.query.get(folder_id)
            if folder and (folder.city == courier.city or folder.city is None):
                cf = CourierFolder(courier_id=courier_id, folder_id=folder_id)
                db.session.add(cf)
                assigned_count += 1
                
                city_clean = clean_filename(courier.city) if courier.city else 'no_city'
                last_name_clean = clean_filename(courier.last_name)
                folder_name_clean = clean_filename(folder.name)
                
                folder_path = os.path.join(
                    app.config['UPLOAD_FOLDER'],
                    city_clean,
                    last_name_clean,
                    folder_name_clean
                )
                safe_create_directory(folder_path)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Назначено {assigned_count} папок для курьера {courier.first_name} {courier.last_name}'
        })
    
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Database error in assign_folders: {e}")
        return jsonify({'error': 'Ошибка базы данных'}), 500
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in assign_folders: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/admin/delete_folder/<int:folder_id>', methods=['DELETE'])
def delete_folder(folder_id):
    try:
        if 'user_id' not in session or not session.get('is_admin'):
            return jsonify({'error': 'Unauthorized'}), 401
        
        folder = Folder.query.get(folder_id)
        if not folder:
            return jsonify({'error': 'Folder not found'}), 404
        
        courier_folders = CourierFolder.query.filter_by(folder_id=folder_id).all()
        
        folder_name_clean = clean_filename(folder.name)
        
        for cf in courier_folders:
            courier = Courier.query.get(cf.courier_id)
            if courier:
                city_clean = clean_filename(courier.city) if courier.city else 'no_city'
                last_name_clean = clean_filename(courier.last_name)
                folder_path = os.path.join(
                    app.config['UPLOAD_FOLDER'],
                    city_clean,
                    last_name_clean,
                    folder_name_clean
                )
                if os.path.exists(folder_path):
                    shutil.rmtree(folder_path)
                    logger.info(f"Удалена папка: {folder_path}")
        
        CourierFolder.query.filter_by(folder_id=folder_id).delete()
        Photo.query.filter_by(folder_id=folder_id).delete()
        
        db.session.delete(folder)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Папка удалена'
        })
    
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Database error in delete_folder: {e}")
        return jsonify({'error': 'Ошибка базы данных'}), 500
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in delete_folder: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/admin/delete_photo/<int:photo_id>', methods=['DELETE'])
def delete_photo(photo_id):
    try:
        if 'user_id' not in session or not session.get('is_admin'):
            return jsonify({'error': 'Unauthorized'}), 401
        
        photo = Photo.query.get(photo_id)
        if not photo:
            return jsonify({'error': 'Photo not found'}), 404
        
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], 
                                photo.filepath.replace('uploads/', ''))
        safe_delete_file(file_path)
        
        db.session.delete(photo)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Photo deleted'})
    
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Database error in delete_photo: {e}")
        return jsonify({'error': 'Ошибка базы данных'}), 500
    except Exception as e:
        logger.error(f"Error in delete_photo: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

# ============================================
# ГЛОБАЛЬНЫЕ ОБРАБОТЧИКИ ОШИБОК
# ============================================
@app.errorhandler(404)
def not_found_error(error):
    logger.error(f"404 error: {request.url}")
    return render_template('login.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    logger.error(f"500 error: {str(error)}")
    logger.error(traceback.format_exc())
    flash('Произошла ошибка на сервере', 'danger')
    return redirect(url_for('login'))

@app.errorhandler(Exception)
def handle_exception(e):
    logger.error(f"Unhandled exception: {str(e)}")
    logger.error(traceback.format_exc())
    return jsonify({'error': 'Внутренняя ошибка сервера'}), 500

# ============================================
# ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ ПРИ ЗАПУСКЕ
# ============================================
def init_db():
    """Инициализация базы данных при запуске"""
    try:
        with app.app_context():
            # Проверяем и создаем таблицы
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            if not inspector.has_table('courier'):
                logger.info("[WARN] Таблицы не найдены, создаем...")
                db.create_all()
                logger.info("[OK] Все таблицы созданы")
            else:
                logger.info("[OK] Таблицы уже существуют")
            
            # Создаем администратора
            create_admin_if_not_exists()
            
            logger.info("[OK] База данных инициализирована")
            return True
    except Exception as e:
        logger.error(f"[ERROR] Ошибка инициализации базы данных: {e}")
        logger.error(traceback.format_exc())
        return False

# ============================================
# ИНИЦИАЛИЗАЦИЯ ДЛЯ GUNICORN (ПРОД)
# выполняется при импорте main:app
with app.app_context():
    init_db()
    db.create_all()
    create_admin_if_not_exists()
    logger.info("[OK] База данных инициализирована в проде")

# ============================================
# ЛОКАЛЬНЫЙ ЗАПУСК
# ============================================
if __name__ == '__main__':
    try:
        with app.app_context():
            init_db()
            db.create_all()
            create_admin_if_not_exists()
        app.run(debug=DEBUG, host='0.0.0.0', port=5000)
    except Exception as e:
        logger.error(f"[ERROR] Ошибка запуска: {e}")
        logger.error(traceback.format_exc())
