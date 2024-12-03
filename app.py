from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_migrate import Migrate
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'db7710cdf3c463e9f32095b6bccfde53')

# Configuración de la base de datos PostgreSQL
database_url = os.environ.get('DATABASE_URL', 'postgresql://postgres.nlugycdfwsdnqtxbhngw:qewooqkQ,dsp23@aws-0-us-west-1.pooler.supabase.com:6543/postgres')
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

def auto_upgrade_db():
    with app.app_context():
        db.create_all()
        try:
            from flask_migrate import upgrade
            upgrade()
        except Exception as e:
            print(f"Error en migración: {e}")

@app.context_processor
def inject_datetime():
    return dict(datetime=datetime)

# Modelos
class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

class Cliente(db.Model):
    __tablename__ = 'clientes'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    telefono = db.Column(db.String(20))
    plataforma = db.Column(db.String(50))
    nota = db.Column(db.Text)
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)
    licencias = db.relationship('Licencia', backref='cliente', lazy=True, cascade='all, delete-orphan')

class Licencia(db.Model):
    __tablename__ = 'licencias'
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    tipo_software = db.Column(db.String(100), nullable=False)
    clave_licencia = db.Column(db.String(100), nullable=False)
    fecha_inicio = db.Column(db.DateTime, nullable=False)
    fecha_expiracion = db.Column(db.DateTime, nullable=False)
    estado = db.Column(db.String(20), default='Activa')
    notas = db.Column(db.Text)

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.filter_by(id=int(user_id)).first()

