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

# Importação da Inteligência IA YOLO
try:
    from ultralytics import YOLO
    YOLO_DISPONIVEL = True
except ImportError:
    YOLO_DISPONIVEL = False

# ==============================================================================
# CONFIGURAÇÕES DA PÁGINA (WIDE) E CSS CUSTOMIZADO
# ==============================================================================
st.set_page_config(
    page_title="Recorte de Etiquetas",
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
# CARREGAMENTO DO SEU MODELO TREINADO (best.pt)
# ==============================================================================
@st.cache_resource
def carregar_modelo_yolo():
    if not YOLO_DISPONIVEL:
        return None
    try:
        if os.path.exists("best.pt"):
            return YOLO("best.pt")
        return YOLO("yolov8n.pt")
    except Exception as e:
        st.error(f"Erro ao carregar o modelo YOLO (best.pt): {e}")
        return None

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
        <p>Seu código para validar a solicitação no Recorte de Etiquetas é:</p>
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
# ALGORITMO IA (YOLOV8 - MODO AUTÔNOMO PARA GRANDES LOTES)
# ==============================================================================
def extrair_candidatos_etiqueta(imagem_bytes):
    image_np = np.frombuffer(imagem_bytes, np.uint8)
    img_bgr = cv2.imdecode(image_np, cv2.IMREAD_COLOR)
    if img_bgr is None:
        return []

    h_orig, w_orig = img_bgr.shape[:2]
    candidatos = []
    
    modelo = carregar_modelo_yolo()
    
    # 1. PROCESSAMENTO VIA MODELO TREINADO (best.pt)
    if modelo is not None:
        resultados = modelo(img_bgr, conf=0.25, iou=0.5, verbose=False)
        
        deteccoes = []
        for r in resultados:
            for box in r.boxes:
                conf = float(box.conf[0])
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                deteccoes.append((conf, x1, y1, x2, y2))
        
        deteccoes.sort(key=lambda item: item[0], reverse=True)
        
        for conf, x1, y1, x2, y2 in deteccoes:
            pad_w = int((x2 - x1) * 0.04)
            pad_h = int((y2 - y1) * 0.04)
            
            crop_x1 = max(0, x1 - pad_w)
            crop_y1 = max(0, y1 - pad_h)
            crop_x2 = min(w_orig, x2 + pad_w)
            crop_y2 = min(h_orig, y2 + pad_h)
            
            crop = img_bgr[crop_y1:crop_y2, crop_x1:crop_x2]
            if crop.size > 0:
                candidatos.append({
                    "imagem": cv2.cvtColor(crop, cv2.COLOR_BGR2RGB),
                    "confianca": conf
                })

    # 2. FALLBACK SECUNDÁRIO OPENCV
    if not candidatos:
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        gray_contrast = clahe.apply(gray)
        
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 7))
        grad = cv2.morphologyEx(gray_contrast, cv2.MORPH_GRADIENT, kernel)
        _, thresh = cv2.threshold(grad, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            aspect_ratio = float(w) / max(h, 1)
            area = w * h
            
            if 1.5 <= aspect_ratio <= 6.0 and (w_orig * h_orig * 0.008) < area < (w_orig * h_orig * 0.7):
                x1, y1 = max(0, x - 15), max(0, y - 15)
                x2, y2 = min(w_orig, x + w + 15), min(h_orig, y + h + 15)
                
                crop = img_bgr[y1:y2, x1:x2]
                if crop.size > 0:
                    candidatos.append({
                        "imagem": cv2.cvtColor(crop, cv2.COLOR_BGR2RGB),
                        "confianca": 0.5
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
if "etapa_esqueci" not in st.session_state:
    st.session_state.etapa_esqueci = "solicitar"
if "email_esqueci" not in st.session_state:
    st.session_state.email_esqueci = None
if "recortes_lote" not in st.session_state:
    st.session_state.recortes_lote = []

def renderizar_autenticacao():
    col_v1, col_center, col_v2 = st.columns([1, 2, 1])
    with col_center:
        st.markdown("""
            <div style="text-align: center; margin-bottom: 30px; margin-top: 40px;">
                <h1 style="font-size: 36px; font-weight: bold; margin: 0;">LOGO &nbsp;&nbsp;&nbsp;&nbsp; Recorte de Etiquetas</h1>
                <p style="color: #a1a1a6; font-size: 14px; margin-top: 10px;">Acesse para recortar as etiquetas </p>
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

        with aba_esqueci:
            if st.session_state.etapa_esqueci == "solicitar":
                with st.form("form_esqueci_solicitar"):
                    st.markdown("##### Redefinição de Senha")
                    st.caption("Digite seu e-mail cadastrado para receber o código de verificação.")
                    email_req = st.text_input("E-mail").strip().lower()
                    btn_solicitar = st.form_submit_button("Enviar Código por E-mail")

                    if btn_solicitar:
                        usuarios = carregar_usuarios()
                        if email_req in usuarios:
                            codigo = gerar_codigo_verificacao()
                            usuarios[email_req]["codigo_recuperacao"] = codigo
                            salvar_usuarios(usuarios)
                            
                            ok, msg = enviar_codigo_email(email_req, codigo)
                            if ok:
                                st.session_state.email_esqueci = email_req
                                st.session_state.etapa_esqueci = "validar"
                                st.success("Código enviado para o seu e-mail!")
                                st.rerun()
                            else:
                                st.error(f"Erro ao enviar o e-mail: {msg}")
                        else:
                            st.error("E-mail não cadastrado no sistema.")

            elif st.session_state.etapa_esqueci == "validar":
                with st.form("form_esqueci_validar"):
                    st.markdown("##### Digite o Código e a Nova Senha")
                    st.info(f"Código enviado para: **{st.session_state.email_esqueci}**")
                    codigo_in = st.text_input("Código de 6 dígitos", max_chars=6).strip()
                    nova_senha = st.text_input("Nova Senha", type="password")
                    confirma_senha = st.text_input("Confirme a Nova Senha", type="password")
                    
                    col_btn1, col_btn2 = st.columns([1, 1])
                    with col_btn1:
                        btn_alterar = st.form_submit_button("Redefinir Senha")
                    with col_btn2:
                        btn_voltar = st.form_submit_button("Voltar")

                    if btn_voltar:
                        st.session_state.etapa_esqueci = "solicitar"
                        st.session_state.email_esqueci = None
                        st.rerun()

                    if btn_alterar:
                        if nova_senha != confirma_senha:
                            st.error("As senhas não coincidem.")
                        elif len(nova_senha) < 4:
                            st.error("A nova senha deve ter pelo menos 4 caracteres.")
                        else:
                            usuarios = carregar_usuarios()
                            user_data = usuarios.get(st.session_state.email_esqueci, {})
                            if codigo_in == user_data.get("codigo_recuperacao"):
                                usuarios[st.session_state.email_esqueci]["senha"] = gerar_hash_senha(nova_senha)
                                usuarios[st.session_state.email_esqueci].pop("codigo_recuperacao", None)
                                salvar_usuarios(usuarios)
                                st.success("✅ Senha redefinida com sucesso! Faça login na aba 'Entrar'.")
                                st.session_state.etapa_esqueci = "solicitar"
                                st.session_state.email_esqueci = None
                            else:
                                st.error("Código de verificação incorreto.")

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
                        else:
                            st.error(f"Erro ao enviar o e-mail: {msg}")

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
                        else:
                            st.error("Código inválido.")

# ==============================================================================
# FERRAMENTA DE RECORTE (COM BOTÃO DE DISPARO E PROCESSAMENTO EM LOTE)
# ==============================================================================
def renderizar_ferramenta_recorte():
    col_upload, col_painel = st.columns([2.2, 1])
    
    with col_upload:
        arquivos = st.file_uploader(
            "📁 Selecione as fotos do lote", 
            type=["jpg", "png", "jpeg"], 
            accept_multiple_files=True
        )
        
        if arquivos:
            total = len(arquivos)
            st.info(f"📌 **{total} fotos** carregadas e prontas para processamento.")
            
            if st.button("🚀 INICIAR RECORTE AUTOMÁTICO", key="btn_iniciar_recorte"):
                recortes = []
                barra_progresso = st.progress(0)
                status_texto = st.empty()
                
                for idx, arq in enumerate(arquivos):
                    status_texto.text(f"Processando foto {idx+1} de {total}: {arq.name}...")
                    bytes_img = arq.getvalue()
                    candidatos = extrair_candidatos_etiqueta(bytes_img)
                    
                    if candidatos:
                        melhor_crop = candidatos[0]["imagem"]
                        recortes.append((f"etiqueta_{idx+1}_{arq.name}", converter_imagem_para_bytes(melhor_crop)))
                    
                    barra_progresso.progress((idx + 1) / total)
                
                status_texto.empty()
                barra_progresso.empty()
                st.session_state.recortes_lote = recortes
                st.success(f"⚡ Sucesso! {len(recortes)} de {total} etiquetas foram recortadas")
            
            if st.session_state.recortes_lote:
                st.write("---")
                st.markdown("##### 👁️ Amostra das Etiquetas Recortadas")
                cols_prev = st.columns(3)
                for p_idx, (nome, b_img) in enumerate(st.session_state.recortes_lote[:6]):
                    with cols_prev[p_idx % 3]:
                        st.image(b_img, caption=nome, use_container_width=True)

    with col_painel:
        st.markdown("### 📊 Painel do Lote")
        
        qtd_arquivos = len(arquivos) if arquivos else 0
        qtd_recortadas = len(st.session_state.recortes_lote) if arquivos else 0
        
        st.markdown(f"""
            <div class="stat-card">
                <div class="stat-number">{qtd_arquivos}</div>
                <div class="stat-label">Fotos Carregadas</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{qtd_recortadas}</div>
                <div class="stat-label">Etiquetas Prontas</div>
            </div>
        """, unsafe_allow_html=True)

        if st.session_state.recortes_lote and arquivos:
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for nome_arq, dados_bytes in st.session_state.recortes_lote:
                    if dados_bytes:
                        zip_file.writestr(nome_arq, dados_bytes)
            
            st.markdown("#### 📦 Download Express")
            st.download_button(
                label=f"⬇️ BAIXAR {len(st.session_state.recortes_lote)} ETIQUETAS (.ZIP)",
                data=zip_buffer.getvalue(),
                file_name="lote_etiquetas_recortadas.zip",
                mime="application/zip",
                key="btn_download_zip_lote"
            )

# ==============================================================================
# PAINEL DO ADMINISTRADOR
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
                <p style='color: #a1a1a6; margin-top: 5px;'>Recortador inteligente de etiquetas.</p>
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
            st.session_state.recortes_lote = []
            st.rerun()

    st.markdown("""
        <div class="footer-text">
            Desenvolvido por <b>Diego Costa</b>
        </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
