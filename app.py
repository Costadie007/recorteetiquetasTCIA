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

# --- ESTILIZAÇÃO CSS & SCRIPT DE REMOÇÃO FORÇADA ---
st.markdown(
    f"""
    <style>
    /* 1. Oculta barra superior, header, menu e toolbar */
    [data-testid="stToolbar"], 
    [data-testid="stHeader"], 
    header, 
    #MainMenu,
    .stApp > header {{
        display: none !important;
        visibility: hidden !important;
        height: 0px !important;
    }}
    
    /* 2. Oculta o rodapé padrão */
    footer {{
        display: none !important;
    }}

    /* 3. Oculta elementos remanescentes da nuvem */
    [data-testid="stStatusWidget"],
    [data-testid="stConnectionStatus"],
    .viewerBadge_container__1QSob,
    .viewerBadge_link__1S137,
    #ConnectionStatus,
    div[class*="viewerBadge"],
    div[class*="stStatusWidget"],
    div[data-testid="stDecoration"],
    iframe[title="streamlitApp"] ~ div,
    a[href*="streamlit.io"] {{
        display: none !important;
        visibility: hidden !important;
        opacity: 0 !important;
        pointer-events: none !important;
    }}

    /* Estilização Geral do App */
    .stApp {{
        background-color: {COR_GRAFITE};
        color: {COR_TEXTO};
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }}
    div.block-container {{
        padding-top: 1rem !important;
        padding-bottom: 2rem;
        max-width: 92%;
    }}
    h1, h2, h3, h4, h5, h6, p, span, label {{
        color: {COR_TEXTO} !important;
    }}
    .metric-card {{
        background-color: {COR_FUNDO_CARD};
        border: 1px solid #444340;
        border-radius: 10px;
        padding: 12px 8px;
        text-align: center;
        box-shadow: 0 2px 8px rgba(0,0,0,0.2);
    }}
    .metric-value {{
        font-size: 26px;
        font-weight: bold;
        color: {COR_LARANJA} !important;
        line-height: 1.1;
        margin-bottom: 4px;
    }}
    .metric-label {{
        font-size: 11px;
        color: #aaaaaa !important;
        letter-spacing: 0.5px;
    }}
    .stButton>button {{
        background: linear-gradient(90deg, {COR_LARANJA} 0%, #d88100 100%) !important;
        color: #FFFFFF !important;
        border-radius: 8px !important;
        font-weight: bold !important;
        font-size: 16px !important;
        border: none !important;
        padding: 0.6rem 1.2rem !important;
        box-shadow: 0 4px 15px rgba(243, 146, 0, 0.3) !important;
        transition: all 0.3s ease !important;
    }}
    .stButton>button:hover {{
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 20px rgba(243, 146, 0, 0.5) !important;
    }}
    .stDownloadButton>button {{
        background-color: {COR_LARANJA} !important;
        color: #FFFFFF !important;
        border-radius: 8px !important;
        font-weight: bold !important;
        border: none !important;
        box-shadow: 0 4px 12px rgba(243, 146, 0, 0.3) !important;
        width: 100% !important;
        padding: 0.75rem !important;
    }}
    [data-testid="stFileUploadDropzone"] {{
        background-color: {COR_FUNDO_CARD} !important;
        border: 2px dashed {COR_LARANJA} !important;
        border-radius: 12px !important;
        padding: 25px !important;
    }}
    .stProgress > div > div > div > div {{
        background-color: {COR_LARANJA} !important;
    }}
    .badge-admin {{
        background-color: {COR_LARANJA};
        color: #000000;
        font-size: 11px;
        font-weight: bold;
        padding: 3px 8px;
        border-radius: 12px;
        margin-left: 5px;
    }}
    </style>

    <script>
    const removerElementos = () => {{
        const elementos = parent.document.querySelectorAll('[data-testid="stStatusWidget"], .viewerBadge_container__1QSob, a[href*="streamlit.io"]');
        elementos.forEach(el => el.remove());
    }};
    setInterval(removerElementos, 1000);
    </script>
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


def salvar_config_smtp(config):
    with open(ARQUIVO_CONFIG, "w") as f:
        json.dump(config, f, indent=4)


def enviar_notificacao_email(assunto, mensagem_html, email_destino):
    cfg = carregar_config_smtp()
    remetente = cfg.get("email_remetente")
    senha = cfg.get("senha_app")

    if not remetente or not senha:
        return False, "Configuração de SMTP ausente (Remetente ou Senha)."

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
        return True, "E-mail enviado com sucesso!"
    except smtplib.SMTPAuthenticationError:
        return False, (
            "Erro de Autenticação: Verifique se usou a 'Senha de App' de 16"
            " dígitos."
        )
    except Exception as e:
        return False, f"Erro ao enviar e-mail: {str(e)}"


def resetar_e_carregar_usuarios():
    dados_padrao = {
        USUARIO_ADMIN: {
            "senha": "admin123",
            "email": "diego2007costa@gmail.com",
            "status": "aprovado",
            "role": "admin",
        },
        "operador": {
            "senha": "recorte2026",
            "email": "operador@empresa.com",
            "status": "aprovado",
            "role": "user",
        },
    }
    with open(ARQUIVO_USUARIOS, "w") as f:
        json.dump(dados_padrao, f, indent=4)
    return dados_padrao


def carregar_usuarios():
    if not os.path.exists(ARQUIVO_USUARIOS):
        return resetar_e_carregar_usuarios()
    try:
        with open(ARQUIVO_USUARIOS, "r") as f:
            return json.load(f)
    except Exception:
        return resetar_e_carregar_usuarios()


def salvar_usuarios_dict(usuarios):
    with open(ARQUIVO_USUARIOS, "w") as f:
        json.dump(usuarios, f, indent=4)


def solicitar_novo_cadastro(usuario, email, senha):
    usuarios = carregar_usuarios()
    usuario_key = usuario.strip().lower()
    email_limpo = email.strip().lower()

    usuarios[usuario_key] = {
        "senha": senha,
        "email": email_limpo,
        "status": "pendente",
        "role": "user",
    }
    salvar_usuarios_dict(usuarios)

    cfg = carregar_config_smtp()
    url_sistema = cfg.get("url_sistema", "http://localhost:8501")

    email_admin = usuarios.get(USUARIO_ADMIN, {}).get("email", "")
    if email_admin:
        corpo_admin = f"""
        <!DOCTYPE html>
        <html>
        <head><meta charset="utf-8"></head>
        <body style="margin: 0; padding: 0; background-color: #2A2927; font-family: 'Segoe UI', Arial, sans-serif;">
            <table border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 600px; margin: 30px auto; background-color: #333230; border-radius: 12px; border: 1px solid #444340; overflow: hidden;">
                <tr>
                    <td align="center" style="padding: 25px; background-color: #222120; border-bottom: 3px solid #F39200;">
                        <h1 style="color: #F39200; font-size: 28px; font-weight: 900; margin: 0;">LOGO</h1>
                        <p style="color: #aaaaaa; font-size: 12px; margin: 5px 0 0 0; text-transform: uppercase;">Painel do Administrador</p>
                    </td>
                </tr>
                <tr>
                    <td style="padding: 30px; color: #FFFFFF;">
                        <h2 style="color: #FFFFFF; font-size: 20px; margin-top: 0;">⏳ Nova Solicitação de Cadastro</h2>
                        <p style="color: #dddddd; font-size: 14px; line-height: 1.5;">Um novo usuário solicitou acesso ao sistema:</p>
                        <div style="background-color: #2A2927; padding: 15px; border-radius: 8px; border: 1px solid #444340; margin: 15px 0;">
                            <p style="margin: 5px 0; color: #dddddd; font-size: 14px;"><strong>Usuário:</strong> <span style="color: #F39200;">{usuario_key}</span></p>
                            <p style="margin: 5px 0; color: #dddddd; font-size: 14px;"><strong>E-mail:</strong> <span style="color: #F39200;">{email_limpo}</span></p>
                        </div>
                        <p style="color: #dddddd; font-size: 14px;">Acesse o painel para aprovar ou recusar este cadastro.</p>
                        <div style="text-align: center; margin-top: 25px;">
                            <a href="{url_sistema}" target="_blank" style="background-color: #F39200; color: #FFFFFF; text-decoration: none; padding: 12px 25px; border-radius: 6px; font-weight: bold; font-size: 14px; display: inline-block;">Acessar Painel Admin</a>
                        </div>
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """
        enviar_notificacao_email(
            f"[Sistema Recorte] Novo Cadastro Pendente: {usuario_key}",
            corpo_admin,
            email_admin,
        )


def alterar_status_usuario(usuario, novo_status):
    usuarios = carregar_usuarios()
    if usuario in usuarios:
        email_destino = (
            usuarios[usuario].get("email")
            if isinstance(usuarios[usuario], dict)
            else None
        )

        if novo_status == "excluir":
            del usuarios[usuario]
        else:
            usuarios[usuario]["status"] = novo_status

        salvar_usuarios_dict(usuarios)

        cfg = carregar_config_smtp()
        url_sistema = cfg.get("url_sistema", "http://localhost:8501")

        if novo_status == "aprovado" and email_destino:
            assunto = "🎉 Seu acesso ao Sistema de Recorte foi Aprovado!"
            corpo_aprovacao = f"""
            <!DOCTYPE html>
            <html>
            <head><meta charset="utf-8"></head>
            <body style="margin: 0; padding: 0; background-color: #2A2927; font-family: 'Segoe UI', Arial, sans-serif;">
                <table border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 600px; margin: 30px auto; background-color: #333230; border-radius: 12px; border: 1px solid #444340; overflow: hidden;">
                    <tr>
                        <td align="center" style="padding: 25px; background-color: #222120; border-bottom: 3px solid #F39200;">
                            <h1 style="color: #F39200; font-size: 28px; font-weight: 900; margin: 0;">LOGO</h1>
                            <p style="color: #aaaaaa; font-size: 12px; margin: 5px 0 0 0; text-transform: uppercase;">Sistema de Recorte de Etiquetas</p>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 30px; color: #FFFFFF;">
                            <h2 style="color: #FFFFFF; font-size: 20px; margin-top: 0;">🎉 Cadastro Aprovado!</h2>
                            <p style="color: #dddddd; font-size: 14px; line-height: 1.5;">Olá, <strong>{usuario}</strong>!</p>
                            <p style="color: #dddddd; font-size: 14px; line-height: 1.5;">Sua conta foi <strong>aprovada pelo administrador</strong>. Clique no botão abaixo para acessar a plataforma:</p>
                            <div style="text-align: center; margin: 30px 0;">
                                <a href="{url_sistema}" target="_blank" style="background-color: #F39200; color: #FFFFFF; text-decoration: none; padding: 14px 28px; border-radius: 6px; font-weight: bold; font-size: 15px; display: inline-block;">🚀 Acessar Sistema de Recorte</a>
                            </div>
                        </td>
                    </tr>
                </table>
            </body>
            </html>
            """
            enviar_notificacao_email(assunto, corpo_aprovacao, email_destino)


def alterar_senha_usuario(usuario, nova_senha):
    usuarios = carregar_usuarios()
    if usuario in usuarios:
        usuarios[usuario]["senha"] = nova_senha
        salvar_usuarios_dict(usuarios)


# ESTADO DA SESSÃO
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
if "usuario_logado" not in st.session_state:
    st.session_state.usuario_logado = ""
if "dir_temp" not in st.session_state:
    st.session_state.dir_temp = None

# --- TELA DE LOGIN, ESQUECI A SENHA & CADASTRO ---
if not st.session_state.autenticado:
    st.markdown("<br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1.8, 1])

    with col2:
        st.markdown(
            f"""
            <div style="background-color: {COR_FUNDO_CARD}; padding: 25px; border-radius: 12px; border: 1px solid #444340; text-align: center;">
                <h2 style="color: {COR_LARANJA}; margin-bottom: 5px;">✂️ Sistema de Recorte</h2>
                <p style="color: #aaaaaa; font-size: 14px; margin:0;">Acesse com sua conta, recupere seu acesso ou crie um novo cadastro</p>
            </div>
        """,
            unsafe_allow_html=True,
        )

        tab_login, tab_esqueci, tab_cadastro = st.tabs(
            ["🔑 Entrar", "🔒 Esqueci a Senha", "📝 Criar Conta"]
        )
        usuarios_cadastrados = carregar_usuarios()

        with tab_login:
            with st.form("form_login"):
                usuario_input = st.text_input("Usuário").strip().lower()
                senha_input = st.text_input("Senha", type="password")
                btn_entrar = st.form_submit_button(
                    "Acessar Plataforma", use_container_width=True
                )

                if btn_entrar:
                    if usuario_input in usuarios_cadastrados:
                        dados_usr = usuarios_cadastrados[usuario_input]
                        senha_cadastrada = (
                            dados_usr["senha"]
                            if isinstance(dados_usr, dict)
                            else dados_usr
                        )
                        status_cadastrado = (
                            dados_usr.get("status", "aprovado")
                            if isinstance(dados_usr, dict)
                            else "aprovado"
                        )

                        if senha_cadastrada == senha_input:
                            if status_cadastrado == "aprovado":
                                st.session_state.autenticado = True
                                st.session_state.usuario_logado = usuario_input
                                st.success("Login realizado!")
                                st.rerun()
                            else:
                                st.warning(
                                    "⏳ Sua conta ainda está aguardando aprovação do"
                                    " administrador."
                                )
                        else:
                            st.error("Usuário ou senha incorretos.")
                    else:
                        st.error("Usuário ou senha incorretos.")

        with tab_esqueci:
            with st.form("form_esqueci_senha"):
                email_recuperacao = st.text_input("Digite seu E-mail").strip().lower()
                nova_senha_rec = st.text_input("Nova Senha", type="password")
                confirma_nova_senha = st.text_input(
                    "Confirme a Nova Senha", type="password"
                )
                btn_recuperar = st.form_submit_button(
                    "Redefinir Senha", use_container_width=True
                )

                if btn_recuperar:
                    if (
                        not email_recuperacao
                        or not nova_senha_rec
                        or not confirma_nova_senha
                    ):
                        st.warning("Preencha todos os campos.")
                    elif nova_senha_rec != confirma_nova_senha:
                        st.error("As novas senhas não coincidem.")
                    else:
                        usuario_encontrado = None
                        for usr, dados in usuarios_cadastrados.items():
                            if (
                                isinstance(dados, dict)
                                and dados.get("email", "").lower() == email_recuperacao
                            ):
                                usuario_encontrado = usr
                                break

                        if usuario_encontrado:
                            alterar_senha_usuario(usuario_encontrado, nova_senha_rec)
                            st.success(
                                f"✅ Senha do usuário '{usuario_encontrado}' atualizada com"
                                " sucesso!"
                            )
                        else:
                            st.error("Nenhuma conta encontrada com este e-mail.")

        with tab_cadastro:
            with st.form("form_cadastro"):
                novo_usuario = st.text_input("Escolha um Nome de Usuário").strip().lower()
                novo_email = st.text_input("Seu E-mail").strip().lower()
                nova_senha = st.text_input("Escolha uma Senha", type="password")
                confirma_senha = st.text_input("Confirme a Senha", type="password")
                btn_cadastrar = st.form_submit_button(
                    "Solicitar Cadastro", use_container_width=True
                )

                if btn_cadastrar:
                    if not novo_usuario or not novo_email or not nova_senha:
                        st.warning("Preencha todos os campos.")
                    elif "@" not in novo_email or "." not in novo_email:
                        st.error("Digite um e-mail válido.")
                    elif novo_usuario in usuarios_cadastrados:
                        st.error("Este nome de usuário já existe.")
                    elif nova_senha != confirma_senha:
                        st.error("As senhas não coincidem.")
                    else:
                        solicitar_novo_cadastro(novo_usuario, novo_email, nova_senha)
                        st.success(
                            "✅ Solicitação enviada! O administrador foi notificado."
                        )

    st.stop()

# --- SISTEMA PRINCIPAL ---
usuarios_db = carregar_usuarios()
dados_logado = usuarios_db.get(st.session_state.usuario_logado, {})
e_admin = (st.session_state.usuario_logado == USUARIO_ADMIN) or (
    isinstance(dados_logado, dict) and dados_logado.get("role") == "admin"
)

# --- BARRA LATERAL ---
with st.sidebar:
    if e_admin:
        st.markdown(
            f"👤 **Usuário:** `{st.session_state.usuario_logado}` <span"
            " class='badge-admin'>👑 ADMIN</span>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(f"👤 **Usuário:** `{st.session_state.usuario_logado}`")

    st.markdown("---")
    if st.button("🚪 Sair da Conta", use_container_width=True):
        st.session_state.autenticado = False
        st.session_state.usuario_logado = ""
        st.rerun()


def renderizar_texto_logo():
    return f"""
    <div style="display: flex; justify-content: center; align-items: center; padding: 10px;">
        <h1 style="
            color: {COR_LARANJA} !important;
            font-size: 38px;
            font-weight: 900;
            letter-spacing: 3px;
            margin: 0;
            text-shadow: 2px 2px 8px rgba(0, 0, 0, 0.8);
        ">LOGO</h1>
    </div>
    """


col_header_logo, col_header_text = st.columns([1.2, 4])

with col_header_logo:
    st.markdown(renderizar_texto_logo(), unsafe_allow_html=True)

with col_header_text:
    st.markdown(
        """
        <div style="padding-top: 5px;">
            <h1 style="margin:0; font-size: 32px;">Recorte de Etiquetas</h1>
            <p style="margin: 6px 0 0 0; color: #bbbbbb !important; font-size: 15px;">
                Envie as fotos das etiquetas para processamento e recorte automático em lote.
            </p>
        </div>
    """,
        unsafe_allow_html=True,
    )

st.markdown("<br>", unsafe_allow_html=True)

# --- CRIAÇÃO DAS ABAS ---
if e_admin:
    tab_ferramenta, tab_admin = st.tabs(
        ["✂️ Ferramenta de Recorte", "👑 Painel do Administrador"]
    )
else:
    (tab_ferramenta,) = st.tabs(["✂️ Ferramenta de Recorte"])
    tab_admin = None

# ==========================================
# ABA 1: FERRAMENTA DE RECORTE (PRINCIPAL)
# ==========================================
with tab_ferramenta:
    if platform.system() == "Windows":
        caminho_tesseract = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        if os.path.exists(caminho_tesseract):
            pytesseract.pytesseract.tesseract_cmd = caminho_tesseract
        else:
            st.error(
                "⚠️ Tesseract OCR não encontrado em C:\\Program"
                " Files\\Tesseract-OCR."
            )
    else:
        pytesseract.pytesseract.tesseract_cmd = "tesseract"

    @st.cache_resource
    def carregar_modelo():
        if not os.path.exists("best.pt"):
            st.error("⚠️ O arquivo 'best.pt' não foi encontrado.")
            st.stop()
        return YOLO("best.pt")

    try:
        model = carregar_modelo()
    except Exception as e:
        st.error(f"Erro ao carregar o modelo YOLO: {e}")
        st.stop()

    TERMOS_CHAVE = ["claro", "embratel", "sgp", "ctrl", "patrimonio", "propriedade"]

    if "fila_recortes" not in st.session_state:
        st.session_state.fila_recortes = {}

    col_upload, col_stats = st.columns([2.0, 1.0])

    with col_upload:
        arquivos_enviados = st.file_uploader(
            "📂 Selecione ou arraste o lote de fotos aqui",
            type=["jpg", "jpeg", "png"],
            accept_multiple_files=True,
        )

    with col_stats:
        st.markdown("##### 📊 Painel do Lote")
        tot_enviadas = len(arquivos_enviados) if arquivos_enviados else 0
        tot_prontas = len(st.session_state.fila_recortes)

        st.markdown(
            f"""
            <div class="metric-card" style="margin-bottom: 10px;">
                <div class="metric-value">{tot_enviadas}</div>
                <div class="metric-label">FOTOS CARREGADAS</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{tot_prontas}</div>
                <div class="metric-label">RECORTES PRONTOS</div>
            </div>
        """,
            unsafe_allow_html=True,
        )

    if arquivos_enviados:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button(
            "🚀 INICIAR PROCESSAMENTO DAS FOTOS", use_container_width=True
        ):
            st.session_state.fila_recortes = {}
            dir_temp = tempfile.mkdtemp()
            st.session_state.dir_temp = dir_temp

            barra_progresso = st.progress(0)
            status_texto = st.empty()
            total_fotos = len(arquivos_enviados)

            for idx, arquivo in enumerate(arquivos_enviados):
                nome_arquivo = arquivo.name
                status_texto.write(
                    f"🔍 Analisando imagem ({idx+1}/{total_fotos}):"
                    f" **{nome_arquivo}**"
                )

                file_bytes = np.asarray(bytearray(arquivo.read()), dtype=np.uint8)
                img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
                del file_bytes

                if img is None:
                    continue
                h_img, w_img, _ = img.shape

                resultados = model(img, conf=0.35, verbose=False)
                candidatas = []

                for r in resultados:
                    for box in r.boxes:
                        x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().numpy())
                        candidatas.append({
                            "coords": (x1, y1, x2, y2),
                            "altura": y2 - y1,
                            "texto_valido": False,
                        })

                if not candidatas:
                    del img
                    gc.collect()
                    continue

                etiqueta_escolhida = candidatas[0]

                if etiqueta_escolhida is not None:
                    x1, y1, x2, y2 = etiqueta_escolhida["coords"]
                    y1, y2 = max(0, y1 - 10), min(h_img, y2 + 10)
                    x1, x2 = max(0, x1 - 10), min(w_img, x2 + 10)
                    recorte = img[y1:y2, x1:x2]

                    _, buffer = cv2.imencode(".png", recorte)
                    caminho_recorte = os.path.join(
                        dir_temp, f"recorte_{nome_arquivo}.png"
                    )
                    with open(caminho_recorte, "wb") as f:
                        f.write(buffer.tobytes())

                    st.session_state.fila_recortes[nome_arquivo] = caminho_recorte

                del img
                gc.collect()
                barra_progresso.progress((idx + 1) / total_fotos)

            status_texto.success("✅ Processamento concluído!")

    if st.session_state.fila_recortes and st.session_state.dir_temp:
        st.markdown("---")
        st.markdown("### 📥 Recortes Prontos")

        caminho_zip_final = os.path.join(
            st.session_state.dir_temp, "etiquetas_recortadas.zip"
        )
        with zipfile.ZipFile(caminho_zip_final, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for nome, caminho_arquivo in st.session_state.fila_recortes.items():
                nome_recorte = f"recorte_{nome}"
                if os.path.exists(caminho_arquivo):
                    zip_file.write(caminho_arquivo, arcname=nome_recorte)

        col_down, _ = st.columns([1, 2])
        with col_down:
            with open(caminho_zip_final, "rb") as f:
                st.download_button(
                    label="📦 BAIXAR TODOS OS RECORTES (.ZIP)",
                    data=f,
                    file_name="etiquetas_recortadas.zip",
                    mime="application/zip",
                    use_container_width=True,
                )

        cols = st.columns(4)
        for i, (nome, caminho_arquivo) in enumerate(
            st.session_state.fila_recortes.items()
        ):
            with cols[i % 4]:
                if os.path.exists(caminho_arquivo):
                    st.image(caminho_arquivo, caption=nome, use_container_width=True)

# ==========================================
# ABA 2: PAINEL DO ADMINISTRADOR
# ==========================================
if e_admin and tab_admin is not None:
    with tab_admin:
        st.markdown("## 👑 Painel do Administrador")
        st.write("Gerencie aprovações de contas e configurações de notificação de e-mail.")

        tab_adm_users, tab_adm_smtp = st.tabs(
            ["👥 Gerenciar Usuários", "✉️ Configuração de E-mail (SMTP)"]
        )

        # TAB 1: USUÁRIOS
        with tab_adm_users:
            all_users = carregar_usuarios()

            st.markdown("### ⏳ Solicitações Pendentes de Aprovação")
            pendentes = {
                u: d
                for u, d in all_users.items()
                if isinstance(d, dict) and d.get("status") == "pendente"
            }

            if pendentes:
                for usr, d in pendentes.items():
                    col_u1, col_u2, col_u3, col_u4 = st.columns([2, 3, 1, 1])
                    with col_u1:
                        st.write(f"**Usuário:** `{usr}`")
                    with col_u2:
                        st.write(f"**E-mail:** {d.get('email')}")
                    with col_u3:
                        if st.button("✅ Aprovar", key=f"aprov_{usr}"):
                            alterar_status_usuario(usr, "aprovado")
                            st.success(f"Usuário '{usr}' aprovado!")
                            st.rerun()
                    with col_u4:
                        if st.button("❌ Recusar", key=f"recus_{usr}"):
                            alterar_status_usuario(usr, "excluir")
                            st.info(f"Usuário '{usr}' recusado.")
                            st.rerun()
                    st.markdown("---")
            else:
                st.info("Nenhuma solicitação de cadastro pendente.")

            st.markdown("<br>### 👥 Usuários Cadastrados no Sistema", unsafe_allow_html=True)
            aprovados = {
                u: d
                for u, d in all_users.items()
                if not isinstance(d, dict) or d.get("status") == "aprovado"
            }

            for usr, d in aprovados.items():
                col_a1, col_a2, col_a3 = st.columns([2, 3, 1])
                email_usr = d.get("email", "N/A") if isinstance(d, dict) else "N/A"
                role_usr = d.get("role", "user") if isinstance(d, dict) else "user"

                with col_a1:
                    st.write(f"👤 **{usr}** ({role_usr})")
                with col_a2:
                    st.write(f"✉️ {email_usr}")
                with col_a3:
                    if usr != USUARIO_ADMIN and usr != st.session_state.usuario_logado:
                        if st.button("🗑️ Excluir", key=f"del_{usr}"):
                            alterar_status_usuario(usr, "excluir")
                            st.warning(f"Usuário '{usr}' removido.")
                            st.rerun()

        # TAB 2: CONFIGURAÇÃO SMTP
        with tab_adm_smtp:
            st.markdown("### ⚙️ Servidor para envio de e-mails")
            cfg_atual = carregar_config_smtp()

            with st.form("form_smtp"):
                srv = st.text_input("Servidor SMTP", value=cfg_atual.get("servidor", "smtp.gmail.com"))
                porta = st.number_input("Porta", value=int(cfg_atual.get("porta", 587)))
                remetente = st.text_input("E-mail Remetente", value=cfg_atual.get("email_remetente", ""))
                senha_app = st.text_input("Senha de App (16 dígitos)", value=cfg_atual.get("senha_app", ""), type="password")
                url_sys = st.text_input("URL do Sistema (Link dos e-mails)", value=cfg_atual.get("url_sistema", "http://localhost:8501"))

                if st.form_submit_button("💾 Salvar Configurações"):
                    nova_cfg = {
                        "servidor": srv,
                        "porta": porta,
                        "email_remetente": remetente,
                        "senha_app": senha_app,
                        "url_sistema": url_sys,
                    }
                    salvar_config_smtp(nova_cfg)
                    st.success("Configurações de e-mail salvas com sucesso!")
