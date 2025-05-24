import streamlit as st
import psycopg2
import hashlib
import pandas as pd
import os
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
import logging
import re
import matplotlib.pyplot as plt
from datetime import datetime, date, timedelta

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

load_dotenv()

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

# Funções de banco de dados
def conectar_db():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        port=os.getenv("DB_PORT"),
    )

def hash_senha(senha):
    return hashlib.sha256(senha.encode()).hexdigest()

# Funções de validação e alerta
def validar_pressao(pressao):
    """
    Valida o formato e os valores da pressão arterial.
    """
    logging.info(f"Validando pressão arterial: {pressao}")
    if not re.match(PRESSAO_PATTERN, pressao):
        logging.warning(f"Formato de pressão inválido: {pressao}")
        return False, "Formato inválido. Use: 120/80"
    try:
        sist, diast = map(int, pressao.split('/'))
        if not (90 <= sist <= 180 and 60 <= diast <= 110):
            logging.warning(f"Valores de pressão fora do intervalo: {pressao}")
            return False, "Valores fora do intervalo normal"
        return True, ""
    except:
        logging.error(f"Erro ao processar valores de pressão: {pressao}")
        return False, "Erro ao processar valores"

def checar_alertas(sinais):
    """
    Verifica se há alertas nos sinais vitais registrados.
    """
    logging.info(f"Checando alertas para sinais: {sinais}")
    alertas = []
    temperatura = sinais['temperatura']
    pressao = sinais['pressao']
    frequencia = sinais['frequencia']
    saturacao = sinais['saturacao']

    # Temperatura
    if temperatura < TEMP_MIN_ALERTA or temperatura > TEMP_MAX_ALERTA:
        msg = f"Temperatura fora do padrão: {temperatura}°C"
        alertas.append(msg)
        logging.warning(f"ALERTA: {msg}")
    
    # Pressão Arterial
    valido, msg = validar_pressao(pressao)
    if not valido:
        alertas.append(f"Pressão arterial: {msg}")
        logging.warning(f"ALERTA: Pressão arterial inválida - {msg}")
    else:
        sist, diast = map(int, pressao.split('/'))
        if sist > 140 or diast > 90:
            msg = f"Pressão Alta: {pressao} mmHg"
            alertas.append(msg)
            logging.warning(f"ALERTA: {msg}")
        if sist < 90 or diast < 60:
            msg = f"Pressão Baixa: {pressao} mmHg"
            alertas.append(msg)
            logging.warning(f"ALERTA: {msg}")
    
    # Frequência Cardíaca
    if frequencia < FREQ_MIN_ALERTA or frequencia > FREQ_MAX_ALERTA:
        msg = f"Frequência cardíaca fora do padrão: {frequencia} bpm"
        alertas.append(msg)
        logging.warning(f"ALERTA: {msg}")
    
    # Saturação
    if saturacao < SAT_MIN_ALERTA:
        msg = f"Saturação baixa: {saturacao}%"
        alertas.append(msg)
        logging.warning(f"ALERTA: {msg}")
    
    if alertas:
        logging.warning(f"Total de alertas detectados: {len(alertas)}")
    else:
        logging.info("Nenhum alerta detectado")
    
    return alertas

def enviar_alerta_email(paciente_nome, alertas, paciente_email, profissional_email):
    """
    Envia e-mails de alerta para o paciente e o profissional de saúde.
    """
    EMAIL_SENDER = os.getenv("EMAIL_SENDER")
    EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

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
            server.starttls()
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg_prof)
            server.send_message(msg_pac)
        print("Alertas enviados por email!")
        logging.info(f"Alertas enviados para {paciente_email} e {profissional_email}")
        st.success("✉️ Alertas enviados por email!")
    except Exception as e:
        print(f"Erro ao enviar alertas por email: {e}")
        logging.error(f"Erro ao enviar alertas por email: {str(e)}")
        raise Exception(f"Erro ao enviar alertas por email: {str(e)}")

# Funções de consulta
def select_usuarios_pacientes():
    """
    Retorna todos os usuários com perfil de paciente.
    """
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nome FROM usuarios WHERE perfil = 'Paciente'")
    usuarios = cursor.fetchall()
    conn.close()
    return usuarios

