# Bibliotecas padrão
import os
import re
import logging
import hashlib
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, date, timedelta

# Bibliotecas de terceiros
import streamlit as st
import psycopg2
import pandas as pd
import matplotlib.pyplot as plt
from dotenv import load_dotenv, find_dotenv
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from streamlit_extras.add_vertical_space import add_vertical_space
from streamlit_extras.let_it_rain import rain
from cryptography.fernet import Fernet
import random
import string
import plotly.express as px

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Carregamento de variáveis de ambiente
dotenv_path = find_dotenv()
load_dotenv(dotenv_path, override=True)

# Variáveis de ambiente
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_PORT = os.getenv("DB_PORT")

# Debug de configuração
logging.debug(f"Arquivo .env encontrado em: {dotenv_path}")
logging.debug(f"EMAIL_SENDER configurado: {EMAIL_SENDER}")
logging.debug(f"DB_HOST configurado: {DB_HOST}")

# Constantes para validação
TEMP_MIN = 35.0
TEMP_MAX = 38.0
TEMP_MIN_ALERTA = 35.0
TEMP_MAX_ALERTA = 38.0
TEMP_MIN_LIMITE = 25.0
TEMP_MAX_LIMITE = 45.0

FREQ_MIN = 50
FREQ_MAX = 120
FREQ_MIN_ALERTA = 50
FREQ_MAX_ALERTA = 120
FREQ_MIN_LIMITE = 20
FREQ_MAX_LIMITE = 220

SAT_MIN = 90
SAT_MAX = 100
SAT_MIN_ALERTA = 90

PRESSAO_PATTERN = r'^\d{2,3}/\d{2,3}$'

# Chave de criptografia para dados sensíveis (em produção, armazene em local seguro)
FERNET_KEY = os.getenv("FERNET_KEY") or Fernet.generate_key().decode()
fernet = Fernet(FERNET_KEY.encode())

# Funções de banco de dados
def conectar_db():
    """
    Estabelece conexão com o banco de dados PostgreSQL usando as variáveis de ambiente.

    Returns:
        connection (psycopg2.extensions.connection): Conexão ativa com o banco de dados.
    Raises:
        Exception: Se houver falha na conexão, detalha o erro ocorrido.
    """
    try:
        return psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            port=DB_PORT,
        )
    except Exception as e:
        logging.exception("Erro ao conectar ao banco de dados")
        raise Exception(f"Falha na conexão com o banco de dados: {str(e)}")

def hash_senha(senha):
    """
    Gera o hash SHA-256 de uma senha em texto puro.

    Args:
        senha (str): Senha em texto puro.
    Returns:
        str: Hash hexadecimal da senha.
    """
    return hashlib.sha256(senha.encode()).hexdigest()

def registrar_auditoria(usuario_id, acao, detalhes):
    """
    Registra uma ação do usuário para fins de auditoria.
    """
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO auditoria (usuario_id, acao, detalhes, data_hora) VALUES (%s, %s, %s, NOW())",
        (usuario_id, acao, detalhes)
    )
    conn.commit()
    conn.close()

def enviar_mensagem(id_remetente, id_destinatario, texto):
    """
    Envia uma mensagem interna entre usuários e notifica o destinatário por e-mail.

    Args:
        id_remetente (int): ID do usuário remetente.
        id_destinatario (int): ID do usuário destinatário.
        texto (str): Conteúdo da mensagem.
    Returns:
        bool: True se enviada com sucesso, False caso contrário.
    """
    conn = None
    try:
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO mensagens (id_remetente, id_destinatario, texto) VALUES (%s, %s, %s)",
            (id_remetente, id_destinatario, texto)
        )
        # Buscar e-mail do destinatário
        cursor.execute("SELECT email, nome FROM usuarios WHERE id = %s", (id_destinatario,))
        row = cursor.fetchone()
        email_dest, nome_dest = row if row else (None, None)
        # Buscar nome do remetente
        cursor.execute("SELECT nome FROM usuarios WHERE id = %s", (id_remetente,))
        row_rem = cursor.fetchone()
        nome_rem = row_rem[0] if row_rem else "Usuário"
        conn.commit()
        # Enviar notificação por e-mail
        if email_dest:
            try:
                msg = MIMEText(f"Olá {nome_dest},\n\nVocê recebeu uma nova mensagem de {nome_rem} no sistema de Telemonitoramento CEUB.\n\nMensagem: {texto}\n\nAcesse o sistema para responder.")
                msg["Subject"] = "Nova mensagem no Telemonitoramento CEUB"
                msg["From"] = EMAIL_SENDER
                msg["To"] = email_dest
                with smtplib.SMTP('smtp.gmail.com', 587) as server:
                    server.starttls()
                    server.login(EMAIL_SENDER, EMAIL_PASSWORD)
                    server.send_message(msg)
            except Exception as e:
                st.warning(f"Não foi possível enviar notificação por e-mail: {e}")
        registrar_auditoria(id_remetente, "Envio de mensagem", texto.strip())
        return True
    except Exception as e:
        if conn:
            conn.rollback()
        st.error(f"Erro ao enviar mensagem: {str(e)}")
        return False
    finally:
        if conn:
            conn.close()

def buscar_parametros_alerta():
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT temp_min, temp_max, freq_min, freq_max, sat_min, pressao_min, pressao_max FROM parametros_alerta ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    if row:
        temp_min, temp_max, freq_min, freq_max, sat_min, pressao_min, pressao_max = row
    else:
        temp_min, temp_max = 35.0, 38.0
        freq_min, freq_max = 50, 120
        sat_min = 90
        pressao_min, pressao_max = "90/60", "140/90"
    return {
        "temp_min": temp_min, "temp_max": temp_max,
        "freq_min": freq_min, "freq_max": freq_max,
        "sat_min": sat_min,
        "pressao_min": pressao_min, "pressao_max": pressao_max
    }

# Funções de validação
def validar_pressao(pressao):
    """
    Valida o formato e os valores da pressão arterial informada.

    Args:
        pressao (str): Pressão no formato 'sistólica/diastólica' (ex: '120/80').
    Returns:
        tuple: (bool, str) indicando se é válida e mensagem de erro (ou vazio).
    """
    if not re.match(PRESSAO_PATTERN, pressao):
        logging.debug(f"Formato de pressão inválido: {pressao}")
        return False, "Formato inválido. Use: 120/80"
    try:
        sist, diast = map(int, pressao.split('/'))
        if not (90 <= sist <= 180 and 60 <= diast <= 110):
            logging.debug(f"Valores de pressão fora do intervalo: {pressao}")
            return False, "Valores fora do intervalo normal"
        return True, ""
    except Exception as e:
        logging.exception(f"Erro ao processar pressão: {pressao}")
        return False, "Erro ao processar valores"

def checar_alertas(sinais):
    """
    Verifica se há alertas nos sinais vitais registrados, comparando com limites definidos.

    Args:
        sinais (dict): Dicionário com chaves 'temperatura', 'pressao', 'frequencia', 'saturacao'.
    Returns:
        list: Lista de strings descrevendo os alertas encontrados (vazia se nenhum).
    """
    params = buscar_parametros_alerta()
    alertas = []
    temperatura = sinais['temperatura']
    pressao = sinais['pressao']
    frequencia = sinais['frequencia']
    saturacao = sinais['saturacao']

    if temperatura < params['temp_min'] or temperatura > params['temp_max']:
        alertas.append(f"Temperatura fora do padrão: {temperatura}°C (Limite: {params['temp_min']}–{params['temp_max']}°C)")
    valido, msg = validar_pressao(pressao)
    if not valido:
        alertas.append(f"Pressão arterial: {msg}")
    else:
        sist, diast = map(int, pressao.split('/'))
        sist_min, diast_min = map(int, params['pressao_min'].split('/'))
        sist_max, diast_max = map(int, params['pressao_max'].split('/'))
        if sist > sist_max or diast > diast_max:
            alertas.append(f"Pressão Alta: {pressao} mmHg (Limite: {params['pressao_max']} mmHg)")
        if sist < sist_min or diast < diast_min:
            alertas.append(f"Pressão Baixa: {pressao} mmHg (Limite: {params['pressao_min']} mmHg)")
    if frequencia < params['freq_min'] or frequencia > params['freq_max']:
        alertas.append(f"Frequência cardíaca fora do padrão: {frequencia} bpm (Limite: {params['freq_min']}–{params['freq_max']} bpm)")
    if saturacao < params['sat_min']:
        alertas.append(f"Saturação baixa: {saturacao}% (Mínimo: {params['sat_min']}%)")
    return alertas

