from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, PasswordField, SelectField, DateField, FloatField, TextAreaField, BooleanField, IntegerField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional, ValidationError
from models import User

# ... (mantener los formularios anteriores)

class TaskForm(FlaskForm):
    title = StringField('Título', validators=[DataRequired()])
    description = TextAreaField('Descripción', validators=[Optional()])
    due_date = DateField('Fecha de vencimiento', format='%Y-%m-%d', validators=[Optional()])
    subject_id = SelectField('Materia (opcional)', coerce=int, validators=[Optional()])
    completed = BooleanField('Completada')

class ForumTopicForm(FlaskForm):
    title = StringField('Título', validators=[DataRequired(), Length(max=200)])
    description = TextAreaField('Descripción', validators=[Optional(), Length(max=500)])

class ForumPostForm(FlaskForm):
    content = TextAreaField('Mensaje', validators=[DataRequired()])

class ForumCommentForm(FlaskForm):
    content = TextAreaField('Comentario', validators=[DataRequired()])

class NotificationSettingsForm(FlaskForm):
    email_notifications = BooleanField('Recibir notificaciones por email')
    # Otros ajustes

class DarkModeForm(FlaskForm):
    dark_mode = BooleanField('Modo oscuro')