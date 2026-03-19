from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, PasswordField, SelectField, DateField, FloatField, TextAreaField, BooleanField, DateTimeField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional

class RegistrationForm(FlaskForm):
    username = StringField('Usuario', validators=[DataRequired(), Length(min=2, max=80)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    career = SelectField('Carrera', choices=[('medicina', 'Medicina'), ('enfermeria', 'Enfermería')], validators=[DataRequired()])
    password = PasswordField('Contraseña', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirmar contraseña', validators=[DataRequired(), EqualTo('password')])

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Contraseña', validators=[DataRequired()])

class SubjectForm(FlaskForm):
    name = StringField('Nombre de la materia', validators=[DataRequired()])
    study_plan = FileField('Plan de estudios (PDF)', validators=[FileAllowed(['pdf'], 'Solo PDF')])
    course_program = FileField('Programa de cursado (PDF)', validators=[FileAllowed(['pdf'], 'Solo PDF')])
    exam_program = FileField('Programa de examen (PDF)', validators=[FileAllowed(['pdf'], 'Solo PDF')])

class MaterialForm(FlaskForm):
    description = StringField('Descripción', validators=[Optional()])
    file = FileField('Archivo', validators=[DataRequired(), FileAllowed(['pdf', 'doc', 'docx', 'jpg', 'png'], 'Solo PDF, Word, imágenes')])
    subject_id = SelectField('Materia', coerce=int, validators=[DataRequired()])

class ExamForm(FlaskForm):
    type = SelectField('Tipo', choices=[('parcial', 'Parcial'), ('final', 'Final')], validators=[DataRequired()])
    date = DateField('Fecha', format='%Y-%m-%d', validators=[DataRequired()])
    grade = FloatField('Nota (opcional)', validators=[Optional()])
    subject_id = SelectField('Materia', coerce=int, validators=[DataRequired()])

class EventForm(FlaskForm):
    title = StringField('Título', validators=[DataRequired()])
    description = TextAreaField('Descripción', validators=[Optional()])
    date = DateField('Fecha', format='%Y-%m-%d', validators=[DataRequired()])

class ReminderForm(FlaskForm):
    title = StringField('Título', validators=[DataRequired()])
    description = TextAreaField('Descripción', validators=[Optional()])
    datetime = DateTimeField('Fecha y hora', format='%Y-%m-%d %H:%M', validators=[DataRequired()])
    recurring = BooleanField('Recordatorio recurrente')

class ProfileForm(FlaskForm):
    username = StringField('Usuario', validators=[DataRequired(), Length(min=2, max=80)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    career = SelectField('Carrera', choices=[('medicina', 'Medicina'), ('enfermeria', 'Enfermería')], validators=[DataRequired()])
    profile_pic = FileField('Foto de perfil', validators=[FileAllowed(['jpg', 'png'], 'Solo imágenes')])

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

class DarkModeForm(FlaskForm):
    dark_mode = BooleanField('Modo oscuro')