def enviar_alerta_email(paciente_nome, alertas, paciente_email, profissional_email):
    """
    Envia e-mails de alerta para o paciente e o profissional de saúde, detalhando os sinais alterados.

    Args:
        paciente_nome (str): Nome do paciente.
        alertas (list): Lista de strings com alertas detectados.
        paciente_email (str): E-mail do paciente.
        profissional_email (str): E-mail do profissional responsável.
    Raises:
        Exception: Se houver erro no envio de e-mail.
    """
    assunto_prof = f"[ALERTA] Sinais vitais alterados - {paciente_nome}"
    corpo_prof = (
        f"O paciente {paciente_nome} apresentou alterações nos seguintes sinais:\n\n"
        + '\n'.join(f"⚠️ {alerta}" for alerta in alertas)
        + "\n\nPor favor, avalie o caso e, se necessário, entre em contato."
    )
    
    assunto_pac = f"[ATENÇÃO] Alteração nos seus sinais vitais"
    corpo_pac = (
        f"Olá {paciente_nome},\n\nDetectamos alterações em seus sinais vitais:\n\n"
        + '\n'.join(f"⚠️ {alerta}" for alerta in alertas)
        + "\n\nRecomendamos procurar orientação profissional caso não esteja se sentindo bem."
    )

    msg_prof = MIMEText(corpo_prof)
    msg_prof['Subject'] = assunto_prof
    msg_prof['From'] = EMAIL_SENDER
    msg_prof['To'] = profissional_email

    msg_pac = MIMEText(corpo_pac)
    msg_pac['Subject'] = assunto_pac
    msg_pac['From'] = EMAIL_SENDER
    msg_pac['To'] = paciente_email

    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.set_debuglevel(1)
            server.starttls()
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg_prof)
            server.send_message(msg_pac)
        logging.info(f"Alertas enviados para {paciente_email} e {profissional_email}")
        st.success("✉️ Alertas enviados por email!")
    except Exception as e:
        logging.error("Detalhes SMTP:", exc_info=True)
        st.error(f"Falha no envio de e-mail: {e}")
        raise Exception(f"Erro ao enviar alertas por email: {str(e)}")

# Funções de envio de email
def enviar_notificacao_profissional(paciente_nome, sinais_vitais, profissional_email, is_critico=True):
    """
    Envia notificação por e-mail ao profissional de saúde sobre os sinais vitais do paciente.

    Args:
        paciente_nome (str): Nome do paciente.
        sinais_vitais (dict): Dicionário com os valores dos sinais vitais.
        profissional_email (str): E-mail do profissional de saúde.
        is_critico (bool, opcional): Se True, envia como notificação crítica. Default: True.
    Raises:
        Exception: Se houver erro no envio do e-mail.
    """
    try:
        assunto = f"[CRÍTICO] Sinais Vitais - {paciente_nome}" if is_critico else f"[ALERTA] Sinais Vitais - {paciente_nome}"
        corpo = f"""
        {'⚠️ REGISTRO CRÍTICO DE SINAIS VITAIS ⚠️' if is_critico else '🔔 ALERTA DE SINAIS VITAIS'}
        
        Paciente: {paciente_nome}
        Data/Hora: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
        
        Sinais Vitais Registrados:
        - Temperatura: {sinais_vitais['temperatura']}°C
        - Pressão Arterial: {sinais_vitais['pressao']} mmHg
        - Frequência Cardíaca: {sinais_vitais['frequencia']} bpm
        - Saturação de O2: {sinais_vitais['saturacao']}%
        
        {'⚠️ AVALIE ESTES DADOS COM URGÊNCIA!' if is_critico else 'Por favor, avalie estes dados.'}
        """
        
        msg = MIMEText(corpo)
        msg['Subject'] = assunto
        msg['From'] = EMAIL_SENDER
        msg['To'] = profissional_email
        
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.set_debuglevel(1)  # Ativa debug
            server.starttls()
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)
        
        logging.info(f"Email enviado com sucesso para {profissional_email}")
    except Exception as e:
        logging.exception("Erro ao enviar email de notificação")
        raise Exception(f"Falha no envio do email: {str(e)}")

# Funções de consulta
def select_usuarios_pacientes():
    """
    Retorna todos os usuários cadastrados com perfil de paciente.

    Returns:
        list: Lista de tuplas (id, nome) dos pacientes.
    Raises:
        Exception: Se houver erro na consulta ao banco de dados.
    """
    conn = None
    try:
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, nome FROM usuarios WHERE perfil = 'Paciente'")
        usuarios = cursor.fetchall()
        logging.debug(f"Encontrados {len(usuarios)} usuários pacientes")
        return usuarios
    except Exception as e:
        logging.exception("Erro ao buscar usuários pacientes")
        raise Exception(f"Falha ao buscar pacientes: {str(e)}")
    finally:
        if conn:
            conn.close()

def select_profissionais():
    """
    Retorna todos os usuários cadastrados com perfil de profissional de saúde.

    Returns:
        list: Lista de tuplas (id, nome) dos profissionais.
    Raises:
        Exception: Se houver erro na consulta ao banco de dados.
    """
    conn = None
    try:
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, nome FROM usuarios WHERE perfil = 'Profissional de Saúde'")
        profs = cursor.fetchall()
        logging.debug(f"Encontrados {len(profs)} profissionais de saúde")
        return profs
    except Exception as e:
        logging.exception("Erro ao buscar profissionais")
        raise Exception(f"Falha ao buscar profissionais: {str(e)}")
    finally:
        if conn:
            conn.close()

def buscar_pacientes_do_profissional(profissional_id):
    """
    Retorna todos os pacientes vinculados a um profissional específico.

    Args:
        profissional_id (int): ID do profissional de saúde.
    Returns:
        list: Lista de tuplas (id, nome) dos pacientes vinculados.
    Raises:
        Exception: Se houver erro na consulta ao banco de dados.
    """
    conn = None
    try:
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.id, u.nome
            FROM pacientes p
            JOIN usuarios u ON p.usuario_id = u.id
            WHERE p.profissional_responsavel_id = %s
        """, (profissional_id,))
        pacientes = cursor.fetchall()
        logging.debug(f"Encontrados {len(pacientes)} pacientes para o profissional {profissional_id}")
        return pacientes
    except Exception as e:
        logging.exception(f"Erro ao buscar pacientes do profissional {profissional_id}")
        raise Exception(str(e))
    finally:
        if conn:
            conn.close()

def buscar_todos_pacientes():
    """
    Retorna todos os pacientes cadastrados no sistema.

    Returns:
        list: Lista de tuplas (id, nome) dos pacientes.
    Raises:
        Exception: Se houver erro na consulta ao banco de dados.
    """
    conn = None
    try:
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.id, u.nome
            FROM pacientes p
            JOIN usuarios u ON p.usuario_id = u.id
        """)
        pacientes = cursor.fetchall()
        logging.debug(f"Total de pacientes encontrados: {len(pacientes)}")
        return pacientes
    except Exception as e:
        logging.exception("Erro ao buscar todos os pacientes")
        raise Exception(str(e))
    finally:
        if conn:
            conn.close()

# Funções de cadastro
def cadastrar_usuario_novo(nome, email, senha, tipo, status=True):
    """
    Cadastra um novo usuário na tabela usuarios.

    Args:
        nome (str): Nome do usuário.
        email (str): E-mail do usuário.
        senha (str): Senha em texto puro.
        tipo (str): Tipo/perfil do usuário (Admin, Profissional, Paciente).
        status (bool, opcional): Status ativo/inativo. Default: True.
    Returns:
        int or None: ID do usuário cadastrado ou None em caso de erro.
    """
    conn = None
    try:
        conn = conectar_db()
        cursor = conn.cursor()
        senha_hash = hash_senha(senha)
        cursor.execute(
            "INSERT INTO usuarios (nome, email, senha, tipo, status) VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (nome, email, senha_hash, tipo, status)
        )
        usuario_id = cursor.fetchone()[0]
        registrar_auditoria(usuario_id, f"Cadastro de usuário {tipo}", f"Nome: {nome}, Email: {email}")
        return usuario_id
    except psycopg2.errors.UniqueViolation:
        if conn:
            conn.rollback()
        st.error("Este e-mail já está cadastrado!")
        return None
    except Exception as e:
        if conn:
            conn.rollback()
        st.error(f"Erro ao cadastrar usuário: {str(e)}")
        return None
    finally:
        if conn:
            conn.close()

