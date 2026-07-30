import io
import json
import os
import platform
import smtplib
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
    [data-testid="stToolbar"], 
    [data-testid="stHeader"], 
    header, 
    #MainMenu {{
        display: none !important;
        visibility: hidden !important;
        height: 0px !important;
    }}
    
    .stApp > header {{
        display: none !important;
    }}
    
    footer {{
        display: none !important;
    }}

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
    .img-card {{
        background-color: {COR_FUNDO_CARD};
        border-radius: 10px;
        padding: 10px;
        border: 1px solid #444340;
        margin-bottom: 15px;
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
            " dígitos do Gmail."
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

    # Notifica o Administrador sobre o cadastro pendente
    email_admin = usuarios.get(USUARIO_ADMIN, {}).get("email", "")
    if email_admin:
        corpo = f"""
        <h3>✂️ Nova Solicitação de Cadastro</h3>
        <p>Um novo usuário solicitou acesso ao sistema:</p>
        <ul>
            <li><b>Usuário:</b> {usuario_key}</li>
            <li><b>E-mail:</b> {email_limpo}</li>
        </ul>
        <p>Acesse o <b>Painel do Administrador</b> para aprovar ou recusar este cadastro.</p>
        """
        enviar_notificacao_email(
            f"[Sistema Recorte] Novo Cadastro Pendente: {usuario_key}",
            corpo,
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

        # Dispara e-mail informando o Usuário sobre a Aprovação
        if novo_status == "aprovado" and email_destino:
            assunto = "🎉 Seu acesso ao Sistema de Recorte foi Aprovado!"
            corpo = f"""
            <h3>Olá, {usuario}!</h3>
            <p>Sua conta foi <b>aprovada pelo administrador</b>.</p>
            <p>Você já pode realizar login na plataforma e enviar suas fotos para recorte de etiquetas.</p>
            """
            enviar_notificacao_email(assunto, corpo, email_destino)


def alterar_senha_usuario(usuario, nova_senha):
    usuarios = carregar_usuarios()
    if usuario in usuarios:
        usuarios[usuario]["senha"] = nova_senha
        salvar_usuarios_dict(usuarios)


def alterar_email_usuario(usuario, novo_email):
    usuarios = carregar_usuarios()
    if usuario in usuarios:
        if isinstance(usuarios[usuario], dict):
            usuarios[usuario]["email"] = novo_email.strip().lower()
        salvar_usuarios_dict(usuarios)


# ESTADO DA SESSÃO
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
if "usuario_logado" not in st.session_state:
    st.session_state.usuario_logado = ""

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

        # TAB 1: LOGIN
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

        # TAB 2: ESQUECI A SENHA
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
                                " sucesso! Faça login na aba 'Entrar'."
                            )
                        else:
                            st.error("Nenhuma conta encontrada com este e-mail.")

        # TAB 3: CRIAR CONTA
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

# VERIFICA SE O USUÁRIO LOGADO É ADMIN
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


# --- EXIBIÇÃO DE TEXTO DA LOGO ---
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


# --- CABEÇALHO ---
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

# --- NAVEGAÇÃO POR ABAS DO SISTEMA ---
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
    if "duvidas_pendentes" not in st.session_state:
        st.session_state.duvidas_pendentes = {}

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
            st.session_state.duvidas_pendentes = {}

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
                    continue

                etiqueta_escolhida = None

                if len(candidatas) == 1:
                    etiqueta_escolhida = candidatas[0]
                else:
                    for cand in candidatas:
                        cx1, cy1, cx2, cy2 = cand["coords"]
                        crop_teste = img[
                            max(0, cy1 - 5) : min(h_img, cy2 + 5),
                            max(0, cx1 - 5) : min(w_img, cx2 + 5),
                        ]
                        crop_gray = cv2.cvtColor(crop_teste, cv2.COLOR_BGR2GRAY)

                        try:
                            texto_extraido = pytesseract.image_to_string(
                                crop_gray, config="--psm 11"
                            ).lower()
                            if any(termo in texto_extraido for termo in TERMOS_CHAVE):
                                cand["texto_valido"] = True
                        except Exception:
                            pass

                    validadas = [c for c in candidatas if c["texto_valido"]]

                    if len(validadas) == 1:
                        etiqueta_escolhida = validadas[0]
                    else:
                        st.session_state.duvidas_pendentes[nome_arquivo] = {
                            "imagem": img,
                            "candidatas": candidatas,
                        }

                if etiqueta_escolhida is not None:
                    x1, y1, x2, y2 = etiqueta_escolhida["coords"]
                    y1, y2 = max(0, y1 - 10), min(h_img, y2 + 10)
                    x1, x2 = max(0, x1 - 10), min(w_img, x2 + 10)
                    recorte = img[y1:y2, x1:x2]
                    _, buffer = cv2.imencode(".png", recorte)
                    st.session_state.fila_recortes[nome_arquivo] = buffer.tobytes()

                barra_progresso.progress((idx + 1) / total_fotos)

            # --- NOTIFICAÇÃO POR E-MAIL AO USUÁRIO ---
            usr_atual = st.session_state.usuario_logado
            email_usr_atual = usuarios_db.get(usr_atual, {}).get("email")

            if email_usr_atual:
                assunto_lote = "📦 Seus recortes de etiquetas estão prontos!"
                corpo_lote = f"""
                <h3>Olá, {usr_atual}!</h3>
                <p>O processamento do seu lote de fotos foi concluído com sucesso.</p>
                <ul>
                    <li><b>Total de fotos enviadas:</b> {total_fotos}</li>
                    <li><b>Recortes gerados:</b> {len(st.session_state.fila_recortes)}</li>
                </ul>
                <p>Acesse o sistema para realizar o download dos arquivos em PNG ou em pacote .ZIP.</p>
                """
                enviar_notificacao_email(assunto_lote, corpo_lote, email_usr_atual)

            status_texto.success("🎉 Processamento concluído com sucesso e e-mail enviado ao usuário!")
            st.rerun()

    if st.session_state.duvidas_pendentes:
        st.markdown("---")
        st.markdown("### ⚠️ Decisões Manuais Necessárias")
        st.write(
            "A IA encontrou múltiplas etiquetas em algumas fotos. Clique na opção"
            " correta:"
        )

        fotos_com_duvida = list(st.session_state.duvidas_pendentes.keys())

        for nome_foto in fotos_com_duvida:
            dados = st.session_state.duvidas_pendentes[nome_foto]
            img = dados["imagem"]
            h_img, w_img, _ = img.shape
            candidatas = dados["candidatas"]

            st.markdown(f"**Foto:** `{nome_foto}`")
            colunas = st.columns(len(candidatas))

            for idx, cand in enumerate(candidatas):
                cx1, cy1, cx2, cy2 = cand["coords"]
                cy1_m, cy2_m = max(0, cy1 - 10), min(h_img, cy2 + 10)
                cx1_m, cx2_m = max(0, cx1 - 10), min(w_img, cx2 + 10)
                crop_opcao = img[cy1_m:cy2_m, cx1_m:cx2_m]
                crop_rgb = cv2.cvtColor(crop_opcao, cv2.COLOR_BGR2RGB)

                with colunas[idx]:
                    st.image(
                        crop_rgb, caption=f"Opção {idx + 1}", use_container_width=True
                    )
                    if st.button(
                        f"✓ Selecionar {idx + 1}", key=f"btn_{nome_foto}_{idx}"
                    ):
                        x1, y1, x2, y2 = cand["coords"]
                        y1, y2 = max(0, y1 - 10), min(h_img, y2 + 10)
                        x1, x2 = max(0, x1 - 10), min(w_img, x2 + 10)
                        recorte = img[y1:y2, x1:x2]
                        _, buffer = cv2.imencode(".png", recorte)

                        st.session_state.fila_recortes[nome_foto] = buffer.tobytes()
                        del st.session_state.duvidas_pendentes[nome_foto]
                        st.rerun()

    if st.session_state.fila_recortes:
        st.markdown("---")
        col_titulo, col_dl_zip = st.columns([2.5, 1.5])
        with col_titulo:
            st.markdown(
                f"### 📥 Recortes Prontos ({len(st.session_state.fila_recortes)})"
            )

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(
            zip_buffer, "a", zipfile.ZIP_DEFLATED, False
        ) as zip_file:
            for nome_foto, bytes_img in st.session_state.fila_recortes.items():
                zip_file.writestr(f"recorte_{nome_foto}", bytes_img)

        with col_dl_zip:
            st.download_button(
                label="📦 BAIXAR TODOS EM .ZIP",
                data=zip_buffer.getvalue(),
                file_name="recortes_etiquetas.zip",
                mime="application/zip",
                use_container_width=True,
            )

        st.markdown("<br>", unsafe_allow_html=True)

        recortes_prontos = st.session_state.fila_recortes
        colunas_galeria = st.columns(4)

        for idx, (nome, bytes_img) in enumerate(recortes_prontos.items()):
            col_idx = idx % 4
            with colunas_galeria[col_idx]:
                st.markdown('<div class="img-card">', unsafe_allow_html=True)
                st.image(bytes_img, caption=nome, use_container_width=True)
                st.download_button(
                    label="📥 Baixar PNG",
                    data=bytes_img,
                    file_name=f"recorte_{nome}",
                    mime="image/png",
                    key=f"dl_{nome}",
                    use_container_width=True,
                )
                st.markdown("</div>", unsafe_allow_html=True)

# ==========================================
# ABA 2: EXCLUSIVA DE ADMIN
# ==========================================
if e_admin and tab_admin:
    with tab_admin:
        st.markdown("## 👑 Painel de Controle do Administrador")
        st.write(
            "Gerencie solicitações de acesso, configure o envio de e-mails e controle as contas do sistema."
        )
        st.markdown("<br>", unsafe_allow_html=True)

        todos_usuarios = carregar_usuarios()

        # CONFIGURAÇÃO DE E-MAIL
        st.markdown("### ⚙️ Configuração do Servidor de E-mail (SMTP)")
        cfg_smtp = carregar_config_smtp()

        with st.form("form_smtp_config"):
            c_serv, c_port = st.columns([3, 1])
            with c_serv:
                servidor_input = st.text_input(
                    "Servidor SMTP",
                    value=cfg_smtp.get("servidor", "smtp.gmail.com"),
                )
            with c_port:
                porta_input = st.number_input(
                    "Porta", value=int(cfg_smtp.get("porta", 587))
                )

            c_rem, c_sen = st.columns([1, 1])
            with c_rem:
                remetente_input = st.text_input(
                    "E-mail Remetente (E-mail do Sistema)",
                    value=cfg_smtp.get("email_remetente", ""),
                )
            with c_sen:
                senha_input = st.text_input(
                    "Senha / Senha de App",
                    value=cfg_smtp.get("senha_app", ""),
                    type="password",
                )

            btn_salvar_smtp = st.form_submit_button("💾 Salvar Configuração de E-mail")

            if btn_salvar_smtp:
                nova_cfg = {
                    "servidor": servidor_input.strip(),
                    "porta": int(porta_input),
                    "email_remetente": remetente_input.strip(),
                    "senha_app": senha_input.strip(),
                }
                salvar_config_smtp(nova_cfg)
                st.success("✅ Configurações de e-mail salvas com sucesso!")

        # BOTÃO DE TESTE DE EMAIL
        if st.button("🧪 Testar Disparo de E-mail para mim"):
            ok, msg = enviar_notificacao_email(
                "Teste de Conexão SMTP",
                "<p>Este é um e-mail de teste do <b>Sistema de Recorte de Etiquetas</b>!</p>",
                cfg_smtp.get("email_remetente", ""),
            )
            if ok:
                st.success(msg)
            else:
                st.error(msg)

        st.markdown("<br>", unsafe_allow_html=True)

        # ALTERAÇÃO DE E-MAIL DO ADMIN / USUÁRIOS
        st.markdown("### 📧 Alterar E-mail de Notificação do Admin / Usuários")
        with st.form("form_alterar_email"):
            col_sel, col_em = st.columns([1, 2])
            with col_sel:
                usuario_para_editar = st.selectbox(
                    "Selecione o Usuário",
                    options=list(todos_usuarios.keys()),
                    index=0,
                )
            with col_em:
                email_atual = (
                    todos_usuarios[usuario_para_editar].get("email", "")
                    if isinstance(todos_usuarios[usuario_para_editar], dict)
                    else ""
                )
                novo_email_input = st.text_input(
                    "Novo E-mail", value=email_atual
                ).strip().lower()

            btn_salvar_email = st.form_submit_button("💾 Salvar Novo E-mail")

            if btn_salvar_email:
                if (
                    not novo_email_input
                    or "@" not in novo_email_input
                    or "." not in novo_email_input
                ):
                    st.error("Por favor, digite um e-mail válido.")
                else:
                    alterar_email_usuario(usuario_para_editar, novo_email_input)
                    st.success(
                        f"✅ E-mail do usuário `{usuario_para_editar}` atualizado para"
                        f" `{novo_email_input}` com sucesso!"
                    )
                    st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)

        # SOLICITAÇÕES PENDENTES
        pendentes = {
            u: d
            for u, d in todos_usuarios.items()
            if isinstance(d, dict) and d.get("status") == "pendente"
        }

        st.markdown("### ⏳ Solicitações Pendentes")
        if pendentes:
            for usr, dados in pendentes.items():
                col_u, col_a, col_r = st.columns([3, 1, 1])
                with col_u:
                    email_usr = dados.get("email", "Sem e-mail")
                    st.markdown(
                        f"👤 **`{usr}`** (`{email_usr}`) aguardando liberação."
                    )
                with col_a:
                    if st.button("✅ Aprovar", key=f"tab_aprove_{usr}"):
                        alterar_status_usuario(usr, "aprovado")
                        st.success(f"Conta '{usr}' aprovada e e-mail enviado!")
                        st.rerun()
                with col_r:
                    if st.button("❌ Recusar", key=f"tab_reject_{usr}"):
                        alterar_status_usuario(usr, "excluir")
                        st.info(f"Conta '{usr}' recusada.")
                        st.rerun()
                st.markdown(
                    "<hr style='margin: 5px 0;'>", unsafe_allow_html=True
                )
        else:
            st.info("Nenhuma conta aguardando aprovação no momento.")

        st.markdown("<br><br>", unsafe_allow_html=True)

        # LISTA COMPLETA DE USUÁRIOS
        st.markdown("### 👥 Todos os Usuários Cadastrados")

        col_header1, col_header2, col_header3, col_header4, col_header5 = (
            st.columns([1.5, 2, 1, 1, 1.5])
        )
        col_header1.markdown("**Usuário**")
        col_header2.markdown("**E-mail**")
        col_header3.markdown("**Nível**")
        col_header4.markdown("**Status**")
        col_header5.markdown("**Ações**")
        st.markdown("---")

        for usr, dados in todos_usuarios.items():
            if isinstance(dados, dict):
                role = dados.get("role", "user")
                status = dados.get("status", "aprovado")
                email_usr = dados.get("email", "N/A")
            else:
                role = "user"
                status = "aprovado"
                email_usr = "N/A"

            col_usr, col_email, col_role, col_stat, col_act = st.columns(
                [1.5, 2, 1, 1, 1.5]
            )

            with col_usr:
                st.write(f"**`{usr}`**")

            with col_email:
                st.write(f"`{email_usr}`")

            with col_role:
                if role == "admin":
                    st.markdown("👑 **Admin**")
                else:
                    st.write("👤 Usuário")

            with col_stat:
                if status == "aprovado":
                    st.markdown(
                        "🟢 <span style='color:#00FF00;'>Aprovado</span>",
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        "🟡 <span style='color:#FFFF00;'>Pendente</span>",
                        unsafe_allow_html=True,
                    )

            with col_act:
                if usr != USUARIO_ADMIN:
                    if st.button("🗑️ Excluir", key=f"del_user_{usr}"):
                        alterar_status_usuario(usr, "excluir")
                        st.success(f"Conta `{usr}` removida!")
                        st.rerun()
                else:
                    st.write("*(Protegido)*")

            st.markdown(
                "<hr style='margin: 3px 0; border-color: #333;'>",
                unsafe_allow_html=True,
            )

# --- RODAPÉ ---
st.markdown("<br><br>", unsafe_allow_html=True)
st.markdown("---")
st.markdown(
    """
    <div style="text-align: center; padding: 12px 0; color: #888888; font-size: 13px; letter-spacing: 0.5px;">
        Desenvolvido por <strong>Diego Costa</strong>
    </div>
    """,
    unsafe_allow_html=True,
)