def buscar_pacientes_do_profissional(profissional_id):
    """
    Retorna todos os pacientes vinculados a um profissional.
    """
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.id, u.nome
        FROM pacientes p
        JOIN usuarios u ON p.usuario_id = u.id
        WHERE p.profissional_responsavel_id = %s
    """, (profissional_id,))
    pacientes = cursor.fetchall()
    conn.close()
    return pacientes

def buscar_todos_pacientes():
    """
    Retorna todos os pacientes cadastrados.
    """
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.id, u.nome
        FROM pacientes p
        JOIN usuarios u ON p.usuario_id = u.id
    """)
    pacientes = cursor.fetchall()
    conn.close()
    return pacientes

# Funções de cadastro
def cadastrar_usuario(nome, email, senha, perfil, especialidade, registro):
    """
    Cadastra um novo usuário no sistema.
    """
    conn = conectar_db()
    cursor = conn.cursor()
    senha_hash = hash_senha(senha)
    try:
        cursor.execute(
            "INSERT INTO usuarios (nome, email, senha, perfil, especialidade, registro_profissional) VALUES (%s, %s, %s, %s, %s, %s)",
            (nome, email, senha_hash, perfil, especialidade, registro)
        )
        conn.commit()
        st.success("Usuário cadastrado com sucesso!")
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        st.error("Este e-mail já está cadastrado!")
    finally:
        conn.close()

def cadastrar_paciente(usuario_id, idade, diagnostico, profissional_id):
    """
    Cadastra um novo paciente no sistema.
    """
    conn = conectar_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO pacientes (usuario_id, idade, diagnostico, profissional_responsavel_id) VALUES (%s, %s, %s, %s)",
            (usuario_id, idade, diagnostico, profissional_id)
        )
        conn.commit()
        st.success("Paciente cadastrado com sucesso!")
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        st.error("Esse usuário já está vinculado a um paciente!")
    except Exception as e:
        conn.rollback()
        st.error(f"Erro ao cadastrar paciente: {e}")
    finally:
        conn.close()

def cadastrar_sinais_vitais(paciente_id, temperatura, pressao, frequencia, saturacao):
    """
    Registra os sinais vitais de um paciente e envia alertas se necessário.
    """
    logging.info(f"Iniciando registro de sinais vitais para paciente_id={paciente_id}")
    print(f"Registrando sinais: temp={temperatura}, pressao={pressao}, freq={frequencia}, sat={saturacao}")
    
    conn = conectar_db()
    cursor = conn.cursor()
    try:
        # Salva os sinais vitais
        cursor.execute(
            "INSERT INTO sinais_vitais (paciente_id, temperatura, pressao, frequencia_cardiaca, saturacao) VALUES (%s, %s, %s, %s, %s)",
            (paciente_id, temperatura, pressao, frequencia, saturacao)
        )
        logging.info(f"Sinais vitais registrados com sucesso para paciente_id={paciente_id}")
        
        # Verifica alertas
        sinais = {
            'temperatura': float(temperatura),
            'pressao': pressao,
            'frequencia': int(frequencia),
            'saturacao': int(saturacao)
        }
        alertas = checar_alertas(sinais)
        
        if alertas:
            logging.warning(f"Alertas detectados para paciente_id={paciente_id}: {alertas}")
            # Busca emails do paciente e do profissional
            cursor.execute("""
                SELECT u.nome, u.email, up.email as prof_email
                FROM pacientes p
                JOIN usuarios u ON p.usuario_id = u.id
                JOIN usuarios up ON p.profissional_responsavel_id = up.id
                WHERE p.id = %s
            """, (paciente_id,))
            dados = cursor.fetchone()
            if dados:
                paciente_nome, paciente_email, profissional_email = dados
                try:
                    enviar_alerta_email(paciente_nome, alertas, paciente_email, profissional_email)
                except Exception as e:
                    print(f"Erro ao enviar alertas: {e}")
                    logging.error(f"Falha ao enviar alertas: {str(e)}")
                    st.warning("⚠️ Os sinais vitais foram registrados, mas não foi possível enviar os alertas por email. A equipe foi notificada.")
            else:
                logging.error(f"Dados do paciente/profissional não encontrados para paciente_id={paciente_id}")
                st.warning("⚠️ Não foi possível enviar alertas: dados do paciente ou profissional não encontrados.")
        
        conn.commit()
        st.success("✅ Sinais vitais registrados com sucesso!")
        st.balloons()
    except Exception as e:
        conn.rollback()
        print(f"Erro ao registrar sinais vitais: {e}")
        logging.error(f"Erro ao registrar sinais vitais: {str(e)}")
        st.error("Houve uma falha ao registrar os sinais vitais. Por favor, tente novamente ou contate o suporte.")
    finally:
        conn.close()

