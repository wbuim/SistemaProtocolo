import os
import json # ### Importamos a biblioteca JSON ###
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta

# --- CONFIGURAÇÃO INICIAL ---
app = Flask(__name__)
app.secret_key = 'chave_super_secreta_12345'
basedir = os.path.abspath(os.path.dirname(__file__))

# ### NOME DO BANCO DE DADOS ATUALIZADO PARA v6 ###
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'dados_v6.db')

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- MODELO DO BANCO DE DADOS (COM CAMPO SNAPSHOT) ---
class Protocolo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero_protocolo = db.Column(db.String(100), unique=True, nullable=False)
    nome_paciente = db.Column(db.String(200), nullable=False)
    medico_solicitante = db.Column(db.String(200))
    unidade_origem = db.Column(db.String(100))
    prioridade = db.Column(db.String(50), default='Eletivo')
    exame_especialidade = db.Column(db.String(200), nullable=False)
    data_pedido_medico = db.Column(db.Date, nullable=True)
    atendente = db.Column(db.String(100), nullable=False)
    data_atendimento = db.Column(db.Date, nullable=False)
    hora_atendimento = db.Column(db.Time, nullable=False)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50), default='Ativo', nullable=False)
    dados_impressao = db.Column(db.Text, nullable=True) # ### NOVO CAMPO PARA O SNAPSHOT JSON ###
    def __repr__(self):
        return f'<Protocolo {self.numero_protocolo}>'

# --- USUÁRIOS ---
USUARIOS_CADASTRADOS = {
    'admin': {'password': 'senha123', 'full_name': 'Administrador do Sistema', 'role': 'admin'},
    'neto':  {'password': 'neto', 'full_name': 'Neto Buim', 'role': 'admin'},
    'tuca':  {'password': 'tuca', 'full_name': 'Tuca da Silva', 'role': 'user'}
}

# --- ROTAS ---
@app.route('/')
def home():
    if 'username' in session:
        is_admin = session.get('role') == 'admin'
        return render_template('protocolo.html', atendente_nome_completo=session['full_name'], is_admin=is_admin)
    return redirect(url_for('login_page'))

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    error = None
    if request.method == 'POST':
        username_form = request.form['username']
        password_form = request.form['password']
        user_data = USUARIOS_CADASTRADOS.get(username_form)
        if user_data and user_data['password'] == password_form:
            session['username'] = username_form
            session['full_name'] = user_data['full_name']
            session['role'] = user_data['role']
            return redirect(url_for('home'))
        else:
            error = 'Usuário ou senha inválida.'
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))

@app.route('/lista')
def lista_protocolos():
    if 'username' not in session: return redirect(url_for('login_page'))
    is_admin = session.get('role') == 'admin'
    query = request.args.get('busca')
    filtro = request.args.get('filtro')
    consulta = Protocolo.query.filter_by(status='Ativo')
    if query:
        # (Lógica de filtros omitida para brevidade - continua igual)
        if filtro == 'prioridade' and is_admin: consulta = consulta.filter(Protocolo.prioridade.ilike(f'%{query}%'))
        elif filtro == 'protocolo': consulta = consulta.filter(Protocolo.numero_protocolo.ilike(f'%{query}%'))
        elif filtro == 'medico': consulta = consulta.filter(Protocolo.medico_solicitante.ilike(f'%{query}%'))
        elif filtro == 'origem': consulta = consulta.filter(Protocolo.unidade_origem.ilike(f'%{query}%'))
        else: consulta = consulta.filter(Protocolo.nome_paciente.ilike(f'%{query}%'))
    protocolos = consulta.order_by(Protocolo.id.desc()).all()
    return render_template('lista_protocolos.html', todos_protocolos=protocolos, atendente_nome_completo=session['full_name'], is_admin=is_admin)