def cadastrar_profissional(usuario_id, especialidade, registro_profissional):
    """
    Cadastra um novo profissional na tabela profissionais.

    Args:
        usuario_id (int): ID do usuário vinculado.
        especialidade (str): Especialidade do profissional.
        registro_profissional (str): Registro profissional (CRM, COREN, etc).
    Returns:
        bool: True se cadastrado com sucesso, False caso contrário.
    """
    conn = None
    try:
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO profissionais (id_usuario, especialidade, registro_profissional) VALUES (%s, %s, %s)",
            (usuario_id, especialidade, registro_profissional)
        )
        conn.commit()
        return True
    except Exception as e:
        if conn:
            conn.rollback()
        st.error(f"Erro ao cadastrar profissional: {str(e)}")
        return False
    finally:
        if conn:
            conn.close()

def cadastrar_paciente(usuario_id, id_profissional_responsavel, dados_medicos=None):
    """
    Cadastra um novo paciente na tabela pacientes.

    Args:
        usuario_id (int): ID do usuário vinculado.
        id_profissional_responsavel (int): ID do profissional responsável.
        dados_medicos (str, opcional): Dados médicos criptografados.
    Returns:
        bool: True se cadastrado com sucesso, False caso contrário.
    """
    conn = None
    try:
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO pacientes (id_usuario, id_profissional_responsavel, dados_medicos) VALUES (%s, %s, %s)",
            (usuario_id, id_profissional_responsavel, dados_medicos)
        )
        conn.commit()
        return True
    except Exception as e:
        if conn:
            conn.rollback()
        st.error(f"Erro ao cadastrar paciente: {str(e)}")
        return False
    finally:
        if conn:
            conn.close()

def cadastrar_sinais_vitais(paciente_id, temperatura, pressao, frequencia, saturacao):
    """
    Registra os sinais vitais de um paciente e notifica o profissional responsável.

    Args:
        paciente_id (int): ID do paciente.
        temperatura (float): Temperatura corporal.
        pressao (str): Pressão arterial.
        frequencia (int): Frequência cardíaca.
        saturacao (int): Saturação de oxigênio.
    Raises:
        Exception: Se houver erro ao registrar os sinais vitais.
    """
    logging.info(f"Registrando sinais vitais para paciente_id={paciente_id}")
    conn = None
    try:
        conn = conectar_db()
        cursor = conn.cursor()
        # Primeiro registra no banco
        cursor.execute(
            "INSERT INTO sinais_vitais (paciente_id, temperatura, pressao, frequencia_cardiaca, saturacao) VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (paciente_id, temperatura, pressao, frequencia, saturacao)
        )
        registro_id = cursor.fetchone()[0]
        conn.commit()
        logging.info(f"Sinais vitais registrados com sucesso (id={registro_id})")
        # Depois busca dados para notificação
        cursor.execute("""
            SELECT u.nome, up.email as prof_email
            FROM pacientes p
            JOIN usuarios u ON p.usuario_id = u.id
            JOIN usuarios up ON p.profissional_responsavel_id = up.id
            WHERE p.id = %s
        """, (paciente_id,))
        dados = cursor.fetchone()
        if not dados:
            logging.error(f"Dados não encontrados para paciente_id={paciente_id}")
            st.warning("⚠️ Sinais vitais registrados, mas não foi possível identificar o profissional para notificação.")
            return
        paciente_nome, profissional_email = dados
        # Tenta enviar email, mas não reverte registro em caso de falha
        sinais = {
            'temperatura': temperatura,
            'pressao': pressao,
            'frequencia': frequencia,
            'saturacao': saturacao
        }
        try:
            enviar_notificacao_profissional(paciente_nome, sinais, profissional_email, is_critico=True)
            st.success("✅ Sinais vitais registrados e profissional notificado!")
        except Exception as e:
            logging.exception("Falha ao enviar notificação")
            st.warning("⚠️ Sinais vitais registrados, mas não foi possível notificar o profissional.")
    except Exception as e:
        if conn:
            conn.rollback()
        logging.exception("Erro ao registrar sinais vitais")
        raise Exception(f"Falha ao registrar sinais vitais: {str(e)}")
    finally:
        if conn:
            conn.close()

# Funções de interface Streamlit
def criar_campos_sinais_vitais():
    """
    Cria os campos de entrada para os sinais vitais na interface, com validação em tempo real.

    Returns:
        tuple: (temperatura, pressao, frequencia, saturacao) informados pelo usuário.
    """
    col1, col2 = st.columns(2)

    with col1:
        temperatura = st.number_input(
            "Temperatura (°C)", 
            min_value=TEMP_MIN_LIMITE,
            max_value=TEMP_MAX_LIMITE,
            value=36.5,
            step=0.1,
            help=f"Valores normais: {TEMP_MIN}–{TEMP_MAX}°C"
        )
        if temperatura < TEMP_MIN_ALERTA or temperatura > TEMP_MAX_ALERTA:
            logging.warning(f"Temperatura fora do normal: {temperatura}°C")
            st.warning(f"⚠️ Temperatura fora do normal ({TEMP_MIN}–{TEMP_MAX}°C)")

        frequencia = st.number_input(
            "Frequência Cardíaca (bpm)",
            min_value=FREQ_MIN_LIMITE,
            max_value=FREQ_MAX_LIMITE,
            value=80,
            help=f"Normal: {FREQ_MIN}–{FREQ_MAX} bpm"
        )
        if frequencia < FREQ_MIN_ALERTA or frequencia > FREQ_MAX_ALERTA:
            logging.warning(f"Frequência cardíaca fora do normal: {frequencia} bpm")
            st.warning(f"⚠️ Frequência cardíaca fora do normal ({FREQ_MIN}–{FREQ_MAX} bpm)")

    with col2:
        pressao = st.text_input(
            "Pressão Arterial (Ex: 120/80)",
            help="Digite no formato: sistólica/diastólica"
        )
        if pressao:
            valido, msg = validar_pressao(pressao)
            if not valido:
                logging.warning(f"Pressão arterial inválida: {pressao} - {msg}")
        
        saturacao = st.number_input(
            "Saturação (%)",
            min_value=50,
            max_value=SAT_MAX,
            value=97,
            help=f"Normal: {SAT_MIN}–{SAT_MAX}%"
        )
        if saturacao < SAT_MIN_ALERTA:
            logging.warning(f"Saturação baixa: {saturacao}%")
            st.warning(f"⚠️ Saturação baixa (< {SAT_MIN}%)")
    
    return temperatura, pressao, frequencia, saturacao

def plotar_evolucao_sinais(sinais_df):
    """
    Exibe gráfico de evolução dos sinais vitais do paciente.

    Args:
        sinais_df (pd.DataFrame): DataFrame com colunas Data, Temperatura, Frequência, Saturação.
    """
    if sinais_df.empty:
        logging.debug("Sem dados para plotar gráfico de evolução")
        st.info("Ainda não há registros para mostrar o gráfico de evolução.")
        return

    st.subheader("📈 Evolução dos sinais vitais")
    fig, ax = plt.subplots(figsize=(12, 6))
    
    try:
        sinais_df['Data'] = sinais_df['Data'].astype(str)
        
        ax.plot(sinais_df['Data'], sinais_df['Temperatura'], marker='o', label='Temperatura (°C)', color='red')
        ax.plot(sinais_df['Data'], sinais_df['Frequência'], marker='o', label='Frequência Cardíaca (bpm)', color='blue')
        ax.plot(sinais_df['Data'], sinais_df['Saturação'], marker='o', label='Saturação (%)', color='green')
        
        ax.set_xlabel("Data")
        ax.set_ylabel("Valores")
        ax.legend()
        ax.grid(True)
        plt.xticks(rotation=30)
        plt.tight_layout()
        st.pyplot(fig)
        logging.debug("Gráfico de evolução plotado com sucesso")
    except Exception as e:
        logging.exception("Erro ao plotar gráfico de evolução")
        st.error("Não foi possível gerar o gráfico de evolução")