# Funções de interface
def criar_campos_sinais_vitais():
    """
    Cria os campos de entrada para os sinais vitais com validação em tempo real.
    """
    col1, col2 = st.columns(2)

    with col1:
        temperatura = st.number_input(
            "Temperatura (°C)", 
            min_value=TEMP_MIN_LIMITE,
            max_value=TEMP_MAX_LIMITE,
            value=36.5,
            step=0.1,
            help="Valores normais: 35.0–38.0°C. Valores fora deste intervalo serão sinalizados ao profissional."
        )
        if temperatura < TEMP_MIN_ALERTA or temperatura > TEMP_MAX_ALERTA:
            st.warning("⚠️ Temperatura fora do normal (35.0–38.0°C). Será sinalizado como alerta.")

        frequencia = st.number_input(
            "Frequência Cardíaca (bpm)",
            min_value=FREQ_MIN_LIMITE,
            max_value=FREQ_MAX_LIMITE,
            value=80,
            help="Normal: 50–120 bpm. Valores fora deste intervalo serão sinalizados ao profissional."
        )
        if frequencia < FREQ_MIN_ALERTA or frequencia > FREQ_MAX_ALERTA:
            st.warning("⚠️ Frequência cardíaca fora do normal (50–120 bpm). Será sinalizado como alerta.")

    with col2:
        pressao = st.text_input(
            "Pressão Arterial (Ex: 120/80)",
            help="Digite no formato: sistólica/diastólica. Normal: 90/60–140/90 mmHg. Valores fora deste intervalo serão sinalizados."
        )
        
        saturacao = st.number_input(
            "Saturação (%)",
            min_value=50,
            max_value=SAT_MAX,
            value=97,
            help="Normal: 90–100%. Valores baixos serão sinalizados ao profissional."
        )
        if saturacao < SAT_MIN_ALERTA:
            st.warning("⚠️ Saturação baixa (< 90%). Será sinalizado como alerta.")
    
    return temperatura, pressao, frequencia, saturacao

# Funções de visualização e gráficos
def plotar_evolucao_sinais(sinais_df):
    """
    Exibe gráfico de evolução dos sinais vitais usando matplotlib.
    sinais_df deve ter as colunas: Data, Temperatura, Frequência, Saturação
    """
    if sinais_df.empty:
        st.info("Ainda não há registros para mostrar o gráfico de evolução.")
        return

    st.subheader("📈 Evolução dos seus sinais vitais")
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # Convertendo data para string se necessário
    sinais_df['Data'] = sinais_df['Data'].astype(str)
    
    # Plotando os sinais
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

def mostrar_ultimos_registros(df):
    """
    Exibe os últimos registros de sinais vitais em formato de tabela.
    """
    if df.empty:
        st.info("Ainda não há registros para mostrar.")
        return
        
    st.subheader("🗂️ Seus últimos registros")
    st.dataframe(df, use_container_width=True)

def verificar_registro_hoje(paciente_id):
    """
    Verifica se o paciente já registrou sinais vitais hoje.
    Retorna True se já registrou, False caso contrário.
    """
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
    conn.close()
    return registrado > 0

def mostrar_lembrete_registro(paciente_id):
    """
    Exibe um lembrete caso o paciente não tenha registrado seus sinais vitais hoje.
    """
    if verificar_registro_hoje(paciente_id):
        st.success("✅ Você já registrou seus sinais vitais hoje. Obrigado pelo comprometimento!")
    else:
        st.warning("⏰ Lembrete: você ainda não registrou seus sinais vitais hoje! " 
                  "O registro diário é importante para seu acompanhamento.")

