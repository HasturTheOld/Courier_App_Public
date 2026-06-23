"""Запуск сервера с защитой от падений"""

import os
import sys
import time
import logging
import subprocess
from datetime import datetime
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# ============================================
# ИСПРАВЛЕНИЕ КОДИРОВКИ ДЛЯ WINDOWS
# ============================================
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    os.environ['PYTHONUTF8'] = '1'

# ============================================
# НАСТРОЙКА ЛОГИРОВАНИЯ
# ============================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('server_startup.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Получаем данные администратора из .env
ADMIN_LOGIN = os.environ.get('ADMIN_LOGIN', 'admin')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')

def main():
    """Запуск сервера"""
    print("=" * 50)
    print("[START] ЗАПУСК СЕРВЕРА")
    print("=" * 50)
    print(f"[TIME] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"[ADMIN] {ADMIN_LOGIN}")
    print("[PASS] ********")  # Скрываем пароль
    print("=" * 50)
    
    while True:
        try:
            logger.info("[RUN] Запуск приложения...")
            result = subprocess.run(
                [sys.executable, 'app.py'],
                capture_output=True,
                text=True,
                encoding='utf-8'
            )
            
            if result.returncode != 0:
                logger.error(f"[ERROR] Сервер упал с кодом {result.returncode}")
                if result.stderr:
                    logger.error(f"[ERROR] {result.stderr[:500]}")
                logger.info("[RESTART] Перезапуск через 5 секунд...")
                time.sleep(5)
            else:
                logger.info("[OK] Сервер завершил работу нормально")
                break
                
        except KeyboardInterrupt:
            logger.info("[STOP] Остановка сервера")
            break
        except Exception as e:
            logger.error(f"[ERROR] {e}")
            logger.info("[RESTART] Перезапуск через 10 секунд...")
            time.sleep(10)
    
    logger.info("[BYE] Сервер остановлен")

if __name__ == '__main__':
    main()