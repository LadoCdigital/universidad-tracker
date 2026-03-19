import os
import csv
import io
import base64
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, render_template, redirect, url_for, flash, request, abort, send_file, jsonify, make_response
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_login import login_user, logout_user, login_required, current_user
from flask_mail import Message
from flask_uploads import UploadSet, configure_uploads, IMAGES, DOCUMENTS
from flask_apscheduler import APScheduler
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from flask import send_from_directory
import openpyxl
from openpyxl.styles import Font
import requests

from extensions import db, login_manager, mail, files, scheduler
from models import (
    User, Subject, Material, Exam, Event, Reminder, Task,
    ForumTopic, ForumPost, ForumComment, Notification
)
from forms import (
    RegistrationForm, LoginForm, SubjectForm, MaterialForm, ExamForm,
    EventForm, ReminderForm, ProfileForm, TaskForm, ForumTopicForm,
    ForumPostForm, ForumCommentForm, DarkModeForm
)
from config import Config

app = Flask(__name__)
app.config.from_object(Config)

@app.context_processor
def inject_notifications():
    if current_user.is_authenticated:
        unread = Notification.query.filter_by(user_id=current_user.id, read=False).count()
    else:
        unread = 0
    return dict(unread_notifications=unread)

# Inicializar extensiones
db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'login'
mail.init_app(app)
configure_uploads(app, files)
scheduler.init_app(app)
scheduler.start()

@login_manager.user_loader
def load_user(user_id):
    """Carga un usuario de la base de datos por su ID."""
    # Flask-Login pasa el user_id como string, lo convertimos a entero si es necesario
    return User.query.get(int(user_id))

# Crear tablas
with app.app_context():
    db.create_all()
    # Crear carpetas necesarias
    os.makedirs(app.config['UPLOADED_FILES_DEST'], exist_ok=True)
    for subfolder in ['profile_pics', 'study_plans', 'course_programs', 'exam_programs', 'materials']:
        os.makedirs(os.path.join(app.config['UPLOADED_FILES_DEST'], subfolder), exist_ok=True)
    os.makedirs(app.config['BACKUP_FOLDER'], exist_ok=True)

# Decorador para verificar si el usuario es administrador (para el foro)
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Podrías definir un campo is_admin en User
        if not current_user.is_authenticated or not current_user.email.endswith('@admin.com'):  # Ejemplo simple
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

# ==================== Funciones auxiliares ====================
def send_async_email(app, msg):
    with app.app_context():
        mail.send(msg)

def notify_user(user_id, message, link='#'):
    notif = Notification(user_id=user_id, message=message, link=link)
    db.session.add(notif)
    db.session.commit()

def check_reminders_and_exams():
    """Tarea programada para enviar recordatorios por email y crear notificaciones."""
    with app.app_context():
        now = datetime.now()
        # Recordatorios en las próximas 24 horas
        soon = now + timedelta(hours=24)
        reminders = Reminder.query.filter(Reminder.datetime.between(now, soon)).all()
        for rem in reminders:
            user = User.query.get(rem.user_id)
            if user:
                msg = Message('Recordatorio: ' + rem.title,
                              recipients=[user.email])
                msg.body = f"""
                Título: {rem.title}
                Descripción: {rem.description}
                Fecha y hora: {rem.datetime.strftime('%d/%m/%Y %H:%M')}
                """
                send_async_email(app, msg)
                notify_user(user.id, f'Recordatorio: {rem.title}', url_for('reminders'))

        # Exámenes en los próximos 7 días
        week_later = now.date() + timedelta(days=7)
        exams = Exam.query.filter(Exam.date.between(now.date(), week_later)).all()
        for ex in exams:
            user = User.query.get(ex.user_id)
            if user:
                msg = Message('Examen próximo: ' + ex.subject.name,
                              recipients=[user.email])
                msg.body = f"""
                Materia: {ex.subject.name}
                Tipo: {ex.type}
                Fecha: {ex.date.strftime('%d/%m/%Y')}
                """
                send_async_email(app, msg)
                notify_user(user.id, f'Examen próximo: {ex.subject.name} - {ex.date}', url_for('exams'))

