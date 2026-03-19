import os
from dotenv import load_dotenv

# Carga variables de entorno desde archivo .env (solo para desarrollo local)
load_dotenv()

class Config:
    # Clave secreta: toma de variable de entorno o usa valor por defecto (cambiar en producción)
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'clave-secreta-por-defecto'

    # Base de datos SQLite
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///database.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Directorio base del proyecto
    basedir = os.path.abspath(os.path.dirname(__file__))

    # Carpeta para archivos subidos (debe existir y tener subcarpetas)
    UPLOADED_FILES_DEST = os.path.join(basedir, 'uploads')

    # Carpeta para backups
    BACKUP_FOLDER = os.path.join(basedir, 'backups')

    # Configuración de correo
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'smtp.gmail.com'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS') or True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER')

    # Google Calendar API Key (opcional)
    GOOGLE_CALENDAR_API_KEY = os.environ.get('GOOGLE_CALENDAR_API_KEY')