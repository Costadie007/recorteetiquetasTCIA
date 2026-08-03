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
# CONFIGURAÇÕES DA PÁGINA (WIDE) E CSS CUSTOMIZADO
# ==============================================================================
st.set_page_config(
    page_title="Recorte de Etiquetas",
    page_icon="✂️",
    layout="wide"
)

st.markdown("""
    <style>
    /* Ocultar elementos nativos do Streamlit */
    header {visibility: hidden;}
    footer {visibility: hidden;}
    #MainMenu {visibility: hidden;}
    
    /* Fundo escuro */
    .stApp {
        background-color: #1c1c1e;
        color: #ffffff;
    }
    
    /* Inputs */
    div[data-baseweb="input"] {
        background-color: #2c2c2e !important;
        border-color: #3a3a3c !important;
        border-radius: 8px !important;
        color: #ffffff !important;
    }
    
    /* Cards de Estatísticas (Painel do Lote) */
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
    
    /* Botões */
    .stButton > button {
        width: 100%;
        background-color: #2c2c2e;
        color: #ffffff;
        border: 1px solid #3a3a3c;
        border-radius: 8px;
        padding: 10px 16px;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    .stButton > button:hover {
        background-color: #3a3a3c;
        border-color: #545458;
        color: #ffffff;
    }
    
    /* Rodapé */
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
# URL da sua aplicação implantada no Streamlit Cloud ou servidor
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
    # Força a existência do admin master com hash correto da senha 'admin123'
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
    <div style="font-family: Arial, sans-serif; background-color: #2c2c2e; color: #ffffff; padding: 25px; border-radius: 8px;">
        <h2 style="color: #34c759; margin-top: 0;">Conta Aprovada!</h2>
        <p>Olá, <b>{nome_usuario}</b>!</p>
        <p>Sua solicitação de cadastro foi aprovada pelo Administrador. Você já pode acessar a plataforma para realizar os recortes de etiquetas.</p>
        <div style="margin: 30px 0; text-align: center;">
            <a href="{URL_APLICACAO}" style="background-color: #ff9500; color: #ffffff; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">
                🚀 Acessar o Sistema
            </a>
        </div>
        <p style="font-size: 12px; color: #a1a1a6;">Se o botão não funcionar, acesse via o link: <br><a href="{URL_APLICACAO}" style="color: #ff9500;">{URL_APLICACAO}</a></p>
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
# TELA DE AUTENTICAÇÃO
# ==============================================================================
def renderizar_autenticacao():
    col_v1, col_center, col_v2 = st.columns([1, 2, 1])
    with col_center:
        st.markdown("""
            <div style="text-align: center; margin-bottom: 30px; margin-top: 40px;">
                <h1 style="font-size: 36px; font-weight: bold; margin: 0;">LOGO &nbsp;&nbsp;&nbsp;&nbsp; Recorte de Etiquetas</h1>
                <p style="color: #a1a1a6; font-size: 14px; margin-top: 10px;">Acesse com sua conta, recupere seu acesso ou crie um novo cadastro</p>
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
# PAINEL DE OPERAÇÃO / DASHBOARD
# ==============================================================================
def renderizar_ferramenta_recorte():
    col_upload, col_painel = st.columns([2.2, 1])
    
    total_fotos = 0
    total_recortes = 0
    
    with col_upload:
        arquivos = st.file_uploader(
            "📁 Selecione ou arraste o lote de fotos aqui", 
            type=["jpg", "png", "jpeg"], 
            accept_multiple_files=True
        )
        
        if arquivos:
            total_fotos = len(arquivos)
            st.write("---")
            for idx, arq in enumerate(arquivos):
                bytes_img = arq.getvalue()
                res = processar_etiqueta(bytes_img)
                total_recortes += len(res)
                
                st.markdown(f"### 📷 Foto #{idx+1}: {arq.name}")
                c_original, c_recortes = st.columns(2)
                with c_original:
                    st.image(bytes_img, use_container_width=True, caption="Original")
                with c_recortes:
                    for i, r in enumerate(res):
                        st.image(r["imagem"], caption=f"Recorte #{i+1}")
                        st.text_area(f"Texto #{i+1}", r["texto"], key=f"txt_{idx}_{i}")

    with col_painel:
        st.markdown("### 📊 Painel do Lote")
        
        st.markdown(f"""
            <div class="stat-card">
                <div class="stat-number">{total_fotos}</div>
                <div class="stat-label">Fotos Carregadas</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{total_recortes}</div>
                <div class="stat-label">Recortes Prontos</div>
            </div>
        """, unsafe_allow_html=True)

# ==============================================================================
# PAINEL DO ADMINISTRADOR (ATUALIZAÇÃO EM TEMPO REAL + NOTIFICAÇÃO VIA EMAIL)
# ==============================================================================
def renderizar_painel_admin():
    st.markdown("### ⚙️ Painel do Administrador")
    t1, t2, t3 = st.tabs(["Aprovação de Usuários", "👥 Gerenciar Usuários", "Configuração SMTP"])
    
    # --- ABA 1: APROVAÇÃO ---
    with t1:
        c_top1, c_top2 = st.columns([3, 1])
        with c_top1:
            st.markdown("#### Solicitações de Acesso")
        with c_top2:
            if st.button("🔄 Atualizar Lista de Pendentes"):
                st.rerun()

        # Lê os dados em disco em tempo real
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
                    
                    # Envio do E-mail notificando o usuário com o link do site
                    ok_envio, msg_envio = enviar_notificacao_aprovacao(email, d['nome'])
                    
                    if ok_envio:
                        st.success(f"✅ {email} aprovado como {novo_cargo}! E-mail com link enviado com sucesso.")
                    else:
                        st.warning(f"✅ {email} aprovado, mas falhou o envio do e-mail: {msg_envio}")
                        
                    st.rerun()

                if col2.button("Rejeitar", key=f"rej_{email}"):
                    del usuarios[email]
                    salvar_usuarios(usuarios)
                    st.warning("Solicitação removida.")
                    st.rerun()

    # --- ABA 2: GERENCIAR E REMOVER USUÁRIOS ---
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

    # --- ABA 3: CONFIGURAÇÃO SMTP ---
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
        # Cabeçalho Principal
        c_head1, c_head2 = st.columns([1, 4])
        with c_head1:
            st.markdown("<h1 style='font-size: 38px; margin: 0;'>LOGO</h1>", unsafe_allow_html=True)
        with c_head2:
            st.markdown("""
                <h1 style='font-size: 32px; margin: 0;'>Recorte de Etiquetas</h1>
                <p style='color: #a1a1a6; margin-top: 5px;'>Envie as fotos das etiquetas para processamento e recorte automático em lote.</p>
            """, unsafe_allow_html=True)

        st.write("")
        
        cargo = st.session_state.usuario_logado["cargo"]
        
        # Navegação por Abas para Administrador ou Direto para Operador
        if cargo == "Administrador":
            tab_recorte, tab_admin = st.tabs(["✂️ Ferramenta de Recorte", "👑 Painel do Administrador"])
            with tab_recorte:
                renderizar_ferramenta_recorte()
            with tab_admin:
                renderizar_painel_admin()
        else:
            renderizar_ferramenta_recorte()

        # Botão discreto para deslogar
        st.write("")
        if st.button("🚪 Sair do Sistema", key="btn_logout_top"):
            st.session_state.usuario_logado = None
            st.rerun()

    # Rodapé
    st.markdown("""
        <div class="footer-text">
            Desenvolvido por <b>Diego Costa</b>
        </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