def formatar_mensagem_alerta(alertas):
    """
    Formata as mensagens de alerta de forma mais amigável e personalizada.
    """
    mensagens_personalizadas = {
        "temperatura": "Sua temperatura está alterada. Mantenha-se hidratado e monitore.",
        "frequencia": "Seus batimentos cardíacos estão alterados. Procure descansar um pouco.",
        "saturacao": "Sua saturação está baixa. Respire profundamente e procure um local arejado.",
        "pressao": "Sua pressão arterial está alterada. Mantenha a calma e descanse."
    }
    
    msg_alertas = []
    for alerta in alertas:
        if "temperatura" in alerta.lower():
            msg_alertas.append(mensagens_personalizadas["temperatura"])
        elif "frequência" in alerta.lower():
            msg_alertas.append(mensagens_personalizadas["frequencia"])
        elif "saturação" in alerta.lower():
            msg_alertas.append(mensagens_personalizadas["saturacao"])
        elif "pressão" in alerta.lower():
            msg_alertas.append(mensagens_personalizadas["pressao"])
        else:
            msg_alertas.append(alerta)
    
    return ("\n\n".join(msg_alertas) + 
            "\n\n⚕️ Nossa equipe já foi notificada. Se estiver se sentindo mal, procure orientação médica!")

def obter_registros_sinais(paciente_id, dias=7):
    """
    Obtém os registros de sinais vitais do paciente no período especificado.
    """
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
    conn.close()
    
    if not dados:
        return pd.DataFrame()
    
    df = pd.DataFrame(dados, columns=["Data", "Temperatura", "Pressão", "Frequência", "Saturação"])
    return df

# Funções de autenticação
def autenticar(email, senha):
    """
    Autentica um usuário no sistema.
    Retorna os dados do usuário se autenticado, None caso contrário.
    """
    conn = conectar_db()
    cursor = conn.cursor()
    senha_hash = hash_senha(senha)
    cursor.execute("SELECT * FROM usuarios WHERE email=%s AND senha=%s", (email, senha_hash))
    usuario = cursor.fetchone()
    conn.close()
    return usuario

# --------- INÍCIO DO APP ---------
if "usuario" not in st.session_state:
    st.session_state.usuario = None

if not st.session_state.usuario:
    st.title("🔐 Login - Telemonitoramento CEUB")
    email = st.text_input("E-mail")
    senha = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        usuario = autenticar(email, senha)
        if usuario:
            st.session_state.usuario = usuario
            st.success(f"Bem-vindo(a), {usuario[1]}!")
            st.experimental_rerun() if hasattr(st, "experimental_rerun") else st.rerun()
        else:
            st.error("Credenciais inválidas!")
    st.stop()

# ---- MENU LATERAL ----
perfil = st.session_state.usuario[4]
st.sidebar.title("Menu")
if perfil == "Administrador":
    opcoes_menu = ["Dashboard", "Usuários", "Pacientes", "Sinais Vitais", "Relatórios"]
elif perfil == "Profissional de Saúde":
    opcoes_menu = ["Pacientes", "Sinais Vitais", "Relatórios", "Usuários"]
elif perfil == "Paciente":
    opcoes_menu = ["Sinais Vitais", "Relatórios"]
else:
    opcoes_menu = ["Sair"]
opcao = st.sidebar.selectbox("Escolha uma opção", opcoes_menu)

if st.sidebar.button("Logout"):
    st.session_state.usuario = None
    st.rerun()

# ---- TELAS ----
if opcao == "Usuários":
    if perfil == "Administrador":
        st.header("Cadastro de Usuários")
        with st.form("form_usuario"):
            nome = st.text_input("Nome completo")
            email = st.text_input("E-mail")
            senha = st.text_input("Senha", type="password")
            perfil = st.selectbox("Perfil", ["Administrador", "Profissional de Saúde", "Paciente"])
            especialidade = st.text_input("Especialidade") if perfil == "Profissional de Saúde" else ""
            registro = st.text_input("Registro Profissional") if perfil == "Profissional de Saúde" else ""
            cadastrar = st.form_submit_button("Cadastrar")
            if cadastrar:
                if not (nome and email and senha):
                    st.warning("Preencha todos os campos obrigatórios!")
                elif perfil == "Profissional de Saúde" and (not especialidade or not registro):
                    st.warning("Informe a especialidade e o registro!")
                else:
                    cadastrar_usuario(nome, email, senha, perfil, especialidade, registro)
    elif perfil == "Profissional de Saúde":
        st.header("Cadastro de Usuários - Pacientes")
        with st.form("form_usuario"):
            nome = st.text_input("Nome completo")
            email = st.text_input("E-mail")
            senha = st.text_input("Senha", type="password")
            perfil_usuario = "Paciente"
            cadastrar = st.form_submit_button("Cadastrar")
            if cadastrar:
                if not (nome and email and senha):
                    st.warning("Preencha todos os campos!")
                else:
                    cadastrar_usuario(nome, email, senha, perfil_usuario, "", "")
    else:
        st.warning("Sem permissão para acessar.")