@app.route('/inativos')
def lista_inativos():
    if 'username' not in session: return redirect(url_for('login_page'))
    is_admin = session.get('role') == 'admin'
    query = request.args.get('busca')
    filtro = request.args.get('filtro')
    consulta = Protocolo.query.filter_by(status='Finalizado')
    if query:
        # (Lógica de filtros omitida para brevidade - continua igual)
        if filtro == 'prioridade' and is_admin: consulta = consulta.filter(Protocolo.prioridade.ilike(f'%{query}%'))
        elif filtro == 'protocolo': consulta = consulta.filter(Protocolo.numero_protocolo.ilike(f'%{query}%'))
        elif filtro == 'medico': consulta = consulta.filter(Protocolo.medico_solicitante.ilike(f'%{query}%'))
        elif filtro == 'origem': consulta = consulta.filter(Protocolo.unidade_origem.ilike(f'%{query}%'))
        else: consulta = consulta.filter(Protocolo.nome_paciente.ilike(f'%{query}%'))
    protocolos = consulta.order_by(Protocolo.id.desc()).all()
    return render_template('lista_inativos.html', todos_protocolos=protocolos, atendente_nome_completo=session['full_name'], is_admin=is_admin)

# Rota original de impressão (usada APENAS na criação)
@app.route('/imprimir/<int:protocolo_id>')
def imprimir_protocolo(protocolo_id):
    if 'username' not in session: return redirect(url_for('login_page'))
    protocolo = Protocolo.query.get_or_404(protocolo_id)
    hora_local_emissao = protocolo.data_criacao - timedelta(hours=3)
    return render_template('impressao.html', protocolo=protocolo, hora_local_emissao=hora_local_emissao)

# ### NOVA ROTA PARA REIMPRIMIR USANDO O SNAPSHOT ###
@app.route('/reimprimir/<int:protocolo_id>')
def reimprimir_protocolo(protocolo_id):
    if 'username' not in session: return redirect(url_for('login_page'))
    
    protocolo = Protocolo.query.get_or_404(protocolo_id)
    
    if not protocolo.dados_impressao:
        flash("Não há dados de impressão salvos para este protocolo.", "danger")
        # Decide para onde voltar dependendo do status atual
        if protocolo.status == 'Ativo':
            return redirect(url_for('lista_protocolos'))
        else:
            return redirect(url_for('lista_inativos'))

    try:
        # Carrega os dados do JSON
        snapshot_data = json.loads(protocolo.dados_impressao)
        
        # Converte as strings de data/hora de volta para objetos datetime/time
        # (Necessário para a formatação .strftime() no template)
        hora_local_emissao_obj = datetime.fromisoformat(snapshot_data['hora_local_emissao_iso'])
        data_atendimento_obj = datetime.fromisoformat(snapshot_data['data_atendimento_iso']).date()
        hora_atendimento_obj = datetime.fromisoformat(snapshot_data['hora_atendimento_iso']).time()

        # Renderiza o template de impressão passando os dados do snapshot
        return render_template('impressao.html', 
                               protocolo=snapshot_data, # Passa o dicionário como 'protocolo'
                               hora_local_emissao=hora_local_emissao_obj, # Passa o objeto datetime calculado
                               # Passa os objetos data/hora recalculados para o template usar no strftime
                               data_atendimento_obj=data_atendimento_obj,
                               hora_atendimento_obj=hora_atendimento_obj
                              )
    except Exception as e:
        flash(f"Erro ao carregar dados de impressão: {e}", "danger")
        if protocolo.status == 'Ativo':
            return redirect(url_for('lista_protocolos'))
        else:
            return redirect(url_for('lista_inativos'))


