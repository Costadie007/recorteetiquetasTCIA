import gc
import json
import os
import platform
import smtplib
import tempfile
import zipfile
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import cv2
import numpy as np
import pytesseract
import streamlit as st
from ultralytics import YOLO

# --- CONFIGURAÇÃO DE ADMINISTRADOR ---
USUARIO_ADMIN = "diego.costa"

# --- PALETA DE CORES PERSONALIZADA ---
COR_GRAFITE = "#2A2927"
COR_LARANJA = "#F39200"
COR_FUNDO_CARD = "#333230"
COR_TEXTO = "#FFFFFF"

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Recorte de Etiquetas", page_icon="✂️", layout="wide"
)

# --- ESTILIZAÇÃO CSS ---
st.markdown(
    f"""
    <style>
    [data-testid="stToolbar"], [data-testid="stHeader"], header, #MainMenu, .stApp > header {{
        display: none !important;
        visibility: hidden !important;
        height: 0px !important;
    }}
    footer {{ display: none !important; }}
    [data-testid="stStatusWidget"], [data-testid="stConnectionStatus"], .viewerBadge_container__1QSob {{
        display: none !important;
    }}
    .stApp {{ background-color: {COR_GRAFITE}; color: {COR_TEXTO}; font-family: 'Inter', sans-serif; }}
    div.block-container {{ padding-top: 1rem !important; padding-bottom: 2rem; max-width: 92%; }}
    h1, h2, h3, h4, h5, h6, p, span, label {{ color: {COR_TEXTO} !important; }}
    .metric-card {{
        background-color: {COR_FUNDO_CARD};
        border: 1px solid #444340;
        border-radius: 10px;
        padding: 12px 8px;
        text-align: center;
    }}
    .metric-value {{ font-size: 26px; font-weight: bold; color: {COR_LARANJA} !important; }}
    .metric-label {{ font-size: 11px; color: #aaaaaa !important; }}
    .stButton>button {{
        background: linear-gradient(90deg, {COR_LARANJA} 0%, #d88100 100%) !important;
        color: #FFFFFF !important;
        border-radius: 8px !important;
        font-weight: bold !important;
        border: none !important;
    }}
    .stDownloadButton>button {{
        background-color: {COR_LARANJA} !important;
        color: #FFFFFF !important;
        border-radius: 8px !important;
        font-weight: bold !important;
        border: none !important;
        width: 100% !important;
    }}
    </style>
""",
    unsafe_allow_html=True,
)

# --- GERENCIAMENTO DE USUÁRIOS E CONFIGURAÇÕES ---
ARQUIVO_USUARIOS = "usuarios.json"
ARQUIVO_CONFIG = "config_smtp.json"


def carregar_config_smtp():
    if os.path.exists(ARQUIVO_CONFIG):
        try:
            with open(ARQUIVO_CONFIG, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "servidor": "smtp.gmail.com",
        "porta": 587,
        "email_remetente": "",
        "senha_app": "",
        "url_sistema": "http://localhost:8501",
    }


def enviar_notificacao_email(assunto, mensagem_html, email_destino):
    cfg = carregar_config_smtp()
    remetente = cfg.get("email_remetente")
    senha = cfg.get("senha_app")

    if not remetente or not senha:
        return False, "Configuração de SMTP ausente."

    try:
        msg = MIMEMultipart()
        msg["From"] = remetente
        msg["To"] = email_destino
        msg["Subject"] = assunto
        msg.attach(MIMEText(mensagem_html, "html"))

        server = smtplib.SMTP(
            cfg.get("servidor", "smtp.gmail.com"), int(cfg.get("porta", 587))
        )
        server.ehlo()
        server.starttls()
        server.login(remetente, senha)
        server.sendmail(remetente, email_destino, msg.as_string())
        server.quit()
        return True, "E-mail enviado!"
    except Exception as e:
        return False, str(e)


def carregar_usuarios():
    if not os.path.exists(ARQUIVO_USUARIOS):
        dados_padrao = {
            USUARIO_ADMIN: {
                "senha": "admin123",
                "email": "admin@empresa.com",
                "status": "aprovado",
                "role": "admin",
            }
        }
        with open(ARQUIVO_USUARIOS, "w") as f:
            json.dump(dados_padrao, f, indent=4)
        return dados_padrao
    try:
        with open(ARQUIVO_USUARIOS, "r") as f:
            return json.load(f)
    except Exception:
        return {}


# ESTADO DA SESSÃO
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
if "usuario_logado" not in st.session_state:
    st.session_state.usuario_logado = ""
if "caminho_zip_temp" not in st.session_state:
    st.session_state.caminho_zip_temp = None