# Rutas
@app.route('/')
@login_required
def dashboard():
    total_clientes = Cliente.query.count()
    total_licencias = Licencia.query.count()
    fecha_limite = datetime.utcnow() + timedelta(days=5)
    licencias_por_expirar = Licencia.query.filter(
        Licencia.fecha_expiracion.between(datetime.utcnow(), fecha_limite)
    ).count()
    licencias_expiradas = Licencia.query.filter(
        Licencia.fecha_expiracion < datetime.utcnow()
    ).count()
    return render_template('dashboard.html', 
                         total_clientes=total_clientes,
                         total_licencias=total_licencias,
                         licencias_por_expirar=licencias_por_expirar,
                         licencias_expiradas=licencias_expiradas)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = Usuario.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page if next_page else url_for('dashboard'))
        flash('Usuario o contraseña incorrectos', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/clientes')
@login_required
def clientes():
    clientes = Cliente.query.all()
    return render_template('clientes.html', clientes=clientes)

@app.route('/cliente/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo_cliente():
    if request.method == 'POST':
        cliente = Cliente(
            nombre=request.form['nombre'],
            email=request.form['email'],
            telefono=request.form['telefono'],
            plataforma=request.form['plataforma'],
            nota=request.form['nota']
        )
        try:
            db.session.add(cliente)
            db.session.commit()
            flash('Cliente creado exitosamente', 'success')
            return redirect(url_for('clientes'))
        except Exception as e:
            db.session.rollback()
            flash('Error al crear el cliente', 'danger')
    return render_template('nuevo_cliente.html')

@app.route('/cliente/<int:id>/licencias')
@login_required
def licencias_cliente(id):
    cliente = Cliente.query.get_or_404(id)
    return render_template('licencias_cliente.html', cliente=cliente)

@app.route('/cliente/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_cliente(id):
    cliente = Cliente.query.get_or_404(id)
    if request.method == 'POST':
        cliente.nombre = request.form['nombre']
        cliente.email = request.form['email']
        cliente.telefono = request.form['telefono']
        cliente.plataforma = request.form['plataforma']
        cliente.nota = request.form['nota']
        try:
            db.session.commit()
            flash('Cliente actualizado exitosamente', 'success')
            return redirect(url_for('clientes'))
        except Exception as e:
            db.session.rollback()
            flash('Error al actualizar el cliente', 'danger')
    return render_template('editar_cliente.html', cliente=cliente)

@app.route('/cliente/eliminar/<int:id>')
@login_required
def eliminar_cliente(id):
    cliente = Cliente.query.get_or_404(id)
    try:
        db.session.delete(cliente)
        db.session.commit()
        flash('Cliente eliminado exitosamente', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error al eliminar el cliente', 'danger')
    return redirect(url_for('clientes'))

@app.route('/licencias')
@login_required
def licencias():
    licencias = Licencia.query.all()
    return render_template('licencias.html', licencias=licencias)

@app.route('/licencia/nueva', methods=['GET', 'POST'])
@login_required
def nueva_licencia():
    if request.method == 'POST':
        licencia = Licencia(
            cliente_id=request.form['cliente_id'],
            tipo_software=request.form['tipo_software'],
            clave_licencia=request.form['clave_licencia'],
            fecha_inicio=datetime.strptime(request.form['fecha_inicio'], '%Y-%m-%d'),
            fecha_expiracion=datetime.strptime(request.form['fecha_expiracion'], '%Y-%m-%d'),
            notas=request.form['notas']
        )
        try:
            db.session.add(licencia)
            db.session.commit()
            flash('Licencia creada exitosamente', 'success')
            return redirect(url_for('licencias'))
        except Exception as e:
            db.session.rollback()
            flash('Error al crear la licencia', 'danger')
    clientes = Cliente.query.all()
    cliente_id = request.args.get('cliente_id')
    return render_template('nueva_licencia.html', clientes=clientes, cliente_id=cliente_id)

@app.route('/licencia/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_licencia(id):
    licencia = Licencia.query.get_or_404(id)
    if request.method == 'POST':
        licencia.cliente_id = request.form['cliente_id']
        licencia.tipo_software = request.form['tipo_software']
        licencia.clave_licencia = request.form['clave_licencia']
        licencia.fecha_inicio = datetime.strptime(request.form['fecha_inicio'], '%Y-%m-%d')
        licencia.fecha_expiracion = datetime.strptime(request.form['fecha_expiracion'], '%Y-%m-%d')
        licencia.estado = request.form['estado']
        licencia.notas = request.form['notas']
        try:
            db.session.commit()
            flash('Licencia actualizada exitosamente', 'success')
            return redirect(url_for('licencias'))
        except Exception as e:
            db.session.rollback()
            flash('Error al actualizar la licencia', 'danger')
    clientes = Cliente.query.all()
    return render_template('editar_licencia.html', licencia=licencia, clientes=clientes)

@app.route('/licencia/eliminar/<int:id>')
@login_required
def eliminar_licencia(id):
    licencia = Licencia.query.get_or_404(id)
    try:
        db.session.delete(licencia)
        db.session.commit()
        flash('Licencia eliminada exitosamente', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error al eliminar la licencia', 'danger')
    return redirect(url_for('licencias'))

@app.route('/crear-admin')
def crear_admin():
    try:
        # Crear todas las tablas si no existen
        db.create_all()
        
        # Verificar si existe el usuario admin
        admin = Usuario.query.filter_by(username='tecnoplus').first()
        if not admin:
            # Crear usuario admin
            admin = Usuario(
                username='tecnoplus',
                password_hash=generate_password_hash('admintecno')
            )
            db.session.add(admin)
            db.session.commit()
            flash('Usuario administrador creado exitosamente', 'success')
        else:
            flash('El usuario administrador ya existe', 'info')
        return redirect(url_for('login'))
    except Exception as e:
        db.session.rollback()
        flash(f'Error al crear el administrador: {str(e)}', 'danger')
        return redirect(url_for('login'))

@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500

if __name__ == '__main__':
    with app.app_context():
        try:
            auto_upgrade_db()
            admin = Usuario.query.filter_by(username='tecnoplus').first()
            if not admin:
                admin = Usuario(
                    username='tecnoplus',
                    password_hash=generate_password_hash('admintecno')
                )
                db.session.add(admin)
                db.session.commit()
                print("Usuario admin creado exitosamente")
        except Exception as e:
            print(f"Error al inicializar la base de datos: {e}")
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