def mostrar_ultimos_registros(df):
    """
    Exibe os últimos registros de sinais vitais em formato de tabela na interface.

    Args:
        df (pd.DataFrame): DataFrame com os registros de sinais vitais.
    """
    if df.empty:
        logging.debug("Sem dados para mostrar últimos registros")
        st.info("Ainda não há registros para mostrar.")
        return
        
    st.subheader("🗂️ Últimos registros")
    try:
        st.dataframe(df, use_container_width=True)
        logging.debug(f"Exibidos {len(df)} registros na tabela")
    except Exception as e:
        logging.exception("Erro ao exibir tabela de registros")
        st.error("Não foi possível exibir os registros")

def verificar_registro_hoje(paciente_id):
    """
    Verifica se o paciente já registrou sinais vitais no dia atual.

    Args:
        paciente_id (int): ID do paciente.
    Returns:
        bool: True se já registrou hoje, False caso contrário.
    """
    conn = None
    try:
        conn = conectar_db()
        cursor = conn.cursor()
        hoje = date.today()
        cursor.execute("""
            SELECT COUNT(*) 
            FROM sinais_vitais 
            WHERE paciente_id = %s 
            AND DATE(data_registro) = %s
        """, (paciente_id, hoje))
        registrado = cursor.fetchone()[0]
        logging.debug(f"Verificação de registro do dia para paciente {paciente_id}: {registrado > 0}")
        return registrado > 0
    except Exception as e:
        logging.exception("Erro ao verificar registro do dia")
        return False
    finally:
        if conn:
            conn.close()

def mostrar_lembrete_registro(paciente_id):
    """
    Exibe um lembrete na interface caso o paciente não tenha registrado sinais vitais hoje.

    Args:
        paciente_id (int): ID do paciente.
    """
    if verificar_registro_hoje(paciente_id):
        logging.info(f"Paciente {paciente_id} já registrou sinais vitais hoje")
        st.success("✅ Você já registrou seus sinais vitais hoje. Obrigado pelo comprometimento!")
    else:
        logging.warning(f"Paciente {paciente_id} ainda não registrou sinais vitais hoje")
        st.warning("⏰ Lembrete: você ainda não registrou seus sinais vitais hoje!")

