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
import io
import zipfile
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

try:
    from ultralytics import YOLO
    YOLO_DISPONIVEL = True
except ImportError:
    YOLO_DISPONIVEL = False

# ==============================================================================
# CONFIGURAÇÕES DA PÁGINA (WIDE) E CSS CUSTOMIZADO
# ==============================================================================
st.set_page_config(
    page_title="Recorte de Etiquetas EMBRATEL",
    page_icon="✂️",
    layout="wide"
)

st.markdown("""
    <style>
    header {visibility: hidden;}
    footer {visibility: hidden;}
    #MainMenu {visibility: hidden;}
    
    .stApp {
        background-color: #1c1c1e;
        color: #ffffff;
    }
    
    div[data-baseweb="input"] {
        background-color: #2c2c2e !important;
        border-color: #3a3a3c !important;
        border-radius: 8px !important;
        color: #ffffff !important;
    }
    
    .stat-card {
        background-color: #2c2c2e;
        border: 1px solid #3a3a3c;
        border-radius: 8px;
        padding: 20px;
        text-align: center;
        margin-bottom: 15px;
    }
    .stat-number {
        font-size: 32px;
        font-weight: bold;
        color: #ff9500;
        margin-bottom: 5px;
    }
    .stat-label {
        font-size: 11px;
        color: #a1a1a6;
        letter-spacing: 1px;
        text-transform: uppercase;
        font-weight: 600;
    }
    
    .stButton > button, .stDownloadButton > button {
        width: 100%;
        background-color: #ff9500;
        color: #ffffff;
        border: none;
        border-radius: 8px;
        padding: 12px 16px;
        font-weight: bold;
        transition: all 0.3s ease;
    }
    .stButton > button:hover, .stDownloadButton > button:hover {
        background-color: #e08300;
        color: #ffffff;
    }
    
    .footer-text {
        text-align: center;
        color: #8e8e93;
        font-size: 13px;
        margin-top: 50px;
        padding-top: 20px;
        border-top: 1px solid #2c2c2e;
    }
    </style>
""", unsafe_allow_html=True)

ARQUIVO_USUARIOS = "usuarios.json"
ARQUIVO_SMTP = "config_smtp.json"
URL_APLICACAO = "https://recorteetiquetas.streamlit.app/"

if os.name == 'nt':
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# ==============================================================================
# FUNÇÕES HELPER & SMTP
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
    usuarios = carregar_json(ARQUIVO_USUARIOS, {})
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
    assunto = "Código de Verificação - Recorte de Etiquetas"
    corpo = f"""
    <div style="font-family: Arial, sans-serif; background-color: #2c2c2e; color: #ffffff; padding: 20px; border-radius: 8px;">
        <h2 style="color: #ff9500;">Código de Verificação</h2>
        <p>Seu código para validar o e-mail no Recorte de Etiquetas é:</p>
        <div style="background-color: #1c1c1e; font-size: 32px; font-weight: bold; color: #ff9500; padding: 15px; text-align: center; letter-spacing: 8px; border-radius: 8px; width: 200px;">
            {codigo}
        </div>
    </div>
    """
    return enviar_email_smtp(email_destino, assunto, corpo)

