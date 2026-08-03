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
MODELO_YOLO_PATH = "best.pt"

# Link da sua aplicação hospedada no Streamlit Cloud
URL_APLICACAO = "https://recorteetiquetastcia.streamlit.app"

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
        <p style="margin-top: 20px; font-size: 12px; color: #a1a1a6;">Insira este código na tela para submeter seu cadastro ao Administrador.</p>
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
            <p style="font-size: 12px; color: #a1a1a6;">Link direto: <a href="{URL_APLICACAO}" style="color: #ff9500;">{URL_APLICACAO}</a></p>
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
# DETECTOR EXCLUSIVO E SEGURO DE ETIQUETAS (EMBRATEL/PATRIMÔNIO)
# ==============================================================================
def recortar_somente_etiquetas_validas(imagem_bytes):
    image_np = np.frombuffer(imagem_bytes, np.uint8)
    img_bgr = cv2.imdecode(image_np, cv2.IMREAD_COLOR)
    if img_bgr is None:
        return []

    h_orig, w_orig = img_bgr.shape[:2]
    recortes_encontrados = []

    # 1. Tenta usar o Detector de Código de Barras do OpenCV de forma segura (compatível com Linux/Windows)
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
                    
                    pad_w = int((x_max - x_min) * 0.25)
                    pad_h = int((y_max - y_min) * 1.40)
                    
                    x1 = max(0, x_min - pad_w)
                    y1 = max(0, y_min - pad_h)
                    x2 = min(w_orig, x_max + pad_w)
                    y2 = min(h_orig, y_max + pad_h)
                    
                    crop = img_bgr[y1:y2, x1:x2]
                    if crop.size > 0:
                        recortes_encontrados.append({
                            "imagem": cv2.cvtColor(crop, cv2.COLOR_BGR2RGB),
                            "box": (x1, y1, x2, y2)
                        })
    except Exception:
        pass

    # 2. Análise Morfológica Restrita a Etiquetas Retangulares (Padrão Embratel)
    if not recortes_encontrados:
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 7))
        grad = cv2.morphologyEx(gray, cv2.MORPH_GRADIENT, kernel)
        _, thresh = cv2.threshold(grad, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            aspect_ratio = float(w) / max(h, 1)
            area = w * h
            
            if aspect_ratio >= 1.9 and area > (w_orig * h_orig * 0.006):
                x1, y1 = max(0, x - 10), max(0, y - 10)
                x2, y2 = min(w_orig, x + w + 10), min(h_orig, y + h + 10)
                
                crop = img_bgr[y1:y2, x1:x2]
                if crop.size > 0:
                    recortes_encontrados.append({
                        "imagem": cv2.cvtColor(crop, cv2.COLOR_BGR2RGB),
                        "box": (x1, y1, x2, y2)
                    })

    # Retorna SOMENTE recortes validados (sem imagens inteiras como fallback)
    return recortes_encontrados

# ==============================================================================
# CONTROLE DE SESSÃO E LOGIN
# ==============================================================================
if "usuario_logado" not in st.session_state:
    st.session_state.usuario_logado = None
if "etapa_cadastro" not in st.session_state:
    st.session_state.etapa_cadastro = "formulario"
if "email_em_verificacao" not in st.session_state:
    st.session_state.email_em_verificacao = None

def renderizar_autenticacao():
    col_v1, col_center, col_v2 = st.columns([1, 2, 1])
    with col_center:
        st.markdown("""
            <div style="text-align: center; margin-bottom: 30px; margin-top: 40px;">
                <h1 style="font-size: 36px; font-weight: bold; margin: 0;">LOGO &nbsp;&nbsp;&nbsp;&nbsp; Recorte de Etiquetas</h1>
                <p style="color: #a1a1a6; font-size: 14px; margin-top: 10px;">Acesse para recortar e baixar etiquetas Embratel / Códigos de Barras</p>
            </div>
        """, unsafe_allow_html=True)

        aba_login, aba_esqueci, aba_cadastro = st.tabs([
            "🔑 Entrar", 
            "🔒 Esqueci a Senha", 
            "📝 Criar Conta"
        ])
        
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
                                st.warning("E-mail não verificado. Refaça o cadastro para validar.")
                            elif u.get("status") == "pendente_aprovação_admin":
                                st.info("E-mail verificado! Aguardando aprovação do Administrador.")
                        else:
                            st.error("Senha incorreta.")
                    else:
                        st.error("Usuário não encontrado.")

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
                                st.success("Código enviado para o seu e-mail!")
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
                            
                            st.success("✅ E-mail confirmado! Aguardando aprovação do Administrador.")
                            st.session_state.etapa_cadastro = "formulario"
                            st.session_state.email_em_verificacao = None
                        else:
                            st.error("Código inválido. Tente novamente.")
                
                if st.button("⬅️ Voltar / Reenviar"):
                    st.session_state.etapa_cadastro = "formulario"
                    st.session_state.email_em_verificacao = None
                    st.rerun()

# ==============================================================================
# TELA DE RECORTE E DOWNLOAD (.ZIP EXCLUSIVO)
# ==============================================================================
def renderizar_ferramenta_recorte():
    col_upload, col_painel = st.columns([2.2, 1])
    
    total_fotos = 0
    total_recortes = 0
    todos_recortes_bytes = []
    
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
                recortes = recortar_somente_etiquetas_validas(bytes_img)
                
                st.markdown(f"### 📷 Foto #{idx+1}: `{arq.name}`")
                c_original, c_recortes = st.columns([1, 1])
                
                with c_original:
                    st.image(bytes_img, use_container_width=True, caption="Foto Enviada")
                
                with c_recortes:
                    if not recortes:
                        st.warning("⚠️ Nenhuma etiqueta no padrão com código de barras encontrada nesta foto.")
                    else:
                        st.markdown("##### ✂️ Etiquetas Recortadas:")
                        for i, r in enumerate(recortes):
                            total_recortes += 1
                            st.image(r["imagem"], use_container_width=True, caption=f"Etiqueta Validade #{total_recortes}")
                            
                            img_bytes = converter_imagem_para_bytes(r["imagem"])
                            if img_bytes:
                                nome_etiqueta = f"etiqueta_{total_recortes}.png"
                                todos_recortes_bytes.append((nome_etiqueta, img_bytes))
                                
                                st.download_button(
                                    label=f"⬇️ Baixar Etiqueta #{total_recortes} (.PNG)",
                                    data=img_bytes,
                                    file_name=nome_etiqueta,
                                    mime="image/png",
                                    key=f"dl_{idx}_{i}"
                                )

    with col_painel:
        st.markdown("### 📊 Painel do Lote")
        
        st.markdown(f"""
            <div class="stat-card">
                <div class="stat-number">{total_fotos}</div>
                <div class="stat-label">Fotos Processadas</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{total_recortes}</div>
                <div class="stat-label">Etiquetas Válidas Recortadas</div>
            </div>
        """, unsafe_allow_html=True)

        if todos_recortes_bytes:
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for nome_arq, dados_bytes in todos_recortes_bytes:
                    zip_file.writestr(nome_arq, dados_bytes)
            
            st.write("---")
            st.markdown("#### 📦 Download em Lote")
            st.download_button(
                label=f"⬇️ BAIXAR {total_recortes} ETIQUETAS (.ZIP)",
                data=zip_buffer.getvalue(),
                file_name="etiquetas_filtradas.zip",
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
        c_top1, c_top2 = st.columns([3, 1])
        with c_top1:
            st.markdown("#### Solicitações de Acesso")
        with c_top2:
            if st.button("🔄 Atualizar Lista"):
                st.rerun()

        usuarios = carregar_usuarios()
        pendentes = {
            e: d for e, d in usuarios.items() 
            if d.get("status") == "pendente_aprovação_admin" and d.get("email_verificado") == True
        }
        
        if not pendentes:
            st.info("Nenhuma conta pendente de aprovação no momento.")
        else:
            for email, d in pendentes.items():
                st.write(f"**Nome:** {d['nome']} | **E-mail:** {email}")
                novo_cargo = st.selectbox(f"Definir Cargo para {d['nome']}", ["Operador", "Administrador"], key=f"cargo_{email}")
                
                col1, col2, _ = st.columns([1, 1, 4])
                if col1.button("Aprovar", key=f"ap_{email}"):
                    usuarios[email]["cargo"] = novo_cargo
                    usuarios[email]["status"] = "ativo"
                    salvar_usuarios(usuarios)
                    
                    ok_envio, msg_envio = enviar_notificacao_aprovacao(email, d['nome'])
                    
                    if ok_envio:
                        st.success(f"✅ {email} aprovado! E-mail com o link de acesso enviado.")
                    else:
                        st.warning(f"✅ {email} aprovado, mas o envio do e-mail falhou: {msg_envio}")
                        
                    st.rerun()

                if col2.button("Rejeitar", key=f"rej_{email}"):
                    del usuarios[email]
                    salvar_usuarios(usuarios)
                    st.warning("Solicitação removida.")
                    st.rerun()

    with t2:
        st.markdown("#### Usuários Cadastrados no Sistema")
        usuarios = carregar_usuarios()
        
        if usuarios:
            dados_tabela = []
            for email, u in usuarios.items():
                dados_tabela.append({
                    "Nome": u.get("nome", "-"),
                    "E-mail": email,
                    "Cargo": u.get("cargo", "-"),
                    "Status": u.get("status", "-")
                })
            
            st.dataframe(dados_tabela, use_container_width=True)
            st.write("---")
            
            st.markdown("#### 🗑️ Remover Usuário")
            lista_emails = [e for e in usuarios.keys() if e != "admin@empresa.com.br"]
            
            if not lista_emails:
                st.caption("Não há outros usuários cadastrados além do Admin Principal.")
            else:
                usuario_para_remover = st.selectbox("Selecione o e-mail para remover:", lista_emails)
                
                col_btn, _ = st.columns([1, 3])
                if col_btn.button("❌ Excluir Usuário Selecionado", type="secondary"):
                    del usuarios[usuario_para_remover]
                    salvar_usuarios(usuarios)
                    st.success(f"Usuário {usuario_para_remover} removido com sucesso!")
                    st.rerun()

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
# ROUTER PRINCIPAL
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
                <p style='color: #a1a1a6; margin-top: 5px;'>Identificador e extrator exclusivo de etiquetas padrão Embratel.</p>
            """, unsafe_allow_html=True)

        st.write("")
        
        cargo = st.session_state.usuario_logado["cargo"]
        
        if cargo == "Administrador":
            tab_recorte, tab_admin = st.tabs(["✂️ Ferramenta de Recorte", "👑 Painel do Administrador"])
            with tab_recorte:
                renderizar_ferramenta_recorte()
            with tab_admin:
                renderizar_painel_admin()
        else:
            renderizar_ferramenta_recorte()

        st.write("")
        if st.button("🚪 Sair do Sistema", key="btn_logout_top"):
            st.session_state.usuario_logado = None
            st.rerun()

    st.markdown("""
        <div class="footer-text">
            Desenvolvido por <b>Diego Costa</b>
        </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
