from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail
from flask_uploads import UploadSet, configure_uploads, IMAGES, DOCUMENTS
from flask_apscheduler import APScheduler

db = SQLAlchemy()
login_manager = LoginManager()
mail = Mail()
files = UploadSet('files', extensions=('pdf', 'doc', 'docx', 'jpg', 'png'))
scheduler = APScheduler()