# --- TELA DE LOGIN ---
if not st.session_state.autenticado:
    col1, col2, col3 = st.columns([1, 1.8, 1])
    with col2:
        st.markdown("## ✂️ Login - Sistema de Recorte")
        usuarios_cadastrados = carregar_usuarios()
        with st.form("form_login"):
            usuario_input = st.text_input("Usuário").strip().lower()
            senha_input = st.text_input("Senha", type="password")
            if st.form_submit_button("Entrar", use_container_width=True):
                if (
                    usuario_input in usuarios_cadastrados
                    and usuarios_cadastrados[usuario_input]["senha"] == senha_input
                ):
                    st.session_state.autenticado = True
                    st.session_state.usuario_logado = usuario_input
                    st.rerun()
                else:
                    st.error("Usuário ou senha inválidos.")
    st.stop()

# --- NAVEGAÇÃO LATERAL ---
with st.sidebar:
    st.markdown(f"👤 **Usuário:** `{st.session_state.usuario_logado}`")
    if st.button("🚪 Sair", use_container_width=True):
        st.session_state.autenticado = False
        st.session_state.usuario_logado = ""
        st.rerun()

# --- CARREGAMENTO DO MODELO YOLO ---
@st.cache_resource
def carregar_modelo():
    return YOLO("best.pt")

try:
    model = carregar_modelo()
except Exception as e:
    st.error(f"Erro ao carregar modelo YOLO: {e}")
    st.stop()

if platform.system() == "Windows":
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

TERMOS_CHAVE = ["claro", "embratel", "sgp", "ctrl", "patrimonio", "propriedade"]

# --- INTERFACE PRINCIPAL ---
st.title("✂️ Recorte de Etiquetas em Lote")

col_upload, col_stats = st.columns([2.0, 1.0])

with col_upload:
    arquivos_enviados = st.file_uploader(
        "📂 Envie suas imagens", type=["jpg", "jpeg", "png"], accept_multiple_files=True
    )

with col_stats:
    tot_enviadas = len(arquivos_enviados) if arquivos_enviados else 0
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-value">{tot_enviadas}</div>
            <div class="metric-label">FOTOS NO LOTE</div>
        </div>
    """,
        unsafe_allow_html=True,
    )

if arquivos_enviados:
    if st.button("🚀 INICIAR PROCESSAMENTO", use_container_width=True):
        
        # Cria diretório temporário no disco para salvar os recortes sem lotar a RAM
        dir_temp = tempfile.mkdtemp()
        caminho_zip = os.path.join(dir_temp, "recortes_etiquetas.zip")
        
        barra = st.progress(0)
        status = st.empty()
        total_fotos = len(arquivos_enviados)
        recortes_gerados = 0

        with zipfile.ZipFile(caminho_zip, "w", zipfile.ZIP_DEFLATED) as zip_out:
            for idx, arquivo in enumerate(arquivos_enviados):
                status.write(f"Analisando ({idx+1}/{total_fotos}): **{arquivo.name}**")

                # Decodifica imagem
                file_bytes = np.frombuffer(arquivo.read(), np.uint8)
                img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
                del file_bytes  # Libera memória imediatamente
                
                if img is None:
                    continue

                h_img, w_img, _ = img.shape
                resultados = model(img, conf=0.35, verbose=False)
                candidatas = []

                for r in resultados:
                    for box in r.boxes:
                        x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().numpy())
                        candidatas.append((x1, y1, x2, y2))

                if candidatas:
                    # Pega a primeira detecção válida ou ajusta lógica
                    x1, y1, x2, y2 = candidatas[0]
                    y1, y2 = max(0, y1 - 10), min(h_img, y2 + 10)
                    x1, x2 = max(0, x1 - 10), min(w_img, x2 + 10)
                    
                    recorte = img[y1:y2, x1:x2]
                    _, buffer = cv2.imencode(".png", recorte)
                    
                    # Salva direto no arquivo ZIP no disco
                    zip_out.writestr(f"recorte_{arquivo.name}", buffer.tobytes())
                    recortes_gerados += 1
                    
                    del recorte, buffer

                del img
                gc.collect()  # Coletor de lixo força liberação de RAM do Python
                barra.progress((idx + 1) / total_fotos)

        st.session_state.caminho_zip_temp = caminho_zip
        status.success(f"✅ Processamento finalizado! {recortes_gerados} recortes salvos.")

# --- BOTÃO DE DOWNLOAD ---
if st.session_state.caminho_zip_temp and os.path.exists(st.session_state.caminho_zip_temp):
    st.markdown("---")
    with open(st.session_state.caminho_zip_temp, "rb") as f:
        st.download_button(
            label="📦 BAIXAR TODOS OS RECORTES (.ZIP)",
            data=f,
            file_name="etiquetas_recortadas.zip",
            mime="application/zip",
            use_container_width=True,
        )