# Programar tarea cada hora
@scheduler.task('interval', id='check_reminders', hours=1, misfire_grace_time=900)
def scheduled_check():
    check_reminders_and_exams()

def backup_database():
    """Copia la base de datos a la carpeta backups con timestamp."""
    import shutil
    src = os.path.join(app.instance_path, 'database.db')
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    dst = os.path.join(app.config['BACKUP_FOLDER'], f'database_backup_{timestamp}.db')
    shutil.copy2(src, dst)
    # Limpiar backups antiguos (ej. conservar últimos 10)
    backups = sorted(os.listdir(app.config['BACKUP_FOLDER']))
    if len(backups) > 10:
        for old in backups[:-10]:
            os.remove(os.path.join(app.config['BACKUP_FOLDER'], old))

@scheduler.task('cron', id='daily_backup', day='*', hour=3, minute=0)  # cada día a las 3am
def daily_backup():
    backup_database()

# ==================== Rutas de autenticación ====================
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        # Verificar si el email ya existe
        if User.query.filter_by(email=form.email.data).first():
            flash('Email ya registrado', 'danger')
            return render_template('register.html', form=form)
        hashed_pw = generate_password_hash(form.password.data)
        user = User(username=form.username.data, email=form.email.data,
                    career=form.career.data, password=hashed_pw)
        db.session.add(user)
        db.session.commit()
        flash('Registro exitoso. Ya puedes iniciar sesión.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and check_password_hash(user.password, form.password.data):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Email o contraseña incorrectos', 'danger')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# ==================== Dashboard y Perfil ====================
@app.route('/dashboard')
@login_required
def dashboard():
    upcoming_exams = Exam.query.filter_by(user_id=current_user.id).filter(Exam.date >= datetime.today().date()).order_by(Exam.date).limit(5).all()
    upcoming_events = Event.query.filter_by(user_id=current_user.id).filter(Event.date >= datetime.today().date()).order_by(Event.date).limit(5).all()
    upcoming_reminders = Reminder.query.filter_by(user_id=current_user.id).filter(Reminder.datetime >= datetime.now()).order_by(Reminder.datetime).limit(5).all()
    pending_tasks = Task.query.filter_by(user_id=current_user.id, completed=False).order_by(Task.due_date).limit(5).all()
    subjects_count = Subject.query.filter_by(user_id=current_user.id).count()
    materials_count = Material.query.filter_by(user_id=current_user.id).count()
    unread_notifications = Notification.query.filter_by(user_id=current_user.id, read=False).count()
    return render_template('dashboard.html',
                           upcoming_exams=upcoming_exams,
                           upcoming_events=upcoming_events,
                           upcoming_reminders=upcoming_reminders,
                           pending_tasks=pending_tasks,
                           subjects_count=subjects_count,
                           materials_count=materials_count,
                           unread_notifications=unread_notifications)

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    form = ProfileForm(obj=current_user)
    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.email = form.email.data
        current_user.career = form.career.data
        if form.profile_pic.data:
            filename = files.save(form.profile_pic.data, folder='profile_pics', name=f"user_{current_user.id}.")
            current_user.profile_pic = filename
        db.session.commit()
        flash('Perfil actualizado', 'success')
        return redirect(url_for('profile'))
    return render_template('profile.html', form=form)

@app.route('/notifications')
@login_required
def notifications():
    notifs = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).all()
    return render_template('notifications.html', notifications=notifs)

@app.route('/notifications/read/<int:id>')
@login_required
def mark_notification_read(id):
    notif = Notification.query.get_or_404(id)
    if notif.user_id != current_user.id:
        abort(403)
    notif.read = True
    db.session.commit()
    return redirect(notif.link or url_for('notifications'))

@app.route('/dark-mode/toggle', methods=['POST'])
@login_required
def toggle_dark_mode():
    current_user.dark_mode = not current_user.dark_mode
    db.session.commit()
    return redirect(request.referrer or url_for('dashboard'))

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    """Sirve archivos subidos desde la carpeta UPLOADED_FILES_DEST."""
    return send_from_directory(app.config['UPLOADED_FILES_DEST'], filename)

# ==================== Gestión de materias ====================
@app.route('/subjects')
@login_required
def subjects():
    subjects = Subject.query.filter_by(user_id=current_user.id).all()
    return render_template('subjects.html', subjects=subjects)

