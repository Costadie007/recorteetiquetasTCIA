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

try:
    from ultralytics import YOLO
    YOLO_DISPONIVEL = True
except ImportError:
    YOLO_DISPONIVEL = False

# ==============================================================================
# CONFIGURAÇÕES DA PÁGINA E CSS (VISUAL ORIGINAL)
# ==============================================================================
st.set_page_config(
    page_title="Sistema de Recorte",
    page_icon="✂️",
    layout="centered"
)

st.markdown("""
    <style>
    /* Ocultar elementos nativos do Streamlit */
    header {visibility: hidden;}
    footer {visibility: hidden;}
    #MainMenu {visibility: hidden;}
    
    /* Fundo geral escuro */
    .stApp {
        background-color: #1c1c1e;
        color: #ffffff;
    }
    
    /* Container do Cabeçalho */
    .header-card {
        background-color: #2c2c2e;
        border-radius: 12px;
        padding: 30px;
        text-align: center;
        margin-bottom: 25px;
        border: 1px solid #3a3a3c;
    }
    .header-title {
        font-size: 32px;
        font-weight: 700;
        color: #ffffff;
        margin: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 12px;
    }
    .header-subtitle {
        color: #a1a1a6;
        font-size: 14px;
        margin-top: 10px;
    }
    
    /* Inputs customizados */
    div[data-baseweb="input"] {
        background-color: #1c1c1e !important;
        border-color: #3a3a3c !important;
        border-radius: 8px !important;
        color: #ffffff !important;
    }
    
    /* Botões */
    .stButton > button {
        width: 100%;
        background-color: #141c2b;
        color: #ffffff;
        border: 1px solid #2c3a4e;
        border-radius: 8px;
        padding: 10px 16px;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    .stButton > button:hover {
        background-color: #1e2c44;
        border-color: #40587c;
        color: #ffffff;
    }
    </style>
""", unsafe_allow_html=True)

ARQUIVO_USUARIOS = "usuarios.json"
ARQUIVO_SMTP = "config_smtp.json"
MODELO_YOLO_PATH = "best.pt"

if os.name == 'nt':
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# ==============================================================================
# FUNÇÕES DE PERSISTÊNCIA & HELPER
# ==============================================================================
def gerar_hash_senha(senha):
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
    # Carrega os usuários do arquivo JSON se existir
    usuarios = carregar_json(ARQUIVO_USUARIOS, {})
    
    # FORÇA a existência do Admin Principal funcional (Senha: admin123)
    usuarios["admin@empresa.com.br"] = {
        "nome": "Administrador",
        "senha": gerar_hash_senha("admin123"),
        "cargo": "Administrador",
        "status": "ativo",
        "email_verificado": True
    }
    
    return usuarios

def salvar_usuarios(usuarios):
    salvar_json(ARQUIVO_USUARIOS, usuarios)

def carregar_config_smtp():
    return carregar_json(ARQUIVO_SMTP, {
        "servidor": "", "porta": 587, "usuario": "", "senha": "", "usar_tls": True
    })

def gerar_codigo_verificacao():
    return ''.join(random.choices(string.digits, k=6))

def enviar_email_smtp(destino, assunto, corpo_html):
    config = carregar_config_smtp()
    if not config.get("servidor") or not config.get("usuario"):
        return False, "Configurações de SMTP não foram preenchidas no painel Admin."
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
        return True, "Enviado"
    except Exception as e:
        return False, str(e)

def enviar_codigo_email(email_destino, codigo):
    assunto = "Código de Verificação - Sistema de Recorte"
    corpo = f"""
    <div style="font-family: Arial, sans-serif; background-color: #2c2c2e; color: #ffffff; padding: 20px; border-radius: 8px;">
        <h2 style="color: #ff6600;">Código de Verificação</h2>
        <p>Seu código para validar o e-mail no Sistema de Recorte é:</p>
        <div style="background-color: #1c1c1e; font-size: 32px; font-weight: bold; color: #ff6600; padding: 15px; text-align: center; letter-spacing: 8px; border-radius: 8px; width: 200px;">
            {codigo}
        </div>
        <p style="margin-top: 20px; font-size: 12px; color: #a1a1a6;">Insira este código na tela para submeter seu cadastro ao Administrador.</p>
    </div>
    """
    return enviar_email_smtp(email_destino, assunto, corpo)

# ==============================================================================
# VISÃO COMPUTACIONAL
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
                crop_gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
                texto = pytesseract.image_to_string(crop_gray, lang='por+eng').strip()
                recortes.append({
                    "imagem": cv2.cvtColor(crop, cv2.COLOR_BGR2RGB),
                    "texto": texto if texto else "Nenhum texto detectado"
                })
    else:
        img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        texto = pytesseract.image_to_string(img_gray, lang='por+eng').strip()
        recortes.append({
            "imagem": cv2.cvtColor(img, cv2.COLOR_BGR2RGB),
            "texto": texto if texto else "Sem modelo YOLO"
        })
    return recortes