elif opcao == "Pacientes":
    if perfil in ["Administrador", "Profissional de Saúde"]:
        st.header("Cadastro de Pacientes")
        usuarios_pacientes = select_usuarios_pacientes()
        if not usuarios_pacientes:
            st.info("Cadastre primeiro o usuário como Paciente.")
        else:
            with st.form("form_paciente"):
                opcoes = {f"{nome} (ID:{id})": id for id, nome in usuarios_pacientes}
                usuario_escolhido = st.selectbox("Usuário paciente", list(opcoes.keys()))
                usuario_id_val = opcoes[usuario_escolhido] if usuario_escolhido else None
                idade = st.text_input("Idade")
                diagnostico = st.text_input("Diagnóstico clínico")
                profissional_id = st.session_state.usuario[0] if perfil == "Profissional de Saúde" else None
                cadastrar = st.form_submit_button("Cadastrar")
                if cadastrar:
                    if not (usuario_id_val and idade and diagnostico and profissional_id):
                        st.warning("Preencha todos os campos!")
                    elif not idade.isdigit() or int(idade) <= 0:
                        st.warning("Idade inválida!")
                    else:
                        cadastrar_paciente(usuario_id_val, int(idade), diagnostico, profissional_id)
    else:
        st.warning("Sem permissão para acessar.")