@app.route('/subject/new', methods=['GET', 'POST'])
@login_required
def new_subject():
    form = SubjectForm()
    if form.validate_on_submit():
        subject = Subject(name=form.name.data, career=current_user.career, user_id=current_user.id)
        # Guardar archivos si se subieron
        if form.study_plan.data:
            filename = files.save(form.study_plan.data, folder='study_plans', name=f"study_{current_user.id}_{form.name.data}.")
            subject.study_plan = filename
        if form.course_program.data:
            filename = files.save(form.course_program.data, folder='course_programs', name=f"course_{current_user.id}_{form.name.data}.")
            subject.course_program = filename
        if form.exam_program.data:
            filename = files.save(form.exam_program.data, folder='exam_programs', name=f"exam_{current_user.id}_{form.name.data}.")
            subject.exam_program = filename
        db.session.add(subject)
        db.session.commit()
        flash('Materia creada', 'success')
        return redirect(url_for('subjects'))
    return render_template('subject_form.html', form=form, title='Nueva materia')

@app.route('/subject/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_subject(id):
    subject = Subject.query.get_or_404(id)
    if subject.user_id != current_user.id:
        abort(403)
    form = SubjectForm(obj=subject)
    if form.validate_on_submit():
        subject.name = form.name.data
        if form.study_plan.data:
            filename = files.save(form.study_plan.data, folder='study_plans', name=f"study_{current_user.id}_{form.name.data}.")
            subject.study_plan = filename
        if form.course_program.data:
            filename = files.save(form.course_program.data, folder='course_programs', name=f"course_{current_user.id}_{form.name.data}.")
            subject.course_program = filename
        if form.exam_program.data:
            filename = files.save(form.exam_program.data, folder='exam_programs', name=f"exam_{current_user.id}_{form.name.data}.")
            subject.exam_program = filename
        db.session.commit()
        flash('Materia actualizada', 'success')
        return redirect(url_for('subjects'))
    return render_template('subject_form.html', form=form, title='Editar materia')

@app.route('/subject/<int:id>/delete')
@login_required
def delete_subject(id):
    subject = Subject.query.get_or_404(id)
    if subject.user_id != current_user.id:
        abort(403)
    db.session.delete(subject)
    db.session.commit()
    flash('Materia eliminada', 'success')
    return redirect(url_for('subjects'))

@app.route('/subject/<int:id>/toggle_public')
@login_required
def toggle_subject_public(id):
    subject = Subject.query.get_or_404(id)
    if subject.user_id != current_user.id:
        abort(403)
    subject.is_public = not subject.is_public
    db.session.commit()
    flash('Visibilidad actualizada', 'success')
    return redirect(url_for('subjects'))

# ==================== Materiales ====================
@app.route('/materials')
@login_required
def materials():
    # Mostrar materiales propios y los públicos de otros usuarios (si se desea)
    own_materials = Material.query.filter_by(user_id=current_user.id).order_by(Material.uploaded_at.desc()).all()
    # Materiales públicos de otros (a través de materias públicas)
    public_materials = Material.query.join(Subject).filter(Subject.is_public == True, Subject.user_id != current_user.id).order_by(Material.uploaded_at.desc()).all()
    return render_template('materials.html', own_materials=own_materials, public_materials=public_materials)

@app.route('/material/upload', methods=['GET', 'POST'])
@login_required
def upload_material():
    form = MaterialForm()
    # Solo materias del usuario
    form.subject_id.choices = [(s.id, s.name) for s in Subject.query.filter_by(user_id=current_user.id).all()]
    if form.validate_on_submit():
        filename = files.save(form.file.data, folder='materials', name=f"mat_{current_user.id}_{datetime.now().timestamp()}.")
        material = Material(filename=filename, description=form.description.data,
                            subject_id=form.subject_id.data, user_id=current_user.id)
        db.session.add(material)
        db.session.commit()
        flash('Material subido', 'success')
        return redirect(url_for('materials'))
    return render_template('upload_material.html', form=form)

@app.route('/material/<int:id>/delete')
@login_required
def delete_material(id):
    material = Material.query.get_or_404(id)
    if material.user_id != current_user.id:
        abort(403)
    # Eliminar archivo
    try:
        os.remove(os.path.join(app.config['UPLOADED_FILES_DEST'], material.filename))
    except:
        pass
    db.session.delete(material)
    db.session.commit()
    flash('Material eliminado', 'success')
    return redirect(url_for('materials'))

# ==================== Exámenes ====================
@app.route('/exams')
@login_required
def exams():
    exams = Exam.query.filter_by(user_id=current_user.id).order_by(Exam.date).all()
    return render_template('exams.html', exams=exams)

@app.route('/exam/new', methods=['GET', 'POST'])
@login_required
def new_exam():
    form = ExamForm()
    form.subject_id.choices = [(s.id, s.name) for s in Subject.query.filter_by(user_id=current_user.id).all()]
    if form.validate_on_submit():
        exam = Exam(type=form.type.data, date=form.date.data, grade=form.grade.data,
                    subject_id=form.subject_id.data, user_id=current_user.id)
        db.session.add(exam)
        db.session.commit()
        flash('Examen registrado', 'success')
        return redirect(url_for('exams'))
    return render_template('exam_form.html', form=form, title='Nuevo examen')

@app.route('/exam/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_exam(id):
    exam = Exam.query.get_or_404(id)
    if exam.user_id != current_user.id:
        abort(403)
    form = ExamForm(obj=exam)
    form.subject_id.choices = [(s.id, s.name) for s in Subject.query.filter_by(user_id=current_user.id).all()]
    if form.validate_on_submit():
        exam.type = form.type.data
        exam.date = form.date.data
        exam.grade = form.grade.data
        exam.subject_id = form.subject_id.data
        db.session.commit()
        flash('Examen actualizado', 'success')
        return redirect(url_for('exams'))
    return render_template('exam_form.html', form=form, title='Editar examen')

@app.route('/exam/<int:id>/delete')
@login_required
def delete_exam(id):
    exam = Exam.query.get_or_404(id)
    if exam.user_id != current_user.id:
        abort(403)
    db.session.delete(exam)
    db.session.commit()
    flash('Examen eliminado', 'success')
    return redirect(url_for('exams'))

# ==================== Eventos y Calendario ====================
@app.route('/calendar')
@login_required
def calendar():
    events = Event.query.filter_by(user_id=current_user.id).order_by(Event.date).all()
    # También podríamos incluir exámenes como eventos
    exam_events = Exam.query.filter_by(user_id=current_user.id).all()
    return render_template('calendar.html', events=events, exams=exam_events)

@app.route('/event/new', methods=['GET', 'POST'])
@login_required
def new_event():
    form = EventForm()
    if form.validate_on_submit():
        event = Event(title=form.title.data, description=form.description.data,
                      date=form.date.data, user_id=current_user.id)
        db.session.add(event)
        db.session.commit()
        flash('Evento añadido', 'success')
        return redirect(url_for('calendar'))
    return render_template('event_form.html', form=form, title='Nuevo evento')

@app.route('/event/<int:id>/delete')
@login_required
def delete_event(id):
    event = Event.query.get_or_404(id)
    if event.user_id != current_user.id:
        abort(403)
    db.session.delete(event)
    db.session.commit()
    flash('Evento eliminado', 'success')
    return redirect(url_for('calendar'))

# ==================== Recordatorios ====================
@app.route('/reminders')
@login_required
def reminders():
    reminders = Reminder.query.filter_by(user_id=current_user.id).order_by(Reminder.datetime).all()
    return render_template('reminders.html', reminders=reminders)

@app.route('/reminder/new', methods=['GET', 'POST'])
@login_required
def new_reminder():
    form = ReminderForm()
    if form.validate_on_submit():
        reminder = Reminder(title=form.title.data, description=form.description.data,
                            datetime=form.datetime.data, recurring=form.recurring.data,
                            user_id=current_user.id)
        db.session.add(reminder)
        db.session.commit()
        flash('Recordatorio creado', 'success')
        return redirect(url_for('reminders'))
    return render_template('reminder_form.html', form=form, title='Nuevo recordatorio')

@app.route('/reminder/<int:id>/delete')
@login_required
def delete_reminder(id):
    reminder = Reminder.query.get_or_404(id)
    if reminder.user_id != current_user.id:
        abort(403)
    db.session.delete(reminder)
    db.session.commit()
    flash('Recordatorio eliminado', 'success')
    return redirect(url_for('reminders'))

# ==================== Tareas (checklist) ====================
@app.route('/tasks')
@login_required
def tasks():
    tasks = Task.query.filter_by(user_id=current_user.id).order_by(Task.completed, Task.due_date).all()
    return render_template('tasks.html', tasks=tasks)

@app.route('/task/new', methods=['GET', 'POST'])
@login_required
def new_task():
    form = TaskForm()
    form.subject_id.choices = [(0, '-- Ninguna --')] + [(s.id, s.name) for s in Subject.query.filter_by(user_id=current_user.id).all()]
    if form.validate_on_submit():
        task = Task(title=form.title.data, description=form.description.data,
                    due_date=form.due_date.data, completed=form.completed.data,
                    subject_id=form.subject_id.data if form.subject_id.data != 0 else None,
                    user_id=current_user.id)
        db.session.add(task)
        db.session.commit()
        flash('Tarea creada', 'success')
        return redirect(url_for('tasks'))
    return render_template('task_form.html', form=form, title='Nueva tarea')

@app.route('/task/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_task(id):
    task = Task.query.get_or_404(id)
    if task.user_id != current_user.id:
        abort(403)
    form = TaskForm(obj=task)
    form.subject_id.choices = [(0, '-- Ninguna --')] + [(s.id, s.name) for s in Subject.query.filter_by(user_id=current_user.id).all()]
    if form.validate_on_submit():
        task.title = form.title.data
        task.description = form.description.data
        task.due_date = form.due_date.data
        task.completed = form.completed.data
        task.subject_id = form.subject_id.data if form.subject_id.data != 0 else None
        db.session.commit()
        flash('Tarea actualizada', 'success')
        return redirect(url_for('tasks'))
    return render_template('task_form.html', form=form, title='Editar tarea')

@app.route('/task/<int:id>/toggle')
@login_required
def toggle_task(id):
    task = Task.query.get_or_404(id)
    if task.user_id != current_user.id:
        abort(403)
    task.completed = not task.completed
    db.session.commit()
    return redirect(url_for('tasks'))

@app.route('/task/<int:id>/delete')
@login_required
def delete_task(id):
    task = Task.query.get_or_404(id)
    if task.user_id != current_user.id:
        abort(403)
    db.session.delete(task)
    db.session.commit()
    flash('Tarea eliminada', 'success')
    return redirect(url_for('tasks'))

# ==================== Foro ====================
@app.route('/forum')
def forum():
    topics = ForumTopic.query.order_by(ForumTopic.created_at.desc()).all()
    return render_template('forum.html', topics=topics)

@app.route('/forum/topic/new', methods=['GET', 'POST'])
@login_required
def new_topic():
    form = ForumTopicForm()
    if form.validate_on_submit():
        topic = ForumTopic(title=form.title.data, description=form.description.data, user_id=current_user.id)
        db.session.add(topic)
        db.session.commit()
        flash('Tema creado', 'success')
        return redirect(url_for('forum'))
    return render_template('forum_topic_form.html', form=form)

@app.route('/forum/topic/<int:id>')
def view_topic(id):
    topic = ForumTopic.query.get_or_404(id)
    posts = ForumPost.query.filter_by(topic_id=id).order_by(ForumPost.created_at).all()
    return render_template('forum_topic.html', topic=topic, posts=posts)

@app.route('/forum/topic/<int:id>/post/new', methods=['GET', 'POST'])
@login_required
def new_post(id):
    topic = ForumTopic.query.get_or_404(id)
    form = ForumPostForm()
    if form.validate_on_submit():
        post = ForumPost(content=form.content.data, topic_id=id, user_id=current_user.id)
        db.session.add(post)
        db.session.commit()
        # Notificar a los usuarios que siguen el tema (opcional)
        flash('Respuesta publicada', 'success')
        return redirect(url_for('view_topic', id=id))
    return render_template('forum_post_form.html', form=form, topic=topic)

@app.route('/forum/post/<int:id>/comment', methods=['POST'])
@login_required
def add_comment(id):
    post = ForumPost.query.get_or_404(id)
    content = request.form.get('content')
    if content:
        comment = ForumComment(content=content, post_id=id, user_id=current_user.id)
        db.session.add(comment)
        db.session.commit()
    return redirect(url_for('view_topic', id=post.topic_id))

# ==================== Estadísticas con gráficas ====================
@app.route('/statistics')
@login_required
def statistics():
    subjects = Subject.query.filter_by(user_id=current_user.id).all()
    data = []
    total_grades = 0
    count_grades = 0
    for subject in subjects:
        exams = Exam.query.filter_by(subject_id=subject.id).filter(Exam.grade.isnot(None)).all()
        if exams:
            avg_subject = sum(e.grade for e in exams) / len(exams)
            total_grades += sum(e.grade for e in exams)
            count_grades += len(exams)
        else:
            avg_subject = None
        data.append({
            'subject': subject.name,
            'exams': exams,
            'average': avg_subject
        })
    overall_average = total_grades / count_grades if count_grades > 0 else None

    # Preparar datos para gráfica de evolución (últimos 10 exámenes)
    all_exams = Exam.query.filter_by(user_id=current_user.id).filter(Exam.grade.isnot(None)).order_by(Exam.date).all()
    chart_labels = [ex.date.strftime('%d/%m/%Y') + ' - ' + ex.subject.name for ex in all_exams[-10:]]
    chart_data = [ex.grade for ex in all_exams[-10:]]

    return render_template('statistics.html',
                           data=data,
                           overall_average=overall_average,
                           chart_labels=chart_labels,
                           chart_data=chart_data)

# ==================== Exportar datos ====================
@app.route('/export/exams/pdf')
@login_required
def export_exams_pdf():
    exams = Exam.query.filter_by(user_id=current_user.id).order_by(Exam.date).all()
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    c.setFont("Helvetica", 12)
    c.drawString(50, height - 50, "Mis Exámenes")
    y = height - 80
    for ex in exams:
        c.drawString(50, y, f"{ex.subject.name} - {ex.type} - {ex.date} - Nota: {ex.grade if ex.grade else 'Pendiente'}")
        y -= 20
        if y < 50:
            c.showPage()
            y = height - 50
    c.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name='examenes.pdf', mimetype='application/pdf')

@app.route('/export/exams/excel')
@login_required
def export_exams_excel():
    exams = Exam.query.filter_by(user_id=current_user.id).order_by(Exam.date).all()
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Exámenes"
    headers = ['Materia', 'Tipo', 'Fecha', 'Nota']
    ws.append(headers)
    for ex in exams:
        ws.append([ex.subject.name, ex.type, ex.date.strftime('%Y-%m-%d'), ex.grade if ex.grade else ''])
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name='examenes.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

# ==================== Integración Google Calendar (básica) ====================
@app.route('/google-calendar/events')
@login_required
def google_calendar_events():
    # Ejemplo: obtener eventos públicos de un calendario (requiere API key)
    # Esto es solo un esqueleto, necesitarías autenticación OAuth para calendarios privados
    api_key = app.config.get('GOOGLE_CALENDAR_API_KEY')
    calendar_id = 'es.ar#holiday@group.v.calendar.google.com'  # Ejemplo: festivos Argentina
    if not api_key:
        flash('API key no configurada', 'warning')
        return redirect(url_for('calendar'))
    url = f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events?key={api_key}"
    response = requests.get(url)
    if response.status_code == 200:
        events = response.json().get('items', [])
        return render_template('google_calendar.html', events=events)
    else:
        flash('Error al obtener eventos de Google Calendar', 'danger')
        return redirect(url_for('calendar'))

# ==================== Backup manual ====================
@app.route('/backup/manual')
@login_required
def manual_backup():
    if not current_user.email.endswith('@admin.com'):  # Solo admin
        abort(403)
    backup_database()
    flash('Copia de seguridad realizada', 'success')
    return redirect(url_for('dashboard'))

# ==================== Manejo de errores ====================
@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500

# ==================== Inicio ====================
if __name__ == '__main__':
    app.run(debug=True)