from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_socketio import SocketIO
import os
from datetime import datetime
from utils.XMLParse import parse_xml_to_csv

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
socketio = SocketIO(app)

# Initialize Migrate for database changes
from flask_migrate import Migrate
migrate = Migrate(app, db)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# ---------------- DATABASE MODELS ---------------- #
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

class Job(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), unique=True, nullable=False)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)

class ScannedPart(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'), nullable=False)
    part_name = db.Column(db.String(255), nullable=False)
    scanned_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# ---------------- AUTHENTICATION ---------------- #
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            login_user(user)
            return redirect(url_for('jobs'))
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# ---------------- ROUTES ---------------- #
@app.route('/')
@login_required
def home():
    return render_template('index.html')

@app.route('/jobs')
@login_required
def jobs():
    job_files = Job.query.order_by(Job.upload_date.desc()).all()
    
    for job in job_files:
        total_parts = ScannedPart.query.filter_by(job_id=job.id).count()
        scanned_parts = ScannedPart.query.filter_by(job_id=job.id).count()
        job.progress = (scanned_parts / total_parts * 100) if total_parts > 0 else 0

    return render_template('jobs.html', job_files=job_files, is_admin=current_user.is_admin)

@app.route('/upload_folder', methods=['POST'])
@login_required
def upload_folder():
    if 'folder' not in request.files:
        return redirect(url_for('jobs'))

    files = request.files.getlist('folder')
    if not files:
        return redirect(url_for('jobs'))

    parent_folder = os.path.basename(os.path.dirname(files[0].filename))

    existing_job = Job.query.filter_by(filename=parent_folder).first()
    if existing_job:
        return "Job already exists!", 400

    upload_folder = os.path.join('uploads', parent_folder)
    csv_folder = 'csv_files'
    os.makedirs(upload_folder, exist_ok=True)

    csv_files = []
    for file in files:
        if file.filename.endswith('.des') and not file.filename.endswith('Room0.des'):
            file_path = os.path.join(upload_folder, os.path.basename(file.filename))
            file.save(file_path)
            csv_path = parse_xml_to_csv(file_path, csv_folder)
            csv_files.append(csv_path)

    if not csv_files:
        return "No valid .des files found in the folder!", 400

    new_job = Job(filename=parent_folder, upload_date=datetime.utcnow())
    db.session.add(new_job)
    db.session.commit()

    socketio.emit('update')  # Notify all clients about the update

    return redirect(url_for('jobs'))

@app.route('/delete/<filename>', methods=['POST'])
@login_required
def delete_job(filename):
    if not current_user.is_admin:
        return "Unauthorized", 403

    job = Job.query.filter_by(filename=filename).first()
    if job:
        ScannedPart.query.filter_by(job_id=job.id).delete()
        db.session.delete(job)
        db.session.commit()

    socketio.emit('update')  # Notify all clients about the deletion
    return redirect(url_for('jobs'))

@app.route('/checklist/<job_name>')
@login_required
def checklist(job_name):
    job = Job.query.filter_by(filename=job_name).first()
    if not job:
        return "Job not found", 404

    csv_filename = f"{job_name}.csv"
    csv_path = os.path.join('csv_files', csv_filename)
    if not os.path.exists(csv_path):
        return f"File {csv_filename} not found", 404

    data = []
    with open(csv_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()[1:]
        for line in lines:
            parts = line.strip().split(',')
            data.append({
                "Part Name": parts[0],
                "Width (inches)": parts[1],
                "Length (inches)": parts[2],
                "Cabinet Number": parts[3]
            })

    scanned_records = ScannedPart.query.filter_by(job_id=job.id).all()
    scanned_parts = [record.part_name for record in scanned_records]

    return render_template(
        'checklist.html',
        data=data,
        filename=job_name,
        scanned_parts=scanned_parts,
        job=job
    )

@app.route('/scan_part', methods=['POST'])
@login_required
def scan_part():
    job_id = request.form.get('job_id')
    part_name = request.form.get('part_name').strip()

    existing_scan = ScannedPart.query.filter_by(job_id=job_id, part_name=part_name).first()
    if not existing_scan:
        new_scan = ScannedPart(job_id=job_id, part_name=part_name, scanned_by=current_user.id)
        db.session.add(new_scan)
        db.session.commit()

    socketio.emit('update')  # Notify all clients about the scanned part
    return jsonify({"message": "Part scanned successfully"}), 200

@app.route('/reset_scan/<job_id>', methods=['POST'])
@login_required
def reset_scan(job_id):
    ScannedPart.query.filter_by(job_id=job_id).delete()
    db.session.commit()

    socketio.emit('update')  # Notify all clients about reset
    return jsonify({"message": "Scanned data reset"}), 200

@app.route('/trello')
@login_required
def trello():
    return render_template('trello.html')

@app.route('/schedule')
@login_required
def schedule():
    return render_template('schedule.html')

# ---------------- REAL-TIME UPDATES ---------------- #
@socketio.on('update')
def handle_update():
    socketio.emit('refresh')

# ---------------- INITIALIZE DATABASE ---------------- #
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