# ==============================================================================
# CONTROLE DE SESSÃO
# ==============================================================================
if "usuario_logado" not in st.session_state:
    st.session_state.usuario_logado = None
if "etapa_cadastro" not in st.session_state:
    st.session_state.etapa_cadastro = "formulario"
if "email_em_verificacao" not in st.session_state:
    st.session_state.email_em_verificacao = None

# ==============================================================================
# INTERFACE DE AUTENTICAÇÃO
# ==============================================================================
def renderizar_autenticacao():
    st.markdown("""
        <div class="header-card">
            <div class="header-title">
                <span style="color: #ff4a5a; font-size: 38px;">✂️</span> Sistema de Recorte
            </div>
            <div class="header-subtitle">
                Acesse com sua conta, recupere seu acesso ou crie um novo cadastro
            </div>
        </div>
    """, unsafe_allow_html=True)

    aba_login, aba_esqueci, aba_cadastro = st.tabs([
        "🔑 Entrar", 
        "🔒 Esqueci a Senha", 
        "📝 Criar Conta"
    ])
    
    # --- ABA 1: ENTRAR ---
    with aba_login:
        with st.form("form_login"):
            usuario = st.text_input("Usuário").strip().lower()
            senha = st.text_input("Senha", type="password")
            btn_entrar = st.form_submit_button("Acessar Plataforma")
            
            if btn_entrar:
                usuarios = carregar_usuarios()
                senha_h = gerar_hash_senha(senha)
                
                if usuario in usuarios:
                    u = usuarios[usuario]
                    if u["senha"] == senha_h:
                        if u.get("status") == "ativo":
                            st.session_state.usuario_logado = {
                                "email": usuario, "nome": u["nome"], "cargo": u["cargo"]
                            }
                            st.success(f"Bem-vindo(a), {u['nome']}!")
                            st.rerun()
                        elif u.get("status") == "pendente_email":
                            st.warning("E-mail não verificado. Por favor, solicite o cadastro novamente para validar.")
                        elif u.get("status") == "pendente_aprovação_admin":
                            st.info("E-mail verificado! Aguardando aprovação do Administrador.")
                    else:
                        st.error("Senha incorreta.")
                else:
                    st.error("Usuário não encontrado.")

    # --- ABA 2: ESQUECI A SENHA ---
    with aba_esqueci:
        with st.form("form_esqueci"):
            email_rec = st.text_input("Digite o e-mail cadastrado").strip().lower()
            btn_recuperar = st.form_submit_button("Recuperar Acesso")
            
            if btn_recuperar:
                usuarios = carregar_usuarios()
                if email_rec in usuarios:
                    st.info("Instruções de recuperação foram enviadas para o seu e-mail.")
                else:
                    st.error("E-mail não encontrado.")

    # --- ABA 3: CRIAR CONTA ---
    with aba_cadastro:
        if st.session_state.etapa_cadastro == "formulario":
            with st.form("form_criar"):
                nome = st.text_input("Nome Completo")
                email = st.text_input("E-mail Corporativo").strip().lower()
                senha = st.text_input("Crie uma Senha", type="password")
                btn_cadastrar = st.form_submit_button("Enviar e Enviar Código")
                
                if btn_cadastrar:
                    usuarios = carregar_usuarios()
                    if not nome or not email or not senha:
                        st.warning("Preencha todos os campos obrigatórios.")
                    elif email in usuarios and usuarios[email].get("status") == "ativo":
                        st.error("E-mail já cadastrado e ativo.")
                    else:
                        codigo = gerar_codigo_verificacao()
                        usuarios[email] = {
                            "nome": nome,
                            "senha": gerar_hash_senha(senha),
                            "cargo": "Operador",
                            "status": "pendente_email",
                            "codigo_verificacao": codigo,
                            "email_verificado": False
                        }
                        salvar_usuarios(usuarios)
                        
                        ok, msg = enviar_codigo_email(email, codigo)
                        if ok:
                            st.session_state.email_em_verificacao = email
                            st.session_state.etapa_cadastro = "validar_codigo"
                            st.success("Código enviado para o seu e-mail! Insira-o no próximo passo.")
                            st.rerun()
                        else:
                            st.error(f"Erro ao enviar o e-mail: {msg}")

        elif st.session_state.etapa_cadastro == "validar_codigo":
            email_atual = st.session_state.email_em_verificacao
            st.info(f"Insira o código de 6 dígitos enviado para **{email_atual}**:")
            
            with st.form("form_codigo"):
                codigo_in = st.text_input("Código de 6 Dígitos", max_chars=6).strip()
                btn_valida = st.form_submit_button("Confirmar Código")
                
                if btn_valida:
                    usuarios = carregar_usuarios()
                    u_dados = usuarios.get(email_atual, {})
                    
                    if codigo_in == u_dados.get("codigo_verificacao"):
                        usuarios[email_atual]["email_verificado"] = True
                        usuarios[email_atual]["status"] = "pendente_aprovação_admin"
                        usuarios[email_atual]["codigo_verificacao"] = None
                        salvar_usuarios(usuarios)
                        
                        st.success("✅ E-mail confirmado! Sua conta foi enviada para validação do Administrador.")
                        st.session_state.etapa_cadastro = "formulario"
                        st.session_state.email_em_verificacao = None
                    else:
                        st.error("Código inválido. Tente novamente.")
            
            if st.button("⬅️ Voltar / Reenviar"):
                st.session_state.etapa_cadastro = "formulario"
                st.session_state.email_em_verificacao = None
                st.rerun()