@app.route('/salvar_protocolo', methods=['POST'])
def salvar_protocolo():
    if 'username' not in session: return redirect(url_for('login_page'))
    
    prioridade_valor = request.form.get('prioridade', 'Eletivo')
    data_pedido_str = request.form.get('data_pedido_medico')
    data_pedido_obj = None
    if data_pedido_str:
        try: data_pedido_obj = datetime.strptime(data_pedido_str, '%Y-%m-%d').date()
        except ValueError: pass 

    hoje = datetime.now().strftime('%Y%m%d')
    ultimo_protocolo = Protocolo.query.filter(Protocolo.numero_protocolo.like(f"{hoje}-%")).order_by(Protocolo.id.desc()).first()
    novo_num = int(ultimo_protocolo.numero_protocolo.split('-')[1]) + 1 if ultimo_protocolo else 1
    novo_protocolo_num = f"{hoje}-{novo_num:03d}"
    
    data_atendimento_obj = datetime.strptime(request.form['data_atendimento'], '%Y-%m-%d').date()
    hora_atendimento_obj = datetime.strptime(request.form['horario_atendimento'], '%H:%M').time()

    novo_protocolo = Protocolo(
        numero_protocolo=novo_protocolo_num,
        nome_paciente=request.form['nome_paciente'],
        medico_solicitante=request.form['medico_solicitante'],
        unidade_origem=request.form['unidade_origem'],
        prioridade=prioridade_valor,
        exame_especialidade=request.form['exame_especialidade'],
        data_pedido_medico=data_pedido_obj,
        atendente=session['full_name'],
        data_atendimento=data_atendimento_obj,
        hora_atendimento=hora_atendimento_obj,
        status='Ativo'
    )
    
    # ### CRIAÇÃO E SALVAMENTO DO SNAPSHOT JSON ###
    # Precisamos calcular a hora local de emissão AGORA, antes de salvar
    hora_criacao_utc = datetime.utcnow()
    hora_local_emissao_agora = hora_criacao_utc - timedelta(hours=3)
    
    snapshot = {
        'numero_protocolo': novo_protocolo_num,
        'hora_local_emissao_iso': hora_local_emissao_agora.isoformat(), # Guarda em formato ISO
        'atendente': session['full_name'],
        'nome_paciente': novo_protocolo.nome_paciente,
        'exame_especialidade': novo_protocolo.exame_especialidade,
        'especialidade_solicitada': request.form.get('especialidade_solicitada'), # Pegar do form, pois não está mais no modelo
        'medico_solicitante': novo_protocolo.medico_solicitante,
        'local_unidade': request.form.get('local_unidade'), # Pegar do form, pois não está mais no modelo
        'data_pedido_medico_iso': data_pedido_obj.isoformat() if data_pedido_obj else None, # Guarda em formato ISO
        'unidade_origem': novo_protocolo.unidade_origem,
        'data_atendimento_iso': data_atendimento_obj.isoformat(), # Guarda em formato ISO
        'hora_atendimento_iso': hora_atendimento_obj.isoformat() # Guarda em formato ISO
    }
    novo_protocolo.dados_impressao = json.dumps(snapshot) # Converte o dicionário para texto JSON
    
    db.session.add(novo_protocolo)
    db.session.commit()
    flash(f"Protocolo {novo_protocolo_num} gerado e salvo!", 'success')
    return redirect(url_for('imprimir_protocolo', protocolo_id=novo_protocolo.id)) # Continua a ir para a impressão normal na criação

@app.route('/finalizar/<int:protocolo_id>', methods=['POST'])
def finalizar_protocolo(protocolo_id):
    if 'username' not in session: return redirect(url_for('login_page'))
    protocolo = Protocolo.query.get_or_404(protocolo_id)
    protocolo.status = 'Finalizado'
    db.session.commit()
    flash(f"Protocolo {protocolo.numero_protocolo} finalizado!", 'success')
    return redirect(url_for('lista_protocolos'))

@app.route('/reativar/<int:protocolo_id>', methods=['POST'])
def reativar_protocolo(protocolo_id):
    if session.get('role') != 'admin':
        flash("Acesso não autorizado.", 'danger')
        return redirect(url_for('lista_inativos'))
    protocolo = Protocolo.query.get_or_404(protocolo_id)
    protocolo.status = 'Ativo'
    db.session.commit()
    flash(f"Protocolo {protocolo.numero_protocolo} reativado!", 'success')
    return redirect(url_for('lista_inativos'))

@app.route('/editar_prioridade/<int:protocolo_id>', methods=['POST'])
def editar_prioridade(protocolo_id):
    if session.get('role') != 'admin':
        flash("Acesso não autorizado.", 'danger')
        return redirect(request.referrer or url_for('lista_protocolos')) # Volta para onde veio
    protocolo = Protocolo.query.get_or_404(protocolo_id)
    nova_prioridade = request.form.get('nova_prioridade')
    if nova_prioridade in ['Eletivo', 'Retorno', 'Urgente']:
        protocolo.prioridade = nova_prioridade
        db.session.commit()
        flash(f"Prioridade atualizada para {nova_prioridade}.", 'success')
    else:
        flash("Prioridade inválida.", 'danger')
    return redirect(request.referrer or url_for('lista_protocolos')) # Volta para onde veio

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)