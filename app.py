import os
from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# --- CONFIGURAÇÃO INICIAL ---
app = Flask(__name__)
app.secret_key = 'chave_super_secreta_12345'

# Configuração do Banco de Dados SQLite
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'protocolos.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Inicializa a extensão do banco de dados
db = SQLAlchemy(app)

# --- MODELO DO BANCO DE DADOS (A ESTRUTURA DA TABELA) ---
class Protocolo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero_protocolo = db.Column(db.String(100), unique=True, nullable=False)
    nome_paciente = db.Column(db.String(200), nullable=False)
    local_unidade = db.Column(db.String(100), nullable=False)
    medico_solicitante = db.Column(db.String(200))
    exame_solicitado = db.Column(db.String(200), nullable=False)
    especialidade_solicitada = db.Column(db.String(100))
    atendente = db.Column(db.String(100), nullable=False)
    data_atendimento = db.Column(db.Date, nullable=False)
    hora_atendimento = db.Column(db.Time, nullable=False)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Protocolo {self.numero_protocolo}>'

# --- USUÁRIOS (SIMPLIFICADO) ---
USUARIOS_CADASTRADOS = {
    'admin': 'senha123',
    'neto': 'protocolo',
    'tuca': 'tuca'
}

# --- ROTAS DA APLICAÇÃO ---
@app.route('/')
def home():
    if 'username' in session:
        return render_template('protocolo.html', atendente=session['username'])
    return redirect(url_for('login_page'))

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    error = None
    if request.method == 'POST':
        username_form = request.form['username']
        password_form = request.form['password']
        if username_form in USUARIOS_CADASTRADOS and USUARIOS_CADASTRADOS[username_form] == password_form:
            session['username'] = username_form
            return redirect(url_for('home'))
        else:
            error = 'Usuário ou senha inválida.'
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login_page'))

@app.route('/lista')
def lista_protocolos():
    if 'username' not in session:
        return redirect(url_for('login_page'))
    
    query = request.args.get('busca')
    
    if query:
        protocolos = Protocolo.query.filter(Protocolo.nome_paciente.ilike(f'%{query}%')).order_by(Protocolo.id.desc()).all()
    else:
        protocolos = Protocolo.query.order_by(Protocolo.id.desc()).all()
    
    return render_template('lista_protocolos.html', todos_protocolos=protocolos)

@app.route('/imprimir/<int:protocolo_id>')
def imprimir_protocolo(protocolo_id):
    if 'username' not in session:
        return redirect(url_for('login_page'))
    
    protocolo_para_imprimir = Protocolo.query.get_or_404(protocolo_id)
    return render_template('impressao.html', protocolo=protocolo_para_imprimir)

@app.route('/salvar_protocolo', methods=['POST'])
def salvar_protocolo():
    if 'username' not in session:
        return redirect(url_for('login_page'))
    
    # Gerar o número do protocolo
    hoje = datetime.now().strftime('%Y%m%d')
    ultimo_protocolo = Protocolo.query.filter(Protocolo.numero_protocolo.like(f"{hoje}-%")).order_by(Protocolo.id.desc()).first()
    
    novo_num = int(ultimo_protocolo.numero_protocolo.split('-')[1]) + 1 if ultimo_protocolo else 1
    novo_protocolo_num = f"{hoje}-{novo_num:03d}"

    # Criar o novo registro
    novo_protocolo = Protocolo(
        numero_protocolo=novo_protocolo_num,
        nome_paciente=request.form['nome_paciente'],
        local_unidade=request.form['local_unidade'],
        medico_solicitante=request.form['medico_solicitante'],
        exame_solicitado=request.form['exame_solicitado'],
        especialidade_solicitada=request.form['especialidade_solicitada'],
        atendente=session['username'],
        data_atendimento=datetime.strptime(request.form['data_atendimento'], '%Y-%m-%d').date(),
        hora_atendimento=datetime.strptime(request.form['horario_atendimento'], '%H:%M').time()
    )
    
    # Salvar no banco de dados
    db.session.add(novo_protocolo)
    db.session.commit()

    # Redirecionar para a impressão
    return redirect(url_for('imprimir_protocolo', protocolo_id=novo_protocolo.id))

# --- INICIALIZAÇÃO DO SERVIDOR ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)