def enviar_notificacao_aprovacao(email_destino, nome_usuario):
    assunto = "🎉 Seu Acesso Foi Aprovado - Recorte de Etiquetas"
    corpo = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #1c1c1e; color: #ffffff; padding: 30px;">
        <div style="background-color: #2c2c2e; padding: 25px; border-radius: 8px; max-width: 500px; margin: auto;">
            <h2 style="color: #34c759; margin-top: 0;">Conta Aprovada!</h2>
            <p>Olá, <b>{nome_usuario}</b>!</p>
            <p>Sua solicitação de cadastro foi aprovada pelo Administrador. Clique no link abaixo para acessar:</p>
            <p style="margin: 25px 0;">
                <a href="{URL_APLICACAO}" target="_blank" style="background-color: #ff9500; color: #ffffff; padding: 12px 20px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">
                    🚀 Acessar Sistema de Etiquetas
                </a>
            </p>
        </div>
    </body>
    </html>
    """
    return enviar_email_smtp(email_destino, assunto, corpo)

def converter_imagem_para_bytes(img_rgb):
    img_bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
    is_success, buffer = cv2.imencode(".png", img_bgr)
    if is_success:
        return buffer.tobytes()
    return None

# ==============================================================================
# ALGORITMO DE DETECÇÃO DE ETIQUETA
# ==============================================================================
def extrair_candidatos_etiqueta(imagem_bytes):
    image_np = np.frombuffer(imagem_bytes, np.uint8)
    img_bgr = cv2.imdecode(image_np, cv2.IMREAD_COLOR)
    if img_bgr is None:
        return []

    h_orig, w_orig = img_bgr.shape[:2]
    candidatos = []

    # Método A: Detector de Código de Barras OpenCV
    try:
        detector = None
        if hasattr(cv2, 'barcode') and hasattr(cv2.barcode, 'BarcodeDetector'):
            detector = cv2.barcode.BarcodeDetector()
        elif hasattr(cv2, 'BarcodeDetector'):
            detector = cv2.BarcodeDetector()

        if detector is not None:
            ok, _, _, points = detector.detectAndDecode(img_bgr)
            if ok and points is not None:
                for pts in points:
                    pts = pts.astype(int)
                    x_min, y_min = np.min(pts, axis=0)
                    x_max, y_max = np.max(pts, axis=0)
                    
                    pad_w = int((x_max - x_min) * 0.30)
                    pad_h = int((y_max - y_min) * 1.50)
                    
                    x1, y1 = max(0, x_min - pad_w), max(0, y_min - pad_h)
                    x2, y2 = min(w_orig, x_max + pad_w), min(h_orig, y_max + pad_h)
                    
                    crop = img_bgr[y1:y2, x1:x2]
                    if crop.size > 0:
                        candidatos.append({
                            "imagem": cv2.cvtColor(crop, cv2.COLOR_BGR2RGB),
                            "confianca": "alta"
                        })
    except Exception:
        pass

    # Método B: Análise Morfológica em Grayscale
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (21, 5))
    grad = cv2.morphologyEx(gray, cv2.MORPH_GRADIENT, kernel)
    _, thresh = cv2.threshold(grad, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        aspect_ratio = float(w) / max(h, 1)
        area = w * h
        
        if aspect_ratio >= 1.8 and area > (w_orig * h_orig * 0.005):
            x1, y1 = max(0, x - 12), max(0, y - 12)
            x2, y2 = min(w_orig, x + w + 12), min(h_orig, y + h + 12)
            
            crop = img_bgr[y1:y2, x1:x2]
            if crop.size > 0:
                candidatos.append({
                    "imagem": cv2.cvtColor(crop, cv2.COLOR_BGR2RGB),
                    "confianca": "media"
                })

    return candidatos

# ==============================================================================
# AUTENTICAÇÃO
# ==============================================================================
if "usuario_logado" not in st.session_state:
    st.session_state.usuario_logado = None
if "etapa_cadastro" not in st.session_state:
    st.session_state.etapa_cadastro = "formulario"
if "email_em_verificacao" not in st.session_state:
    st.session_state.email_em_verificacao = None
if "selecoes_usuario" not in st.session_state:
    st.session_state.selecoes_usuario = {}

def renderizar_autenticacao():
    col_v1, col_center, col_v2 = st.columns([1, 2, 1])
    with col_center:
        st.markdown("""
            <div style="text-align: center; margin-bottom: 30px; margin-top: 40px;">
                <h1 style="font-size: 36px; font-weight: bold; margin: 0;">LOGO &nbsp;&nbsp;&nbsp;&nbsp; Recorte de Etiquetas</h1>
                <p style="color: #a1a1a6; font-size: 14px; margin-top: 10px;">Acesse para recortar e baixar etiquetas Embratel / Códigos de Barras</p>
            </div>
        """, unsafe_allow_html=True)

        aba_login, aba_esqueci, aba_cadastro = st.tabs(["🔑 Entrar", "🔒 Esqueci a Senha", "📝 Criar Conta"])
        
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
                        if u["senha"] == senha_h and u.get("status") == "ativo":
                            st.session_state.usuario_logado = {"email": usuario, "nome": u["nome"], "cargo": u["cargo"]}
                            st.rerun()
                        else:
                            st.error("Credenciais inválidas ou cadastro pendente de aprovação.")
                    else:
                        st.error("Usuário não encontrado.")

        with aba_cadastro:
            if st.session_state.etapa_cadastro == "formulario":
                with st.form("form_criar"):
                    nome = st.text_input("Nome Completo")
                    email = st.text_input("E-mail Corporativo").strip().lower()
                    senha = st.text_input("Crie uma Senha", type="password")
                    btn_cadastrar = st.form_submit_button("Enviar e Enviar Código")
                    
                    if btn_cadastrar:
                        usuarios = carregar_usuarios()
                        codigo = gerar_codigo_verificacao()
                        usuarios[email] = {
                            "nome": nome, "senha": gerar_hash_senha(senha), "cargo": "Operador",
                            "status": "pendente_email", "codigo_verificacao": codigo, "email_verificado": False
                        }
                        salvar_usuarios(usuarios)
                        ok, msg = enviar_codigo_email(email, codigo)
                        if ok:
                            st.session_state.email_em_verificacao = email
                            st.session_state.etapa_cadastro = "validar_codigo"
                            st.rerun()

            elif st.session_state.etapa_cadastro == "validar_codigo":
                with st.form("form_codigo"):
                    codigo_in = st.text_input("Código de 6 Dígitos", max_chars=6).strip()
                    if st.form_submit_button("Confirmar Código"):
                        usuarios = carregar_usuarios()
                        email_atual = st.session_state.email_em_verificacao
                        if codigo_in == usuarios.get(email_atual, {}).get("codigo_verificacao"):
                            usuarios[email_atual]["email_verificado"] = True
                            usuarios[email_atual]["status"] = "pendente_aprovação_admin"
                            salvar_usuarios(usuarios)
                            st.success("✅ E-mail verificado! Aguarde a aprovação do Admin.")
                            st.session_state.etapa_cadastro = "formulario"
                            st.rerun()

# ==============================================================================
# FERRAMENTA DE RECORTE
# ==============================================================================
def renderizar_ferramenta_recorte():
    col_upload, col_painel = st.columns([2.2, 1])
    
    total_fotos = 0
    recortes_finais = []
    
    with col_upload:
        arquivos = st.file_uploader(
            "📁 Envie fotos contendo etiquetas (Embratel / Código de Barras)", 
            type=["jpg", "png", "jpeg"], 
            accept_multiple_files=True
        )
        
        if arquivos:
            total_fotos = len(arquivos)
            st.write("---")
            
            for idx, arq in enumerate(arquivos):
                bytes_img = arq.getvalue()
                candidatos = extrair_candidatos_etiqueta(bytes_img)
                
                st.markdown(f"#### 📷 Imagem #{idx+1}: `{arq.name}`")
                
                if not candidatos:
                    st.warning("⚠️ Nenhuma etiqueta detectada automaticamente nesta imagem.")
                
                elif len(candidatos) == 1 and candidatos[0]["confianca"] == "alta":
                    img_recortada = candidatos[0]["imagem"]
                    st.image(img_recortada, width=350, caption="Etiqueta Recortada com Precisão")
                    recortes_finais.append((f"etiqueta_{idx+1}.png", converter_imagem_para_bytes(img_recortada)))
                
                else:
                    st.info("🤔 **Identificamos mais de uma opção.** Escolha a etiqueta correta abaixo:")
                    cols = st.columns(min(len(candidatos), 3))
                    
                    for c_idx, cand in enumerate(candidatos[:3]):
                        with cols[c_idx]:
                            st.image(cand["imagem"], use_container_width=True)
                            chave_btn = f"sel_{idx}_{c_idx}"
                            
                            is_selected = st.session_state.selecoes_usuario.get(idx) == c_idx
                            
                            if st.button(f"{'✅ Selecionada' if is_selected else 'Escolher Esta'}", key=chave_btn):
                                st.session_state.selecoes_usuario[idx] = c_idx
                                st.rerun()
                    
                    opcao_escolhida = st.session_state.selecoes_usuario.get(idx)
                    if opcao_escolhida is not None and opcao_escolhida < len(candidatos):
                        img_sel = candidatos[opcao_escolhida]["imagem"]
                        recortes_finais.append((f"etiqueta_{idx+1}_opcao_{opcao_escolhida+1}.png", converter_imagem_para_bytes(img_sel)))
                
                st.write("---")

    with col_painel:
        st.markdown("### 📊 Painel do Lote")
        
        st.markdown(f"""
            <div class="stat-card">
                <div class="stat-number">{total_fotos}</div>
                <div class="stat-label">Fotos Processadas</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{len(recortes_finais)}</div>
                <div class="stat-label">Etiquetas Confirmadas</div>
            </div>
        """, unsafe_allow_html=True)

        if recortes_finais:
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for nome_arq, dados_bytes in recortes_finais:
                    if dados_bytes:
                        zip_file.writestr(nome_arq, dados_bytes)
            
            st.markdown("#### 📦 Download Final")
            st.download_button(
                label=f"⬇️ BAIXAR {len(recortes_finais)} ETIQUETAS (.ZIP)",
                data=zip_buffer.getvalue(),
                file_name="etiquetas_recortadas.zip",
                mime="application/zip",
                key="btn_download_zip_lote"
            )

# ==============================================================================
# PAINEL DO ADMINISTRADOR (COM BOTÕES DE REFRESH/ATUALIZAÇÃO)
# ==============================================================================
def renderizar_painel_admin():
    st.markdown("### ⚙️ Painel do Administrador")
    t1, t2, t3 = st.tabs(["Aprovação de Usuários", "👥 Gerenciar Usuários", "Configuração SMTP"])
    
    with t1:
        col_titulo, col_btn = st.columns([3, 1])
        with col_titulo:
            st.markdown("#### Solicitações Pendentes")
        with col_btn:
            if st.button("🔄 Atualizar Lista", key="btn_refresh_pendentes"):
                st.rerun()

        usuarios = carregar_usuarios()
        pendentes = {e: d for e, d in usuarios.items() if d.get("status") == "pendente_aprovação_admin"}
        
        if not pendentes:
            st.info("Nenhuma conta pendente de aprovação no momento.")
        else:
            for email, d in pendentes.items():
                with st.container():
                    col_info, col_acao = st.columns([3, 1])
                    with col_info:
                        st.markdown(f"**Nome:** {d['nome']}  \n**E-mail:** `{email}`")
                    with col_acao:
                        if st.button("✅ Aprovar Acesso", key=f"ap_{email}"):
                            usuarios[email]["status"] = "ativo"
                            salvar_usuarios(usuarios)
                            enviar_notificacao_aprovacao(email, d['nome'])
                            st.success(f"Acesso aprovado para {d['nome']}!")
                            st.rerun()
                st.write("---")

    with t2:
        col_t2_head, col_t2_btn = st.columns([3, 1])
        with col_t2_head:
            st.markdown("#### Todos os Usuários")
        with col_t2_btn:
            if st.button("🔄 Atualizar Tabela", key="btn_refresh_tabela"):
                st.rerun()
                
        usuarios = carregar_usuarios()
        dados_tabela = [{"Nome": u.get("nome"), "E-mail": e, "Cargo": u.get("cargo"), "Status": u.get("status")} for e, u in usuarios.items()]
        st.dataframe(dados_tabela, use_container_width=True)

    with t3:
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
# MAIN
# ==============================================================================
def main():
    if not st.session_state.usuario_logado:
        renderizar_autenticacao()
    else:
        c_head1, c_head2 = st.columns([1, 4])
        with c_head1:
            st.markdown("<h1 style='font-size: 38px; margin: 0;'>LOGO</h1>", unsafe_allow_html=True)
        with c_head2:
            st.markdown("""
                <h1 style='font-size: 32px; margin: 0;'>Recorte de Etiquetas</h1>
                <p style='color: #a1a1a6; margin-top: 5px;'>Identificador e extrator inteligente de etiquetas.</p>
            """, unsafe_allow_html=True)

        cargo = st.session_state.usuario_logado["cargo"]
        if cargo == "Administrador":
            tab_recorte, tab_admin = st.tabs(["✂️ Ferramenta de Recorte", "👑 Painel do Administrador"])
            with tab_recorte:
                renderizar_ferramenta_recorte()
            with tab_admin:
                renderizar_painel_admin()
        else:
            renderizar_ferramenta_recorte()

        if st.button("🚪 Sair do Sistema"):
            st.session_state.usuario_logado = None
            st.rerun()

    st.markdown("""
        <div class="footer-text">
            Desenvolvido por <b>Diego Costa</b>
        </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