def obter_registros_sinais(paciente_id, dias=7):
    """
    Obtém os registros de sinais vitais do paciente no período especificado.

    Args:
        paciente_id (int): ID do paciente.
        dias (int, opcional): Número de dias a considerar. Default: 7.
    Returns:
        pd.DataFrame: DataFrame com os registros encontrados.
    """
    conn = None
    try:
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT data_registro, temperatura, pressao, frequencia_cardiaca, saturacao
            FROM sinais_vitais
            WHERE paciente_id = %s 
            AND data_registro >= NOW() - INTERVAL '%s days'
            ORDER BY data_registro DESC
        """, (paciente_id, dias))
        dados = cursor.fetchall()
        
        if not dados:
            logging.debug(f"Nenhum registro encontrado para paciente {paciente_id} nos últimos {dias} dias")
            return pd.DataFrame()
        
        logging.debug(f"Encontrados {len(dados)} registros para paciente {paciente_id}")
        return pd.DataFrame(dados, columns=["Data", "Temperatura", "Pressão", "Frequência", "Saturação"])
    except Exception as e:
        logging.exception("Erro ao buscar registros de sinais vitais")
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()

def formatar_mensagem_alerta(alertas):
    """
    Formata a mensagem de alerta para exibição na interface.

    Args:
        alertas (list): Lista de strings com alertas detectados.
    Returns:
        str: Mensagem formatada para exibição.
    """
    return "⚠️ Alertas detectados:\n" + "\n".join(f"- {alerta}" for alerta in alertas)

# Funções de autenticação
def autenticar(email, senha):
    """
    Autentica um usuário no sistema usando e-mail e senha.

    Args:
        email (str): E-mail do usuário.
        senha (str): Senha em texto puro.
    Returns:
        tuple or None: Dados do usuário autenticado ou None se falhar.
    """
    conn = None
    try:
        conn = conectar_db()
        cursor = conn.cursor()
        senha_hash = hash_senha(senha)
        cursor.execute("SELECT * FROM usuarios WHERE email=%s AND senha=%s", (email, senha_hash))
        usuario = cursor.fetchone()
        if usuario:
            if not usuario[5]:  # status (ativo/inativo)
                st.error("Usuário inativo. Contate o administrador.")
                return None
            logging.info(f"Usuário {email} autenticado com sucesso")
            registrar_auditoria(usuario[0], "Login", f"Email: {email}")
        else:
            logging.warning(f"Tentativa de login falhou para {email}")
        return usuario
    except Exception as e:
        logging.exception("Erro na autenticação")
        return None
    finally:
        if conn:
            conn.close()

# Função para criptografar dados médicos
def criptografar_dados(dados):
    """
    Criptografa um dicionário de dados sensíveis usando Fernet.

    Args:
        dados (dict): Dados a serem criptografados.
    Returns:
        str: Dados criptografados em base64.
    """
    if not dados:
        return None
    import json
    return fernet.encrypt(json.dumps(dados).encode()).decode()

def descriptografar_dados(dados_cript):
    """
    Descriptografa dados criptografados com Fernet.

    Args:
        dados_cript (str): Dados criptografados em base64.
    Returns:
        dict: Dados originais descriptografados.
    """
    if not dados_cript:
        return None
    import json
    return json.loads(fernet.decrypt(dados_cript.encode()).decode())

# Início do app Streamlit
if "usuario" not in st.session_state:
    st.session_state.usuario = None

# Recuperação de senha por e-mail
if not st.session_state.get("2fa_validado") and not st.session_state.get("2fa_codigo_enviado") and not st.session_state.usuario:
    st.title("🔐 Login - Telemonitoramento CEUB")
    email = st.text_input("E-mail")
    senha = st.text_input("Senha", type="password")
    col1, col2 = st.columns([2,1])
    with col1:
        login_btn = st.button("Entrar")
    with col2:
        esqueci_btn = st.button("Esqueci minha senha")
    if login_btn:
        usuario = autenticar(email, senha)
        if usuario:
            # Gerar código 2FA
            codigo_2fa = ''.join(random.choices(string.digits, k=6))
            st.session_state["2fa_codigo"] = codigo_2fa
            st.session_state["2fa_email"] = email
            st.session_state["2fa_usuario"] = usuario
            st.session_state["2fa_codigo_enviado"] = True
            # Enviar código por e-mail
            try:
                msg = MIMEText(f"Seu código de verificação 2FA: {codigo_2fa}")
                msg["Subject"] = "Código de verificação 2FA - Telemonitoramento CEUB"
                msg["From"] = EMAIL_SENDER
                msg["To"] = email
                with smtplib.SMTP('smtp.gmail.com', 587) as server:
                    server.starttls()
                    server.login(EMAIL_SENDER, EMAIL_PASSWORD)
                    server.send_message(msg)
                st.info("Código de verificação enviado para seu e-mail.")
            except Exception as e:
                st.error(f"Erro ao enviar código 2FA: {e}")
        else:
            st.error("Credenciais inválidas ou usuário inativo!")
        st.stop()
    if esqueci_btn:
        if not email:
            st.warning("Digite seu e-mail para recuperar a senha.")
        else:
            # Verifica se o e-mail existe
            conn = conectar_db()
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM usuarios WHERE email = %s", (email,))
            user_row = cursor.fetchone()
            conn.close()
            if not user_row:
                st.error("E-mail não encontrado.")
            else:
                codigo_rec = ''.join(random.choices(string.digits, k=6))
                st.session_state["rec_email"] = email
                st.session_state["rec_codigo"] = codigo_rec
                st.session_state["rec_id_usuario"] = user_row[0]
                try:
                    msg = MIMEText(f"Seu código de recuperação de senha: {codigo_rec}")
                    msg["Subject"] = "Recuperação de senha - Telemonitoramento CEUB"
                    msg["From"] = EMAIL_SENDER
                    msg["To"] = email
                    with smtplib.SMTP('smtp.gmail.com', 587) as server:
                        server.starttls()
                        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
                        server.send_message(msg)
                    st.info("Código de recuperação enviado para seu e-mail.")
                except Exception as e:
                    st.error(f"Erro ao enviar código de recuperação: {e}")
                st.session_state["rec_codigo_enviado"] = True
        st.stop()
if st.session_state.get("rec_codigo_enviado") and not st.session_state.get("rec_senha_trocada"):
    st.title("🔑 Recuperação de Senha")
    codigo = st.text_input("Digite o código enviado para seu e-mail")
    nova_senha = st.text_input("Nova senha", type="password", help="Mínimo 8 caracteres, letras, números e símbolos.")
    nova_senha2 = st.text_input("Confirme a nova senha", type="password")
    if st.button("Redefinir senha"):
        if codigo != st.session_state.get("rec_codigo"):
            st.error("Código incorreto.")
        elif not nova_senha or not nova_senha2:
            st.error("Preencha ambos os campos.")
        elif nova_senha != nova_senha2:
            st.error("As senhas não coincidem.")
        elif len(nova_senha) < 8 or not any(c.isdigit() for c in nova_senha) or not any(c.isalpha() for c in nova_senha) or not any(not c.isalnum() for c in nova_senha):
            st.error("A senha deve ter pelo menos 8 caracteres, letras, números e símbolos.")
        else:
            conn = conectar_db()
            cursor = conn.cursor()
            cursor.execute("UPDATE usuarios SET senha = %s, primeiro_acesso = FALSE WHERE id = %s", (hash_senha(nova_senha), st.session_state["rec_id_usuario"]))
            conn.commit()
            conn.close()
            registrar_auditoria(st.session_state["rec_id_usuario"], "Recuperação de senha", f"E-mail: {st.session_state.get('rec_email')}")
            st.success("Senha redefinida com sucesso! Faça login novamente.")
            for k in ["rec_email", "rec_codigo", "rec_id_usuario", "rec_codigo_enviado", "rec_senha_trocada"]:
                if k in st.session_state:
                    del st.session_state[k]
            st.experimental_rerun()
    st.stop()
if st.session_state.get("2fa_codigo_enviado") and not st.session_state.get("2fa_validado"):
    st.title("🔐 Verificação em Duas Etapas (2FA)")
    codigo = st.text_input("Digite o código enviado para seu e-mail")
    if st.button("Verificar"):
        if codigo == st.session_state.get("2fa_codigo"):
            st.session_state.usuario = st.session_state.get("2fa_usuario")
            st.session_state["2fa_validado"] = True
            registrar_auditoria(st.session_state.usuario[0], "Login 2FA", f"Email: {st.session_state.get('2fa_email')}")
            st.success(f"Bem-vindo(a), {st.session_state.usuario[1]}!")
            st.rerun()
        else:
            st.error("Código incorreto. Tente novamente.")
    st.stop()

# Após login 2FA, exigir troca de senha se primeiro_acesso for True
if st.session_state.get("2fa_validado") and st.session_state.usuario:
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT primeiro_acesso FROM usuarios WHERE id = %s", (st.session_state.usuario[0],))
    pa_row = cursor.fetchone()
    conn.close()
    if pa_row and pa_row[0]:
        st.warning("Por segurança, altere sua senha antes de acessar o sistema pela primeira vez.")
        with st.form("form_troca_senha_primeiro_acesso"):
            nova_senha = st.text_input("Nova senha", type="password", help="Mínimo 8 caracteres, letras, números e símbolos.")
            nova_senha2 = st.text_input("Confirme a nova senha", type="password")
            if st.form_submit_button("Alterar senha"):
                if not nova_senha or not nova_senha2:
                    st.error("Preencha ambos os campos.")
                elif nova_senha != nova_senha2:
                    st.error("As senhas não coincidem.")
                elif len(nova_senha) < 8 or not any(c.isdigit() for c in nova_senha) or not any(c.isalpha() for c in nova_senha) or not any(not c.isalnum() for c in nova_senha):
                    st.error("A senha deve ter pelo menos 8 caracteres, letras, números e símbolos.")
                else:
                    conn = conectar_db()
                    cursor = conn.cursor()
                    cursor.execute("UPDATE usuarios SET senha = %s, primeiro_acesso = FALSE WHERE id = %s", (hash_senha(nova_senha), st.session_state.usuario[0]))
                    conn.commit()
                    conn.close()
                    registrar_auditoria(st.session_state.usuario[0], "Troca de senha primeiro acesso", "Usuário alterou a senha no primeiro login.")
                    st.success("Senha alterada com sucesso! Faça login novamente.")
                    for k in ["usuario", "2fa_validado", "2fa_codigo_enviado", "2fa_codigo", "2fa_email", "2fa_usuario"]:
                        if k in st.session_state:
                            del st.session_state[k]
                    st.experimental_rerun()
        st.stop()

# Protege o acesso a usuario_tipo
if st.session_state.usuario is not None:
    usuario_tipo = st.session_state.usuario[4]
else:
    usuario_tipo = None
    st.info("Por favor, faça login para acessar o sistema.")
    st.stop()

# Layout CEUB moderno e interativo
st.set_page_config(page_title="Telemonitoramento CEUB", page_icon="🩺", layout="wide")

# Cabeçalho customizado
st.markdown(
    f'''
    <div style="background: linear-gradient(90deg, #3a0057 60%, #e6007e 100%); padding: 1rem 2rem; display: flex; align-items: center; justify-content: space-between;">
        <div style="display: flex; align-items: center;">
            <img src="https://upload.wikimedia.org/wikipedia/commons/2/2e/Logo_CEUB.png" height="48" style="margin-right: 1rem;">
            <span style="color: white; font-size: 2rem; font-weight: bold; letter-spacing: 2px;">CEUB Telemonitoramento 🩺</span>
        </div>
        <div>
            <span style="color: #fff; font-size: 1.1rem; margin-right: 2rem;">Olá, {st.session_state.usuario[1] if 'usuario' in st.session_state and st.session_state.usuario else ''} 👋</span>
        </div>
    </div>
    ''',
    unsafe_allow_html=True
)

# Sidebar customizada com ícones
st.sidebar.markdown(
    '''
    <style>
    .stSidebar {
        background: linear-gradient(180deg, #6a1b9a 0%, #8e24aa 100%) !important;
    }
    .sidebar-title {
        color: #e6007e;
        font-size: 1.3rem;
        font-weight: bold;
    }
    .sidebar-link {
        margin: 0.5rem 0;
        font-size: 1.1rem;
    }
    </style>
    ''',
    unsafe_allow_html=True
)
st.sidebar.markdown('<div class="sidebar-title">Menu Principal</div>', unsafe_allow_html=True)

if 'opcoes_menu' not in st.session_state:
    st.session_state['opcoes_menu'] = ["Dashboard", "Usuários", "Pacientes", "Sinais Vitais", "Relatórios", "Mensagens", "Auditoria", "Parâmetros de Alerta", "Ajuda"]

opcoes_menu = st.session_state['opcoes_menu']
opcao = st.sidebar.selectbox("Escolha uma opção", opcoes_menu)

menu_itens = {
    "Dashboard": "🏠",
    "Usuários": "👤",
    "Pacientes": "🧑‍⚕️",
    "Sinais Vitais": "💓",
    "Relatórios": "📊",
    "Mensagens": "💬",
    "Auditoria": "🕵️",
    "Parâmetros de Alerta": "⚠️",
    "Ajuda": "❓"
}
for item, emoji in menu_itens.items():
    if item in opcoes_menu:
        st.sidebar.markdown(f'<div class="sidebar-link">{emoji} {item}</div>', unsafe_allow_html=True)

# Tema customizado Streamlit
st.markdown("""
    <style>
    .stButton>button {background-color: #1976d2; color: white; font-weight: bold;}
    .stDownloadButton>button {background-color: #388e3c; color: white;}
    .stTextInput>div>input {background-color: #f0f4f8;}
    .stSidebar {background-color: #e3f2fd;}
    .stDataFrame {background-color: #fff;}
    .stAlert {border-radius: 8px;}
    </style>
""", unsafe_allow_html=True)

# Controle de telas: apenas uma tela exibida por vez
if opcao == "Dashboard":
    st.header("🏥 Painel Gerencial do Administrador")
    # Cards de resumo
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM pacientes")
    total_pacientes = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM profissionais")
    total_profissionais = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM alertas WHERE data_hora >= NOW() - INTERVAL '30 days'")
    total_alertas_30d = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM usuarios WHERE status = TRUE")
    total_usuarios_ativos = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM alertas WHERE status = 'pendente' AND data_hora >= NOW() - INTERVAL '7 days'")
    alertas_pendentes = cursor.fetchone()[0]
    conn.close()
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Pacientes", total_pacientes, "🧑‍⚕️")
    col2.metric("Profissionais", total_profissionais, "👨‍⚕️")
    col3.metric("Usuários Ativos", total_usuarios_ativos, "✅")
    col4.metric("Alertas 30 dias", total_alertas_30d, "⚠️")
    col5.metric("Alertas Pendentes", alertas_pendentes, "🚨")
    st.markdown("---")
    # Gráfico de alertas por dia (últimos 30 dias)
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DATE(data_hora), COUNT(*) FROM alertas
        WHERE data_hora >= NOW() - INTERVAL '30 days'
        GROUP BY DATE(data_hora)
        ORDER BY DATE(data_hora)
    """)
    rows = cursor.fetchall()
    conn.close()
    if rows:
        df_alertas = pd.DataFrame(rows, columns=["Data", "Alertas"])
        fig = px.bar(df_alertas, x="Data", y="Alertas", title="Alertas por Dia (últimos 30 dias)", color="Alertas", color_continuous_scale="magenta")
        st.plotly_chart(fig, use_container_width=True)
    # Gráfico de pacientes por profissional
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.nome, COUNT(p.id) FROM profissionais pr
        JOIN usuarios u ON pr.id_usuario = u.id
        LEFT JOIN pacientes p ON pr.id = p.id_profissional_responsavel
        GROUP BY u.nome
        ORDER BY COUNT(p.id) DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    if rows:
        df_pac_prof = pd.DataFrame(rows, columns=["Profissional", "Pacientes"])
        fig2 = px.bar(df_pac_prof, x="Profissional", y="Pacientes", title="Pacientes por Profissional", color="Pacientes", color_continuous_scale="bluered")
        st.plotly_chart(fig2, use_container_width=True)
    # Gráfico de status de alertas
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT status, COUNT(*) FROM alertas GROUP BY status")
    rows = cursor.fetchall()
    conn.close()
    if rows:
        df_status = pd.DataFrame(rows, columns=["Status", "Qtd"])
        fig3 = px.pie(df_status, names="Status", values="Qtd", title="Status dos Alertas")
        st.plotly_chart(fig3, use_container_width=True)

elif opcao == "Usuários":
    st.header("👤 Gerenciamento de Usuários")
    # Formulário de cadastro
    with st.expander("Cadastrar novo usuário"):
        with st.form("form_cadastro_usuario"):
            nome_novo = st.text_input("Nome")
            email_novo = st.text_input("E-mail")
            senha_novo = st.text_input("Senha", type="password")
            tipo_novo = st.selectbox("Tipo", ["Administrador", "Profissional", "Paciente"])
            cadastrar_btn = st.form_submit_button("Cadastrar")
            if cadastrar_btn:
                if not nome_novo or not email_novo or not senha_novo:
                    st.warning("Preencha todos os campos!")
                else:
                    usuario_id = cadastrar_usuario_novo(nome_novo, email_novo, senha_novo, tipo_novo)
                    if usuario_id:
                        st.success("Usuário cadastrado com sucesso!")
                        st.experimental_rerun()
    # Listagem e ativação/inativação
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nome, email, tipo, status FROM usuarios")
    usuarios = cursor.fetchall()
    conn.close()
    if usuarios:
        df_usuarios = pd.DataFrame(usuarios, columns=["ID", "Nome", "E-mail", "Tipo", "Status"])
        for idx, row in df_usuarios.iterrows():
            col1, col2, col3, col4, col5, col6 = st.columns([1,2,3,2,1,2])
            col1.write(row["ID"])
            col2.write(row["Nome"])
            col3.write(row["E-mail"])
            col4.write(row["Tipo"])
            status_label = "Ativo" if row["Status"] else "Inativo"
            col5.write(status_label)
            if col6.button(f"{'Inativar' if row['Status'] else 'Ativar'}", key=f"status_{row['ID']}"):
                conn = conectar_db()
                cursor = conn.cursor()
                cursor.execute("UPDATE usuarios SET status = %s WHERE id = %s", (not row["Status"], row["ID"]))
                conn.commit()
                conn.close()
                st.experimental_rerun()
    else:
        st.info("Nenhum usuário cadastrado.")

elif opcao == "Pacientes":
    st.header("🧑‍⚕️ Gerenciamento de Pacientes")
    if usuario_tipo in ["Administrador", "Profissional", "Profissional de Saúde"]:
        with st.expander("Cadastrar novo paciente"):
            with st.form("form_cadastro_paciente"):
                nome_pac = st.text_input("Nome completo")
                idade_pac = st.number_input("Idade", min_value=0, max_value=120)
                diagnostico_pac = st.text_input("Diagnóstico")
                # Seleção do profissional responsável
                conn = conectar_db()
                cursor = conn.cursor()
                cursor.execute("SELECT id, nome FROM usuarios WHERE tipo = 'Profissional'")
                profissionais = cursor.fetchall()
                conn.close()
                if profissionais:
                    prof_opcoes = {f"{nome} (ID {pid})": pid for pid, nome in profissionais}
                    prof_resp = st.selectbox("Profissional responsável", list(prof_opcoes.keys()))
                    prof_id = prof_opcoes[prof_resp]
                else:
                    st.warning("Cadastre um profissional antes de cadastrar pacientes!")
                    prof_id = None
                cadastrar_pac_btn = st.form_submit_button("Cadastrar paciente")
                if cadastrar_pac_btn:
                    if not nome_pac or not diagnostico_pac or prof_id is None:
                        st.warning("Preencha todos os campos!")
                    else:
                        dados_medicos = criptografar_dados({"idade": idade_pac, "diagnostico": diagnostico_pac})
                        usuario_id = cadastrar_usuario_novo(nome_pac, f"{nome_pac.lower().replace(' ','.')}@paciente.com", "Senha@123", "Paciente")
                        if usuario_id:
                            ok = cadastrar_paciente(usuario_id, prof_id, dados_medicos)
                            if ok:
                                st.success("Paciente cadastrado com sucesso!")
                                st.experimental_rerun()
    # Listagem de pacientes
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT p.id, u.nome, p.dados_medicos FROM pacientes p JOIN usuarios u ON p.id_usuario = u.id")
    pacientes = cursor.fetchall()
    conn.close()
    if pacientes:
        for pid, nome, dados_med in pacientes:
            with st.expander(f"Paciente: {nome} (ID {pid})"):
                dados = descriptografar_dados(dados_med)
                st.write(f"**Idade:** {dados.get('idade', '-') if dados else '-'}")
                st.write(f"**Diagnóstico:** {dados.get('diagnostico', '-') if dados else '-'}")
                # Histórico de sinais vitais
                conn = conectar_db()
                cursor = conn.cursor()
                cursor.execute("SELECT data_registro, temperatura, pressao, frequencia_cardiaca, saturacao FROM sinais_vitais WHERE paciente_id = %s ORDER BY data_registro DESC LIMIT 10", (pid,))
                sinais = cursor.fetchall()
                conn.close()
                if sinais:
                    st.write("**Últimos sinais vitais:**")
                    st.dataframe(pd.DataFrame(sinais, columns=["Data", "Temperatura", "Pressão", "Frequência", "Saturação"]))
                else:
                    st.info("Nenhum registro de sinais vitais para este paciente.")
    else:
        st.info("Nenhum paciente cadastrado.")

elif opcao == "Sinais Vitais":
    st.header("💓 Registros de Sinais Vitais")
    # Filtros
    params_alerta = buscar_parametros_alerta()
    st.info(f"Limites atuais: Temperatura {params_alerta['temp_min']}–{params_alerta['temp_max']}°C | Frequência {params_alerta['freq_min']}–{params_alerta['freq_max']} bpm | Saturação mínima {params_alerta['sat_min']}% | Pressão {params_alerta['pressao_min']}–{params_alerta['pressao_max']} mmHg")
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT p.id, u.nome FROM pacientes p JOIN usuarios u ON p.id_usuario = u.id")
    pacientes = cursor.fetchall()
    cursor.execute("SELECT id, nome FROM usuarios WHERE tipo = 'Profissional'")
    profissionais = cursor.fetchall()
    conn.close()
    paciente_id_filtro = None
    profissional_id_filtro = None
    if pacientes:
        pac_opcoes = {f"{nome} (ID {pid})": pid for pid, nome in pacientes}
        pac_selecionado = st.selectbox("Filtrar por paciente", ["Todos"] + list(pac_opcoes.keys()), key="rel_pac")
        if pac_selecionado != "Todos":
            paciente_id_filtro = pac_opcoes[pac_selecionado]
    if profissionais:
        prof_opcoes = {f"{nome} (ID {pid})": pid for pid, nome in profissionais}
        prof_selecionado = st.selectbox("Filtrar por profissional", ["Todos"] + list(prof_opcoes.keys()), key="rel_prof")
        if prof_selecionado != "Todos":
            profissional_id_filtro = prof_opcoes[prof_selecionado]
    data_inicio = st.date_input("Data inicial", value=None, key="rel_data_inicio")
    data_fim = st.date_input("Data final", value=None, key="rel_data_fim")
    # Consulta dos registros
    conn = conectar_db()
    cursor = conn.cursor()
    query = "SELECT s.id, u.nome, pr.nome, s.temperatura, s.pressao, s.frequencia_cardiaca, s.saturacao, s.data_registro FROM sinais_vitais s JOIN pacientes p ON s.paciente_id = p.id JOIN usuarios u ON p.id_usuario = u.id JOIN usuarios pr ON p.id_profissional_responsavel = pr.id"
    filtros = []
    params = []
    if paciente_id_filtro:
        filtros.append("s.paciente_id = %s")
        params.append(paciente_id_filtro)
    if profissional_id_filtro:
        filtros.append("p.id_profissional_responsavel = %s")
        params.append(profissional_id_filtro)
    if data_inicio:
        filtros.append("s.data_registro >= %s")
        params.append(str(data_inicio))
    if data_fim:
        filtros.append("s.data_registro <= %s")
        params.append(str(data_fim))
    if filtros:
        query += " WHERE " + " AND ".join(filtros)
    query += " ORDER BY s.data_registro DESC LIMIT 100"
    cursor.execute(query, tuple(params))
    registros = cursor.fetchall()
    conn.close()
    if registros:
        df_rel = pd.DataFrame(registros, columns=["ID", "Paciente", "Profissional", "Temperatura", "Pressão", "Frequência", "Saturação", "Data Registro"])
        st.dataframe(df_rel)
        # Exportar CSV
        csv = df_rel.to_csv(index=False).encode('utf-8')
        st.download_button("Exportar CSV", data=csv, file_name="relatorio_sinais_vitais.csv", mime="text/csv")
        st.info("Exportação PDF e gráficos interativos: Em breve!")
    else:
        st.info("Nenhum dado encontrado para os filtros selecionados.")

elif opcao == "Relatórios":
    st.header("📊 Relatórios e Gráficos")
    # Filtros
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT p.id, u.nome FROM pacientes p JOIN usuarios u ON p.id_usuario = u.id")
    pacientes = cursor.fetchall()
    cursor.execute("SELECT id, nome FROM usuarios WHERE tipo = 'Profissional'")
    profissionais = cursor.fetchall()
    conn.close()
    paciente_id_filtro = None
    profissional_id_filtro = None
    if pacientes:
        pac_opcoes = {f"{nome} (ID {pid})": pid for pid, nome in pacientes}
        pac_selecionado = st.selectbox("Filtrar por paciente", ["Todos"] + list(pac_opcoes.keys()), key="rel_pac")
        if pac_selecionado != "Todos":
            paciente_id_filtro = pac_opcoes[pac_selecionado]
    if profissionais:
        prof_opcoes = {f"{nome} (ID {pid})": pid for pid, nome in profissionais}
        prof_selecionado = st.selectbox("Filtrar por profissional", ["Todos"] + list(prof_opcoes.keys()), key="rel_prof")
        if prof_selecionado != "Todos":
            profissional_id_filtro = prof_opcoes[prof_selecionado]
    data_inicio = st.date_input("Data inicial", value=None, key="rel_data_inicio")
    data_fim = st.date_input("Data final", value=None, key="rel_data_fim")
    # Consulta dos registros
    conn = conectar_db()
    cursor = conn.cursor()
    query = "SELECT s.id, u.nome, pr.nome, s.temperatura, s.pressao, s.frequencia_cardiaca, s.saturacao, s.data_registro FROM sinais_vitais s JOIN pacientes p ON s.paciente_id = p.id JOIN usuarios u ON p.id_usuario = u.id JOIN usuarios pr ON p.id_profissional_responsavel = pr.id"
    filtros = []
    params = []
    if paciente_id_filtro:
        filtros.append("s.paciente_id = %s")
        params.append(paciente_id_filtro)
    if profissional_id_filtro:
        filtros.append("p.id_profissional_responsavel = %s")
        params.append(profissional_id_filtro)
    if data_inicio:
        filtros.append("s.data_registro >= %s")
        params.append(str(data_inicio))
    if data_fim:
        filtros.append("s.data_registro <= %s")
        params.append(str(data_fim))
    if filtros:
        query += " WHERE " + " AND ".join(filtros)
    query += " ORDER BY s.data_registro DESC LIMIT 100"
    cursor.execute(query, tuple(params))
    registros = cursor.fetchall()
    conn.close()
    if registros:
        df_rel = pd.DataFrame(registros, columns=["ID", "Paciente", "Profissional", "Temperatura", "Pressão", "Frequência", "Saturação", "Data Registro"])
        st.dataframe(df_rel)
        # Exportar CSV
        csv = df_rel.to_csv(index=False).encode('utf-8')
        st.download_button("Exportar CSV", data=csv, file_name="relatorio_sinais_vitais.csv", mime="text/csv")
        st.info("Exportação PDF e gráficos interativos: Em breve!")
    else:
        st.info("Nenhum dado encontrado para os filtros selecionados.")

elif opcao == "Mensagens":
    st.header("💬 Mensagens Internas")
    # Filtros
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nome FROM usuarios")
    usuarios = cursor.fetchall()
    conn.close()
    remetente_id_filtro = None
    destinatario_id_filtro = None
    if usuarios:
        user_opcoes = {f"{nome} (ID {uid})": uid for uid, nome in usuarios}
        rem_selecionado = st.selectbox("Filtrar por remetente", ["Todos"] + list(user_opcoes.keys()), key="msg_rem")
        if rem_selecionado != "Todos":
            remetente_id_filtro = user_opcoes[rem_selecionado]
        dest_selecionado = st.selectbox("Filtrar por destinatário", ["Todos"] + list(user_opcoes.keys()), key="msg_dest")
        if dest_selecionado != "Todos":
            destinatario_id_filtro = user_opcoes[dest_selecionado]
    # Formulário de envio
    with st.expander("Enviar nova mensagem"):
        with st.form("form_envio_msg"):
            if usuarios:
                dest_envio = st.selectbox("Destinatário", list(user_opcoes.keys()), key="envio_dest")
                dest_id_envio = user_opcoes[dest_envio]
                texto_msg = st.text_area("Mensagem")
                enviar_btn = st.form_submit_button("Enviar")
                if enviar_btn:
                    if not texto_msg.strip():
                        st.warning("Digite uma mensagem!")
                    else:
                        ok = enviar_mensagem(st.session_state.usuario[0], dest_id_envio, texto_msg)
                        if ok:
                            st.success("Mensagem enviada!")
                            st.experimental_rerun()
            else:
                st.info("Cadastre usuários para enviar mensagens.")
    # Listagem das mensagens
    conn = conectar_db()
    cursor = conn.cursor()
    query = "SELECT m.id, u1.nome, u2.nome, m.texto, m.data_envio FROM mensagens m JOIN usuarios u1 ON m.id_remetente = u1.id JOIN usuarios u2 ON m.id_destinatario = u2.id"
    filtros = []
    params = []
    if remetente_id_filtro:
        filtros.append("m.id_remetente = %s")
        params.append(remetente_id_filtro)
    if destinatario_id_filtro:
        filtros.append("m.id_destinatario = %s")
        params.append(destinatario_id_filtro)
    if filtros:
        query += " WHERE " + " AND ".join(filtros)
    query += " ORDER BY m.data_envio DESC LIMIT 50"
    cursor.execute(query, tuple(params))
    msgs = cursor.fetchall()
    conn.close()
    if msgs:
        st.dataframe(pd.DataFrame(msgs, columns=["ID", "Remetente", "Destinatário", "Texto", "Data Envio"]))
    else:
        st.info("Nenhuma mensagem encontrada para os filtros selecionados.")

elif opcao == "Auditoria":
    st.header("🕵️ Auditoria de Ações")
    # Filtros
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nome FROM usuarios")
    usuarios = cursor.fetchall()
    cursor.execute("SELECT DISTINCT acao FROM auditoria")
    acoes = [row[0] for row in cursor.fetchall()]
    conn.close()
    usuario_id_filtro = None
    acao_filtro = None
    if usuarios:
        user_opcoes = {f"{nome} (ID {uid})": uid for uid, nome in usuarios}
        user_selecionado = st.selectbox("Filtrar por usuário", ["Todos"] + list(user_opcoes.keys()), key="aud_user")
        if user_selecionado != "Todos":
            usuario_id_filtro = user_opcoes[user_selecionado]
    if acoes:
        acao_selecionada = st.selectbox("Filtrar por ação", ["Todas"] + acoes, key="aud_acao")
        if acao_selecionada != "Todas":
            acao_filtro = acao_selecionada
    data_inicio = st.date_input("Data inicial", value=None, key="aud_data_inicio")
    data_fim = st.date_input("Data final", value=None, key="aud_data_fim")
    # Consulta dos registros
    conn = conectar_db()
    cursor = conn.cursor()
    query = "SELECT a.id, u.nome, a.acao, a.detalhes, a.data_hora FROM auditoria a JOIN usuarios u ON a.usuario_id = u.id"
    filtros = []
    params = []
    if usuario_id_filtro:
        filtros.append("a.usuario_id = %s")
        params.append(usuario_id_filtro)
    if acao_filtro:
        filtros.append("a.acao = %s")
        params.append(acao_filtro)
    if data_inicio:
        filtros.append("a.data_hora >= %s")
        params.append(str(data_inicio))
    if data_fim:
        filtros.append("a.data_hora <= %s")
        params.append(str(data_fim))
    if filtros:
        query += " WHERE " + " AND ".join(filtros)
    query += " ORDER BY a.data_hora DESC LIMIT 100"
    cursor.execute(query, tuple(params))
    aud = cursor.fetchall()
    conn.close()
    if aud:
        df_aud = pd.DataFrame(aud, columns=["ID", "Usuário", "Ação", "Detalhes", "Data/Hora"])
        st.dataframe(df_aud)
        # Exportar CSV
        csv = df_aud.to_csv(index=False).encode('utf-8')
        st.download_button("Exportar CSV", data=csv, file_name="auditoria.csv", mime="text/csv")
    else:
        st.info("Nenhum registro de auditoria encontrado para os filtros selecionados.")

elif opcao == "Parâmetros de Alerta":
    st.header("⚠️ Parâmetros de Alerta")
    # Checar/criar tabela de parâmetros se necessário
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS parametros_alerta (
            id SERIAL PRIMARY KEY,
            temp_min FLOAT, temp_max FLOAT,
            freq_min INT, freq_max INT,
            sat_min INT,
            pressao_min VARCHAR(10), pressao_max VARCHAR(10)
        )
    """)
    conn.commit()
    # Buscar parâmetros atuais
    cursor.execute("SELECT temp_min, temp_max, freq_min, freq_max, sat_min, pressao_min, pressao_max FROM parametros_alerta ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    if row:
        temp_min, temp_max, freq_min, freq_max, sat_min, pressao_min, pressao_max = row
    else:
        temp_min, temp_max = 35.0, 38.0
        freq_min, freq_max = 50, 120
        sat_min = 90
        pressao_min, pressao_max = "90/60", "140/90"
    with st.form("form_param_alerta"):
        st.subheader("Limites de alerta para sinais vitais")
        col1, col2 = st.columns(2)
        with col1:
            temp_min_novo = st.number_input("Temperatura mínima (°C)", value=temp_min, min_value=25.0, max_value=45.0, step=0.1)
            freq_min_novo = st.number_input("Frequência mínima (bpm)", value=freq_min, min_value=20, max_value=220)
            sat_min_novo = st.number_input("Saturação mínima (%)", value=sat_min, min_value=50, max_value=100)
            pressao_min_novo = st.text_input("Pressão mínima (Ex: 90/60)", value=pressao_min)
        with col2:
            temp_max_novo = st.number_input("Temperatura máxima (°C)", value=temp_max, min_value=25.0, max_value=45.0, step=0.1)
            freq_max_novo = st.number_input("Frequência máxima (bpm)", value=freq_max, min_value=20, max_value=220)
            pressao_max_novo = st.text_input("Pressão máxima (Ex: 140/90)", value=pressao_max)
        salvar_btn = st.form_submit_button("Salvar parâmetros")
        if salvar_btn:
            conn = conectar_db()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO parametros_alerta (temp_min, temp_max, freq_min, freq_max, sat_min, pressao_min, pressao_max) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (temp_min_novo, temp_max_novo, freq_min_novo, freq_max_novo, sat_min_novo, pressao_min_novo, pressao_max_novo))
            conn.commit()
            conn.close()
            st.success("Parâmetros de alerta salvos com sucesso!")
            st.experimental_rerun()
    st.info("Em breve: integração dos limites de alerta em todo o sistema.")

elif opcao == "Ajuda":
    st.header("ℹ️ Ajuda e Sobre o Sistema")
    st.markdown("""
    **Telemonitoramento CEUB**
    
    - Sistema para acompanhamento remoto de sinais vitais.
    - Alertas automáticos, mensagens internas, relatórios e auditoria.
    - Desenvolvido para garantir segurança, privacidade e facilidade de uso.
    
    **Dúvidas frequentes:**
    - Como cadastrar um paciente? Apenas profissionais ou admin podem cadastrar.
    - Como configurar alertas? Menu 'Parâmetros de Alerta' (admin).
    - Como baixar relatórios? Menu 'Relatórios' > Baixar PDF.
    - Como excluir meus dados? Solicite ao admin ou use a opção de anonimização.
    
    **Contato:** suporte@ceub.edu.br
    """)

# Adicionar opção no menu
if usuario_tipo == "Administrador":
    opcoes_menu = ["Dashboard", "Usuários", "Pacientes", "Sinais Vitais", "Relatórios", "Mensagens", "Auditoria", "Parâmetros de Alerta", "Ajuda"]

# Descriptografar ao exibir dados médicos
if usuario_tipo in ["Administrador", "Profissional", "Profissional de Saúde"] and opcao == "Pacientes":
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, id_usuario, dados_medicos FROM pacientes")
    pacientes = cursor.fetchall()
    conn.close()
    for pid, uid, dados_med in pacientes:
        dados = descriptografar_dados(dados_med)
        st.write(f"Paciente ID: {pid} | Dados: {dados}")

def criar_campo_primeiro_acesso():
    """
    Garante que a coluna 'primeiro_acesso' exista na tabela usuarios, criando-a se necessário.
    """
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute('''
        ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS primeiro_acesso BOOLEAN DEFAULT TRUE;
    ''')
    conn.commit()
    conn.close()
criar_campo_primeiro_acesso()