elif opcao == "Sinais Vitais":
    if perfil in ["Administrador", "Profissional de Saúde"]:
        st.header("Monitoramento de Pacientes")
        
        # Seção de visualização
        st.subheader("📊 Acompanhamento dos Pacientes")
        pacientes = buscar_todos_pacientes() if perfil == "Administrador" else buscar_pacientes_do_profissional(st.session_state.usuario[0])
        if not pacientes:
            st.info("Nenhum paciente cadastrado ainda.")
        else:
            # Seleção do paciente e período
            col1, col2 = st.columns([2, 1])
            with col1:
                paciente_selecionado = st.selectbox(
                    "Selecione um paciente para visualizar registros",
                    [f"{nome} (ID:{pid})" for pid, nome in pacientes]
                )
                paciente_id = int(paciente_selecionado.split("ID:")[1][:-1])
            
            with col2:
                periodo = st.selectbox(
                    "Período de análise", 
                    ["Últimos 7 dias", "Últimos 30 dias", "Todos"],
                    help="Selecione o período para análise dos dados"
                )
                dias = 7 if periodo == "Últimos 7 dias" else 30 if periodo == "Últimos 30 dias" else 3650
            
            # Busca e mostra os dados
            df = obter_registros_sinais(paciente_id, dias)
            if not df.empty:
                # Tabs para organizar visualizações
                tab1, tab2, tab3 = st.tabs(["📈 Gráficos", "📋 Registros", "📝 Novo Registro"])
                
                with tab1:
                    plotar_evolucao_sinais(df)
                    
                    # Estatísticas básicas
                    st.subheader("📊 Resumo Estatístico")
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Temperatura Média", f"{df['Temperatura'].mean():.1f}°C")
                    with col2:
                        st.metric("Freq. Cardíaca Média", f"{df['Frequência'].mean():.0f} bpm")
                    with col3:
                        st.metric("Saturação Média", f"{df['Saturação'].mean():.0f}%")
                    with col4:
                        st.metric("Total Registros", len(df))
                
                with tab2:
                    st.subheader("📋 Histórico de Registros")
                    st.dataframe(df, use_container_width=True)
                    
                    # Opção para download
                    csv = df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        "⬇️ Download dos dados",
                        csv,
                        f"registros_paciente_{paciente_id}.csv",
                        "text/csv",
                        key='download-csv'
                    )
                
                with tab3:
                    st.subheader("📝 Registrar Novos Sinais")
                    with st.form("form_sinais"):
                        temperatura, pressao, frequencia, saturacao = criar_campos_sinais_vitais()
                        
                        if st.form_submit_button("Registrar Sinais", use_container_width=True):
                            if not pressao:
                                st.warning("Por favor, informe a pressão arterial.")
                            else:
                                valido, msg = validar_pressao(pressao)
                                if not valido:
                                    st.warning(f"Pressão arterial: {msg}")
                                else:
                                    with st.spinner("Registrando sinais vitais..."):
                                        try:
                                            sinais = {
                                                'temperatura': float(temperatura),
                                                'pressao': pressao,
                                                'frequencia': int(frequencia),
                                                'saturacao': int(saturacao)
                                            }
                                            alertas = checar_alertas(sinais)
                                            cadastrar_sinais_vitais(paciente_id, temperatura, pressao, frequencia, saturacao)
                                            
                                            if alertas:
                                                st.warning(
                                                    "⚠️ Alertas detectados:\n" + 
                                                    "\n".join(f"- {alerta}" for alerta in alertas)
                                                )
                                            else:
                                                st.success("✅ Sinais vitais registrados com sucesso!")
                                                st.balloons()
                                        except Exception as e:
                                            logging.error(f"Erro ao registrar sinais: {str(e)}")
                                            st.error("Ocorreu um erro ao registrar os sinais vitais. Por favor, tente novamente.")
            else:
                st.info("Nenhum registro encontrado para o período selecionado.")
                
                # Opção para novo registro
                st.markdown("---")
                st.subheader("📝 Registrar Primeiro Sinal Vital")
                with st.form("form_primeiro_sinal"):
                    temperatura, pressao, frequencia, saturacao = criar_campos_sinais_vitais()
                    if st.form_submit_button("Registrar Primeiro Sinal", use_container_width=True):
                        if not pressao:
                            st.warning("Por favor, informe a pressão arterial.")
                        else:
                            valido, msg = validar_pressao(pressao)
                            if not valido:
                                st.warning(f"Pressão arterial: {msg}")
                            else:
                                with st.spinner("Registrando sinais vitais..."):
                                    try:
                                        cadastrar_sinais_vitais(paciente_id, temperatura, pressao, frequencia, saturacao)
                                        st.success("✅ Primeiro registro realizado com sucesso!")
                                        st.balloons()
                                        st.experimental_rerun()
                                    except Exception as e:
                                        logging.error(f"Erro ao registrar sinais: {str(e)}")
                                        st.error("Ocorreu um erro ao registrar os sinais vitais. Por favor, tente novamente.")
    elif perfil == "Paciente":
        st.header("Meus Sinais Vitais")
        usuario_id = st.session_state.usuario[0]
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM pacientes WHERE usuario_id = %s", (usuario_id,))
        resultado = cursor.fetchone()
        conn.close()

        if not resultado:
            st.info("Peça para o profissional responsável fazer seu cadastro!")
        else:
            paciente_id = resultado[0]
            
            # Mostra lembrete de registro
            mostrar_lembrete_registro(paciente_id)
            
            # Tabs para organizar o conteúdo
            tab1, tab2 = st.tabs(["📝 Registrar", "📊 Acompanhamento"])
            
            with tab1:
                st.info(
                    "Registre seus sinais vitais diariamente, mesmo que estejam dentro do normal. "
                    "Isso ajuda sua equipe a acompanhar melhor sua evolução."
                )
                
                with st.form("form_meus_sinais"):
                    col1, col2 = st.columns(2)
                    with col1:
                        temperatura = st.number_input(
                            "Temperatura (°C)", 
                            min_value=20.0,  # Amplo para forçar casos de alerta
                            max_value=45.0,
                            value=36.5,
                            step=0.1,
                            help=f"Intervalo normal: {TEMP_MIN}°C - {TEMP_MAX}°C"
                        )
                        frequencia = st.number_input(
                            "Frequência Cardíaca (bpm)",
                            min_value=10,
                            max_value=250,
                            value=80,
                            help=f"Intervalo normal: {FREQ_MIN}-{FREQ_MAX} bpm"
                        )
                    with col2:
                        pressao = st.text_input(
                            "Pressão Arterial (Ex: 120/80)",
                            help="Digite no formato: sistólica/diastólica (Ex: 120/80)"
                        )
                        saturacao = st.number_input(
                            "Saturação (%)",
                            min_value=50,
                            max_value=100,
                            value=97,
                            help=f"Valor mínimo recomendado: {SAT_MIN}%"
                        )
                    
                    # Só bloqueia se o FORMATO da pressão estiver inválido!
                    valido, msg = validar_pressao(pressao) if pressao else (False, "Pressão não informada")
                    if st.form_submit_button("Registrar Meus Sinais", use_container_width=True):
                        if not pressao:
                            st.warning("Por favor, informe sua pressão arterial.")
                        elif not valido and ("Formato" in msg or "Erro" in msg):
                            st.warning(f"Pressão arterial: {msg}")
                        else:
                            with st.spinner("Registrando seus sinais vitais..."):
                                try:
                                    # Registra os sinais
                                    sinais = {
                                        'temperatura': float(temperatura),
                                        'pressao': pressao,
                                        'frequencia': int(frequencia),
                                        'saturacao': int(saturacao)
                                    }
                                    alertas = checar_alertas(sinais)
                                    cadastrar_sinais_vitais(paciente_id, temperatura, pressao, frequencia, saturacao)
                                    
                                    # Feedback personalizado
                                    if alertas:
                                        st.warning(formatar_mensagem_alerta(alertas))
                                    else:
                                        st.success("✅ Seus sinais vitais foram registrados com sucesso. Continue acompanhando diariamente!")
                                        st.balloons()
                                except Exception as e:
                                    logging.error(f"Erro ao registrar sinais: {str(e)}")
                                    st.error("Ocorreu um erro ao registrar seus sinais vitais. Por favor, tente novamente.")
                    elif not valido and "intervalo" in msg:
                        # Só mostra aviso, mas não bloqueia
                        st.warning(f"Pressão arterial: {msg}")
            
            with tab2:
                # Busca registros dos últimos 7 dias
                df_registros = obter_registros_sinais(paciente_id, dias=7)
                
                if not df_registros.empty:
                    # Mostra gráficos de evolução
                    plotar_evolucao_sinais(df_registros)
                    
                    # Mostra tabela com registros
                    mostrar_ultimos_registros(df_registros)
                else:
                    st.info("Você ainda não tem registros. Comece agora mesmo a monitorar seus sinais vitais!")