# ==============================================================================
# PAINÉIS OPERADOR & ADMIN
# ==============================================================================
def renderizar_painel_operador():
    st.title("✂️ Processamento de Etiquetas")
    st.write(f"Usuário: **{st.session_state.usuario_logado['nome']}**")
    
    up = st.file_uploader("Carregar imagem da etiqueta", type=["jpg", "png", "jpeg"])
    if up:
        bytes_img = up.getvalue()
        c1, c2 = st.columns(2)
        with c1:
            st.image(bytes_img, use_container_width=True)
        with c2:
            res = processar_etiqueta(bytes_img)
            for i, r in enumerate(res):
                st.image(r["imagem"], caption=f"Recorte #{i+1}")
                st.text_area(f"Texto #{i+1}", r["texto"])

def renderizar_painel_admin():
    st.title("⚙️ Gerenciamento do Sistema")
    t1, t2 = st.tabs(["Aprovação de Usuários", "Configuração SMTP"])
    
    with t1:
        usuarios = carregar_usuarios()
        pendentes = {
            e: d for e, d in usuarios.items() 
            if d.get("status") == "pendente_aprovação_admin" and d.get("email_verificado") == True
        }
        
        if not pendentes:
            st.info("Nenhuma conta pendente de aprovação.")
        else:
            for email, d in pendentes.items():
                st.write(f"**Nome:** {d['nome']} | **E-mail:** {email}")
                novo_cargo = st.selectbox(f"Definir Cargo para {d['nome']}", ["Operador", "Administrador"], key=f"cargo_{email}")
                
                col1, col2 = st.columns(6)
                if col1.button("Aprovar", key=f"ap_{email}"):
                    usuarios[email]["cargo"] = novo_cargo
                    usuarios[email]["status"] = "ativo"
                    salvar_usuarios(usuarios)
                    st.success(f"{email} aprovado como {novo_cargo}!")
                    st.rerun()
                if col2.button("Rejeitar", key=f"rej_{email}"):
                    del usuarios[email]
                    salvar_usuarios(usuarios)
                    st.warning("Solicitação removida.")
                    st.rerun()
                    
    with t2:
        cfg = carregar_config_smtp()
        with st.form("f_smtp"):
            srv = st.text_input("Servidor SMTP", value=cfg.get("servidor", ""))
            prt = st.number_input("Porta", value=int(cfg.get("porta", 587)))
            usr = st.text_input("Usuário Remetente", value=cfg.get("usuario", ""))
            pwd = st.text_input("Senha Remetente", value=cfg.get("senha", ""), type="password")
            tls = st.checkbox("Usar TLS", value=cfg.get("usar_tls", True))
            
            if st.form_submit_button("Salvar Configurações"):
                salvar_json(ARQUIVO_SMTP, {"servidor": srv, "porta": prt, "usuario": usr, "senha": pwd, "usar_tls": tls})
                st.success("Configurações salvas!")

# ==============================================================================
# ROUTER PRINCIPAL
# ==============================================================================
def main():
    if not st.session_state.usuario_logado:
        renderizar_autenticacao()
    else:
        st.sidebar.title("Menu")
        st.sidebar.write(f"👤 {st.session_state.usuario_logado['nome']}")
        
        cargo = st.session_state.usuario_logado["cargo"]
        if cargo == "Administrador":
            opt = st.sidebar.radio("Navegar", ["Operador", "Admin"])
            if opt == "Operador":
                renderizar_painel_operador()
            else:
                renderizar_painel_admin()
        else:
            renderizar_painel_operador()
            
        if st.sidebar.button("Sair"):
            st.session_state.usuario_logado = None
            st.rerun()

if __name__ == "__main__":
    main()
