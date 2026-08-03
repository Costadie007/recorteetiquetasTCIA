import streamlit as st
import cv2
import numpy as np
import pytesseract
import json
import os
import smtplib
import random
import string
import hashlib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Importação condicional do Ultralytics (YOLO)
try:
    from ultralytics import YOLO
    YOLO_DISPONIVEL = True
except ImportError:
    YOLO_DISPONIVEL = False

# ==============================================================================
# CONFIGURAÇÕES INICIAIS E ESTILIZAÇÃO (LAYOUT GRAFITE & LARANJA)
# ==============================================================================
st.set_page_config(
    page_title="Sistema de Recorte de Etiquetas",
    page_icon="🏷️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Injeção de CSS para ocultar barras do Streamlit e aplicar o tema da empresa
st.markdown("""
    <style>
    /* Ocultar barra superior e marca d'água */
    header {visibility: hidden;}
    footer {visibility: hidden;}
    #MainMenu {visibility: hidden;}
    
    /* Tema visual Grafite & Laranja */
    .stApp {
        background-color: #1e1e24;
        color: #e0e0e0;
    }
    .stButton>button {
        background-color: #ff6600;
        color: #ffffff;
        border: none;
        font-weight: bold;
        border-radius: 5px;
        padding: 0.5rem 1rem;
    }
    .stButton>button:hover {
        background-color: #e05500;
        color: #ffffff;
    }
    div[data-baseweb="input"] {
        background-color: #2b2b36;
        color: #ffffff;
    }
    .css-card {
        background-color: #2b2b36;
        padding: 20px;
        border-radius: 10px;
        border-left: 5px solid #ff6600;
        margin-bottom: 15px;
    }
    </style>
""", unsafe_allow_html=True)

# Caminhos dos arquivos de configuração locais
ARQUIVO_USUARIOS = "usuarios.json"
ARQUIVO_SMTP = "config_smtp.json"
MODELO_YOLO_PATH = "best.pt"

# Configuração do Tesseract OCR (Ajuste o caminho se necessário)
if os.name == 'nt':
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# ==============================================================================
# FUNÇÕES AUXILIARES E PERSISTÊNCIA (JSON & CRIPTOGRAFIA)
# ==============================================================================
def gerar_hash_senha(senha):
    """Gera um hash SHA-256 da senha do usuário."""
    return hashlib.sha256(senha.encode('utf-8')).hexdigest()

def carregar_json(caminho, padrao):
    if os.path.exists(caminho):
        try:
            with open(caminho, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return padrao
    return padrao

def salvar_json(caminho, dados):
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=4, ensure_ascii=False)

def carregar_usuarios():
    # Cria conta de admin padrão caso o arquivo não exista
    usuarios_padrao = {
        "admin@empresa.com.br": {
            "nome": "Administrador Principal",
            "senha": gerar_hash_senha("admin123"),
            "cargo": "Administrador",
            "status": "ativo",
            "email_verificado": True
        }
    }
    return carregar_json(ARQUIVO_USUARIOS, usuarios_padrao)

def salvar_usuarios(usuarios):
    salvar_json(ARQUIVO_USUARIOS, usuarios)

def carregar_config_smtp():
    return carregar_json(ARQUIVO_SMTP, {
        "servidor": "",
        "porta": 587,
        "usuario": "",
        "senha": "",
        "usar_tls": True
    })

def salvar_config_smtp(config):
    salvar_json(ARQUIVO_SMTP, config)

def gerar_codigo_verificacao():
    return ''.join(random.choices(string.digits, k=6))

# ==============================================================================
# SERVIÇO DE DISPARO DE E-MAILS (SMTP)
# ==============================================================================
def enviar_email_smtp(destino, assunto, corpo_html):
    config = carregar_config_smtp()
    if not config.get("servidor") or not config.get("usuario"):
        return False, "Configurações SMTP não foram personalizadas pelo Administrador."
    
    try:
        msg = MIMEMultipart()
        msg['From'] = config["usuario"]
        msg['To'] = destino
        msg['Subject'] = assunto
        msg.attach(MIMEText(corpo_html, 'html'))
        
        server = smtplib.SMTP(config["servidor"], int(config["porta"]))
        if config.get("usar_tls", True):
            server.starttls()
        server.login(config["usuario"], config["senha"])
        server.sendmail(config["usuario"], destino, msg.as_string())
        server.quit()
        return True, "E-mail enviado com sucesso!"
    except Exception as e:
        return False, f"Erro ao enviar e-mail: {str(e)}"

def enviar_codigo_email(email_destino, codigo):
    assunto = "Código de Verificação de E-mail - Sistema de Etiquetas"
    corpo = f"""
    <div style="font-family: Arial, sans-serif; background-color: #1e1e24; color: #ffffff; padding: 20px; border-radius: 8px;">
        <h2 style="color: #ff6600;">Verificação de E-mail</h2>
        <p>Seu código de verificação para prosseguir com o cadastro no sistema é:</p>
        <div style="background-color: #2b2b36; font-size: 32px; font-weight: bold; color: #ff6600; padding: 15px; text-align: center; letter-spacing: 8px; border-radius: 5px; width: 200px;">
            {codigo}
        </div>
        <p style="margin-top: 20px; font-size: 12px; color: #aaaaaa;">Após digitar este código, sua solicitação será enviada para avaliação do Administrador.</p>
    </div>
    """
    return enviar_email_smtp(email_destino, assunto, corpo)

# ==============================================================================
# PROCESSAMENTO DE IMAGENS E VISÃO COMPUTACIONAL (YOLO + OCR)
# ==============================================================================
@st.cache_resource
def carregar_modelo_yolo():
    if YOLO_DISPONIVEL and os.path.exists(MODELO_YOLO_PATH):
        try:
            return YOLO(MODELO_YOLO_PATH)
        except Exception:
            return None
    return None

def processar_etiqueta(imagem_bytes):
    image_np = np.frombuffer(imagem_bytes, np.uint8)
    img = cv2.imdecode(image_np, cv2.IMREAD_COLOR)
    
    modelo = carregar_modelo_yolo()
    recortes = []
    
    if modelo:
        resultados = modelo(img)
        for r in resultados:
            for box in r.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                crop = img[y1:y2, x1:x2]
                
                # Executa OCR no recorte da etiqueta
                crop_gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
                texto = pytesseract.image_to_string(crop_gray, lang='por+eng').strip()
                
                recortes.append({
                    "imagem": cv2.cvtColor(crop, cv2.COLOR_BGR2RGB),
                    "texto": texto if texto else "Nenhum texto detectado"
                })
    else:
        # Fallback: OCR na imagem inteira se o modelo YOLO não estiver carregado
        img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        texto = pytesseract.image_to_string(img_gray, lang='por+eng').strip()
        recortes.append({
            "imagem": cv2.cvtColor(img, cv2.COLOR_BGR2RGB),
            "texto": texto if texto else "Nenhum texto detectado (Sem modelo YOLO)"
        })
        
    return recortes

# ==============================================================================
# GERENCIAMENTO DE ESTADO DE SESSÃO DO STREAMLIT
# ==============================================================================
if "usuario_logado" not in st.session_state:
    st.session_state.usuario_logado = None
if "etapa_cadastro" not in st.session_state:
    st.session_state.etapa_cadastro = "formulario"
if "email_em_verificacao" not in st.session_state:
    st.session_state.email_em_verificacao = None

# ==============================================================================
# MÓDULO 1: TELAS DE AUTENTICAÇÃO E REGISTRO (LOGIN E CADASTRO DUPLO)
# ==============================================================================
def renderizar_autenticacao():
    st.title("🏷️ Sistema de Recorte e Leitura de Etiquetas")
    aba1, aba2 = st.tabs(["🔒 Entrar no Sistema", "📝 Solicitar Cadastro"])
    
    # ------------------ ABA 1: LOGIN ------------------
    with aba1:
        with st.form("form_login"):
            st.subheader("Acesso ao Sistema")
            email = st.text_input("E-mail corporativo").strip().lower()
            senha = st.text_input("Senha", type="password")
            btn_entrar = st.form_submit_button("Entrar")
            
            if btn_entrar:
                usuarios = carregar_usuarios()
                senha_hash = gerar_hash_senha(senha)
                
                if email in usuarios:
                    u = usuarios[email]
                    if u["senha"] == senha_hash:
                        if u.get("status") == "ativo":
                            st.session_state.usuario_logado = {
                                "email": email,
                                "nome": u["nome"],
                                "cargo": u["cargo"]
                            }
                            st.success(f"Bem-vindo, {u['nome']}!")
                            st.rerun()
                        elif u.get("status") == "pendente_email":
                            st.warning("Seu e-mail ainda não foi verificado. Solicitamos que faça o cadastro novamente para validar o código.")
                        elif u.get("status") == "pendente_aprovação_admin":
                            st.info("Sua conta já teve o e-mail confirmado, mas aguarda a aprovação final do Administrador.")
                    else:
                        st.error("Senha incorreta.")
                else:
                    st.error("Usuário não cadastrado.")
                    
    # ------------------ ABA 2: CADASTRO COM CÓDIGO EMAIL ------------------
    with aba2:
        if st.session_state.etapa_cadastro == "formulario":
            st.subheader("1º Passo: Preencha seus Dados")
            with st.form("form_registro"):
                nome = st.text_input("Nome Completo")
                email = st.text_input("E-mail Corporativo").strip().lower()
                senha = st.text_input("Crie uma Senha", type="password")
                cargo = st.selectbox("Cargo Solicitado", ["Operador", "Administrador"])
                btn_solicitar = st.form_submit_button("Enviar e Gerar Código de Verificação")
                
                if btn_solicitar:
                    usuarios = carregar_usuarios()
                    if not nome or not email or not senha:
                        st.warning("Por favor, preencha todos os campos.")
                    elif email in usuarios and usuarios[email].get("status") == "ativo":
                        st.error("Este e-mail já está cadastrado e ativo no sistema.")
                    else:
                        codigo = gerar_codigo_verificacao()
                        usuarios[email] = {
                            "nome": nome,
                            "senha": gerar_hash_senha(senha),
                            "cargo": cargo,
                            "status": "pendente_email",
                            "codigo_verificacao": codigo,
                            "email_verificado": False
                        }
                        salvar_usuarios(usuarios)
                        
                        sucesso, msg = enviar_codigo_email(email, codigo)
                        if sucesso:
                            st.session_state.email_em_verificacao = email
                            st.session_state.etapa_cadastro = "validar_codigo"
                            st.success("Código de verificação enviado para o seu e-mail! Insira-o abaixo.")
                            st.rerun()
                        else:
                            st.error(f"Não foi possível enviar o e-mail de verificação: {msg}")

        elif st.session_state.etapa_cadastro == "validar_codigo":
            email_atual = st.session_state.email_em_verificacao
            st.subheader("2º Passo: Confirme seu E-mail")
            st.info(f"Digite o código de 6 dígitos que enviamos para: **{email_atual}**")
            
            with st.form("form_validacao_codigo"):
                codigo_digitado = st.text_input("Código de Verificação", max_chars=6).strip()
                btn_confirmar = st.form_submit_button("Validar E-mail")
                
                if btn_confirmar:
                    usuarios = carregar_usuarios()
                    dados_u = usuarios.get(email_atual, {})
                    
                    if codigo_digitado == dados_u.get("codigo_verificacao"):
                        usuarios[email_atual]["email_verificado"] = True
                        usuarios[email_atual]["status"] = "pendente_aprovação_admin"
                        usuarios[email_atual]["codigo_verificacao"] = None
                        salvar_usuarios(usuarios)
                        
                        st.success("🎉 E-mail verificado com sucesso! Sua solicitação agora foi enviada para o Administrador aprovar o acesso.")
                        st.session_state.etapa_cadastro = "formulario"
                        st.session_state.email_em_verificacao = None
                    else:
                        st.error("Código incorreto. Verifique sua caixa de entrada ou spam e tente novamente.")

            if st.button("⬅️ Cancelar / Voltar ao Início"):
                st.session_state.etapa_cadastro = "formulario"
                st.session_state.email_em_verificacao = None
                st.rerun()

# ==============================================================================
# MÓDULO 2: PAINEL DO OPERADOR (DETECÇÃO E OCR)
# ==============================================================================
def renderizar_painel_operador():
    st.title("✂️ Painel de Leitura de Etiquetas")
    st.write(f"Conectado como: **{st.session_state.usuario_logado['nome']}** ({st.session_state.usuario_logado['cargo']})")
    
    arquivo_imagem = st.file_uploader("Envie a imagem da etiqueta (JPG/PNG)", type=["jpg", "jpeg", "png"])
    
    if arquivo_imagem:
        bytes_data = arquivo_imagem.getvalue()
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Imagem Original")
            st.image(bytes_data, use_container_width=True)
            
        with col2:
            st.subheader("Resultado do Recorte e OCR")
            with st.spinner("Processando Inteligência Computacional..."):
                resultados = processar_etiqueta(bytes_data)
                
                for i, res in enumerate(resultados):
                    st.image(res["imagem"], caption=f"Recorte #{i+1}", width=300)
                    st.text_area(f"Texto Extraído #{i+1}", value=res["texto"], height=100)
                    st.divider()

# ==============================================================================
# MÓDULO 3: PAINEL DO ADMINISTRADOR (GERENCIAMENTO & SMTP)
# ==============================================================================
def renderizar_painel_admin():
    st.title("⚙️ Painel de Administração do Sistema")
    st.write(f"Conectado como: **{st.session_state.usuario_logado['nome']}**")
    
    aba_usuarios, aba_smtp = st.tabs(["👥 Aprovação de Usuários", "📧 Configurações de E-mail (SMTP)"])
    
    # ------------------ ABA USUÁRIOS ------------------
    with aba_usuarios:
        st.subheader("Solicitações Pendentes (E-mail Confirmado)")
        usuarios = carregar_usuarios()
        
        # Filtra apenas quem confirmou o e-mail mas aguarda aprovação manual do admin
        pendentes = {
            email: dados for email, dados in usuarios.items()
            if dados.get("status") == "pendente_aprovação_admin" and dados.get("email_verificado") == True
        }
        
        if not pendentes:
            st.info("Nenhuma solicitação pendente no momento.")
        else:
            for email, dados in pendentes.items():
                st.markdown(f"""
                <div class="css-card">
                    <b>Nome:</b> {dados['nome']}<br>
                    <b>E-mail:</b> {email}<br>
                    <b>Cargo Solicitado:</b> {dados['cargo']}
                </div>
                """, unsafe_allow_html=True)
                
                col1, col2 = st.columns(6)
                if col1.button("Aprovar", key=f"ap_{email}"):
                    usuarios[email]["status"] = "ativo"
                    salvar_usuarios(usuarios)
                    st.success(f"Acesso concedido a {email}!")
                    st.rerun()
                if col2.button("Rejeitar", key=f"rej_{email}"):
                    del usuarios[email]
                    salvar_usuarios(usuarios)
                    st.warning(f"Solicitação de {email} recusada.")
                    st.rerun()
                    
        st.divider()
        st.subheader("Usuários Ativos no Sistema")
        ativos = {email: dados for email, dados in usuarios.items() if dados.get("status") == "ativo"}
        for email, dados in ativos.items():
            st.write(f"• **{dados['nome']}** ({email}) — *Cargo: {dados['cargo']}*")

    # ------------------ ABA SMTP ------------------
    with aba_smtp:
        st.subheader("Servidor de Envio de E-mails (SMTP)")
        config_smtp = carregar_config_smtp()
        
        with st.form("form_smtp"):
            servidor = st.text_input("Servidor SMTP (ex: smtp.gmail.com)", value=config_smtp.get("servidor", ""))
            porta = st.number_input("Porta", value=int(config_smtp.get("porta", 587)))
            usuario = st.text_input("E-mail Remetente", value=config_smtp.get("usuario", ""))
            senha = st.text_input("Senha / Senha de App", value=config_smtp.get("senha", ""), type="password")
            usar_tls = st.checkbox("Usar TLS", value=config_smtp.get("usar_tls", True))
            
            btn_salvar_smtp = st.form_submit_button("Salvar Configurações SMTP")
            
            if btn_salvar_smtp:
                nova_config = {
                    "servidor": servidor,
                    "porta": porta,
                    "usuario": usuario,
                    "senha": senha,
                    "usar_tls": usar_tls
                }
                salvar_config_smtp(nova_config)
                st.success("Configurações SMTP salvas com sucesso!")

# ==============================================================================
# FLUXO PRINCIPAL DO SISTEMA
# ==============================================================================
def main():
    if not st.session_state.usuario_logado:
        renderizar_autenticacao()
    else:
        # Barra Lateral (Sidebar) com controle de navegação e Logout
        st.sidebar.title("Navegação")
        st.sidebar.write(f"👤 {st.session_state.usuario_logado['nome']}")
        st.sidebar.write(f"🔑 {st.session_state.usuario_logado['cargo']}")
        
        cargo = st.session_state.usuario_logado["cargo"]
        
        if cargo == "Administrador":
            opcao = st.sidebar.radio("Ir para:", ["✂️ Painel do Operador", "⚙️ Painel de Administração"])
            if opcao == "✂️ Painel do Operador":
                renderizar_painel_operador()
            else:
                renderizar_painel_admin()
        else:
            renderizar_painel_operador()
            
        st.sidebar.divider()
        if st.sidebar.button("🚪 Sair do Sistema"):
            st.session_state.usuario_logado = None
            st.rerun()

if __name__ == "__main__":
    main()