elif opcao == "Relatórios":
    st.header("📊 Relatórios e Análises")
    
    if perfil in ["Administrador", "Profissional de Saúde"]:
        # Seleção do paciente
        pacientes = buscar_todos_pacientes() if perfil == "Administrador" else buscar_pacientes_do_profissional(st.session_state.usuario[0])
        if not pacientes:
            st.info("Nenhum paciente cadastrado ainda.")
        else:
            paciente_selecionado = st.selectbox(
                "Selecione um paciente",
                [f"{nome} (ID:{pid})" for pid, nome in pacientes]
            )
            paciente_id = int(paciente_selecionado.split("ID:")[1][:-1])
            
            # Seleção do período
            col1, col2 = st.columns([2, 1])
            with col1:
                data_inicio = st.date_input(
                    "Data inicial",
                    value=datetime.now().date() - timedelta(days=30),
                    max_value=datetime.now().date()
                )
            with col2:
                data_fim = st.date_input(
                    "Data final",
                    value=datetime.now().date(),
                    max_value=datetime.now().date()
                )
            
            if data_inicio > data_fim:
                st.error("A data inicial deve ser anterior à data final!")
            else:
                # Busca dados do período
                dias = (data_fim - data_inicio).days + 1
                df = obter_registros_sinais(paciente_id, dias)
                
                if not df.empty:
                    # Tabs para diferentes análises
                    tab1, tab2, tab3 = st.tabs(["📈 Tendências", "📊 Estatísticas", "📋 Dados Brutos"])
                    
                    with tab1:
                        st.subheader("📈 Análise de Tendências")
                        plotar_evolucao_sinais(df)
                        
                        # Análise de tendências
                        st.subheader("📉 Variações Significativas")
                        col1, col2 = st.columns(2)
                        with col1:
                            # Variação de temperatura
                            temp_var = df['Temperatura'].max() - df['Temperatura'].min()
                            st.metric(
                                "Variação de Temperatura",
                                f"{temp_var:.1f}°C",
                                delta=f"{(df['Temperatura'].iloc[-1] - df['Temperatura'].iloc[0]):.1f}°C"
                            )
                            
                            # Variação de frequência
                            freq_var = df['Frequência'].max() - df['Frequência'].min()
                            st.metric(
                                "Variação de Frequência",
                                f"{freq_var:.0f} bpm",
                                delta=f"{(df['Frequência'].iloc[-1] - df['Frequência'].iloc[0]):.0f} bpm"
                            )
                        
                        with col2:
                            # Variação de saturação
                            sat_var = df['Saturação'].max() - df['Saturação'].min()
                            st.metric(
                                "Variação de Saturação",
                                f"{sat_var:.0f}%",
                                delta=f"{(df['Saturação'].iloc[-1] - df['Saturação'].iloc[0]):.0f}%"
                            )
                            
                            # Total de registros
                            st.metric(
                                "Registros no Período",
                                len(df),
                                f"{len(df)/dias:.1f} registros/dia"
                            )
                    
                    with tab2:
                        st.subheader("📊 Análise Estatística")
                        
                        # Estatísticas descritivas
                        st.write("#### 📈 Estatísticas Gerais")
                        estatisticas = df.describe()
                        st.dataframe(estatisticas, use_container_width=True)
                        
                        # Contagem de alertas
                        st.write("#### ⚠️ Análise de Alertas")
                        alertas_temp = len(df[
                            (df['Temperatura'] < TEMP_MIN_ALERTA) | 
                            (df['Temperatura'] > TEMP_MAX_ALERTA)
                        ])
                        alertas_freq = len(df[
                            (df['Frequência'] < FREQ_MIN_ALERTA) | 
                            (df['Frequência'] > FREQ_MAX_ALERTA)
                        ])
                        alertas_sat = len(df[df['Saturação'] < SAT_MIN_ALERTA])
                        
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Alertas de Temperatura", alertas_temp)
                        with col2:
                            st.metric("Alertas de Frequência", alertas_freq)
                        with col3:
                            st.metric("Alertas de Saturação", alertas_sat)
                    
                    with tab3:
                        st.subheader("📋 Dados do Período")
                        st.dataframe(df, use_container_width=True)
                        
                        # Opção para download
                        csv = df.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            "⬇️ Download dos dados",
                            csv,
                            f"relatorio_{paciente_id}_{data_inicio}_{data_fim}.csv",
                            "text/csv",
                            key='download-csv'
                        )
                else:
                    st.info("Nenhum registro encontrado para o período selecionado.")
    
    elif perfil == "Paciente":
        # Busca ID do paciente
        usuario_id = st.session_state.usuario[0]
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM pacientes WHERE usuario_id = %s", (usuario_id,))
        resultado = cursor.fetchone()
        conn.close()
        
        if not resultado:
            st.info("Peça para o profissional responsável fazer seu cadastro!")
        else:
            paciente_id = resultado[0]
            
            # Seleção do período
            periodo = st.selectbox(
                "Período de análise",
                ["Últimos 7 dias", "Últimos 30 dias", "Todo histórico"]
            )
            dias = 7 if periodo == "Últimos 7 dias" else 30 if periodo == "Últimos 30 dias" else 3650
            
            # Busca dados
            df = obter_registros_sinais(paciente_id, dias)
            
            if not df.empty:
                # Mostra gráficos
                plotar_evolucao_sinais(df)
                
                # Estatísticas simples
                st.subheader("📊 Resumo do Período")
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Temperatura Média", f"{df['Temperatura'].mean():.1f}°C")
                with col2:
                    st.metric("Freq. Cardíaca Média", f"{df['Frequência'].mean():.0f} bpm")
                with col3:
                    st.metric("Saturação Média", f"{df['Saturação'].mean():.0f}%")
                with col4:
                    st.metric("Total Registros", len(df))
                
                # Tabela de registros
                st.subheader("📋 Seus Registros")
                st.dataframe(df, use_container_width=True)
                
                # Download dos dados
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    "⬇️ Download dos seus dados",
                    csv,
                    f"meus_registros_{periodo.lower().replace(' ', '_')}.csv",
                    "text/csv",
                    key='download-csv'
                )
            else:
                st.info("Você ainda não tem registros no período selecionado. Comece a monitorar seus sinais vitais!")

elif opcao == "Dashboard":
    st.header("🏥 Painel do Administrador")
    
    col1, col2 = st.columns(2)
    with col1:
        st.info("""
        Sistema de Telemonitoramento CEUB
        
        Versão: 1.0.0
        Última atualização: 2024
        """)
    
    with col2:
        st.success("""
        ✅ Sistema em operação
        
        Monitorando:
        - Sinais vitais
        - Alertas automáticos
        - Notificações por email
        """)

elif opcao == "Sair":
    st.session_state.usuario = None
    st.rerun()
