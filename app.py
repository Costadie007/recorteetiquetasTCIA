import streamlit as st
import cv2
import numpy as np
import pytesseract
from ultralytics import YOLO
import platform
import os
import zipfile
import io
import base64

# --- PALETA DE CORES PERSONALIZADA ---
COR_GRAFITE = "#2A2927"
COR_LARANJA = "#F39200"
COR_FUNDO_CARD = "#333230"
COR_TEXTO = "#FFFFFF"

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Recorte de Etiquetas - TCIA",
    page_icon="✂️",
    layout="wide"
)

# --- FUNÇÃO PARA CONVERTER A LOGO EM BASE64 COM TAMANHO MAIOR ---
def carregar_logo_3d(caminho_logo):
    if os.path.exists(caminho_logo):
        with open(caminho_logo, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode()
        return f"""
        <div style="display: flex; justify-content: center; align-items: center; padding: 5px;">
            <img src="data:image/png;base64,{encoded_string}" style="
                max-width: 100%;
                max-height: 140px;
                object-fit: contain;
                filter: 
                    drop-shadow(2px 4px 6px rgba(0, 0, 0, 0.9)) 
                    drop-shadow(0px 0px 18px rgba(243, 146, 0, 0.65)) 
                    brightness(1.2) 
                    contrast(1.15);
                transform: perspective(600px) rotateX(5deg) scale(1.02);
                transition: transform 0.3s ease, filter 0.3s ease;
                cursor: pointer;
            " onmouseover="
                this.style.transform='perspective(600px) rotateX(0deg) scale(1.08)';
                this.style.filter='drop-shadow(3px 8px 12px rgba(0, 0, 0, 1)) drop-shadow(0px 0px 28px rgba(243, 146, 0, 0.95)) brightness(1.3) contrast(1.2)';
            " onmouseout="
                this.style.transform='perspective(600px) rotateX(5deg) scale(1.02)';
                this.style.filter='drop-shadow(2px 4px 6px rgba(0, 0, 0, 0.9)) drop-shadow(0px 0px 18px rgba(243, 146, 0, 0.65)) brightness(1.2) contrast(1.15)';
            "/>
        </div>
        """
    else:
        return "<h1 style='font-size: 50px; margin:0; text-align:center;'>✂️</h1>"

# --- ESTILIZAÇÃO CSS AVANÇADA ---
st.markdown(f"""
    <style>
    /* Fundo da Aplicação */
    .stApp {{
        background-color: {COR_GRAFITE};
        color: {COR_TEXTO};
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }}
    
    /* Container principal */
    div.block-container {{
        padding-top: 1.5rem;
        padding-bottom: 2rem;
        max-width: 92%;
    }}

    /* Header e Títulos */
    h1, h2, h3, h4, h5, h6, p, span, label {{
        color: {COR_TEXTO} !important;
    }}

    /* Cards do Painel do Lote sem corte de texto */
    .metric-card {{
        background-color: {COR_FUNDO_CARD};
        border: 1px solid #444340;
        border-radius: 10px;
        padding: 12px 8px;
        text-align: center;
        box-shadow: 0 2px 8px rgba(0,0,0,0.2);
        overflow: visible !important;
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
        white-space: normal !important;
        word-break: break-word !important;
        overflow: visible !important;
        line-height: 1.2;
    }}

    /* Botão Principal em Laranja */
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
    
    /* Botão de Download */
    .stDownloadButton>button {{
        background-color: {COR_LARANJA} !important;
        color: #FFFFFF !important;
        border-radius: 8px !important;
        font-weight: bold !important;
        border: none !important;
        box-shadow: 0 4px 12px rgba(243, 146, 0, 0.3) !important;
    }}
    .stDownloadButton>button:hover {{
        background-color: #d88100 !important;
        transform: translateY(-2px) !important;
    }}
    
    /* Area de Upload */
    [data-testid="stFileUploadDropzone"] {{
        background-color: {COR_FUNDO_CARD} !important;
        border: 2px dashed {COR_LARANJA} !important;
        border-radius: 12px !important;
        padding: 25px !important;
    }}
    
    /* Barra de Progresso em Laranja */
    .stProgress > div > div > div > div {{
        background-color: {COR_LARANJA} !important;
    }}
    
    /* Cards das imagens recortadas */
    .img-card {{
        background-color: {COR_FUNDO_CARD};
        border-radius: 10px;
        padding: 10px;
        border: 1px solid #444340;
        margin-bottom: 15px;
    }}
    </style>
""", unsafe_allow_html=True)

# --- CABEÇALHO COM LOGO MAIOR E TÍTULO PRINCIPAL ---
col_header_logo, col_header_text = st.columns([1.5, 4])

with col_header_logo:
    html_logo = carregar_logo_3d("logo.png")
    st.markdown(html_logo, unsafe_allow_html=True)

with col_header_text:
    st.markdown("""
        <div style="padding-top: 15px;">
            <h1 style="margin:0; font-size: 32px;">Recorte de Etiquetas - TCIA</h1>
            <p style="margin: 6px 0 0 0; color: #bbbbbb !important; font-size: 15px;">
                Envie as fotos das etiquetas para processamento e recorte automático em lote.
            </p>
        </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# --- CAMINHO AUTOMÁTICO DO TESSERACT ---
if platform.system() == "Windows":
    caminho_tesseract = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if os.path.exists(caminho_tesseract):
        pytesseract.pytesseract.tesseract_cmd = caminho_tesseract
    else:
        st.error("⚠️ Tesseract OCR não encontrado em C:\\Program Files\\Tesseract-OCR.")
else:
    pytesseract.pytesseract.tesseract_cmd = "tesseract"

# --- CARREGAR MODELO YOLO ---
@st.cache_resource
def carregar_modelo():
    if not os.path.exists("best.pt"):
        st.error("⚠️ O arquivo 'best.pt' não foi encontrado na pasta do projeto.")
        st.stop()
    return YOLO("best.pt")

try:
    model = carregar_modelo()
except Exception as e:
    st.error(f"Erro ao carregar o modelo YOLO: {e}")
    st.stop()

TERMOS_CHAVE = ["claro", "embratel", "sgp", "ctrl", "patrimonio", "propriedade"]

# --- ESTADO DA SESSÃO ---
if "fila_recortes" not in st.session_state:
    st.session_state.fila_recortes = {}
if "duvidas_pendentes" not in st.session_state:
    st.session_state.duvidas_pendentes = {}

# --- UPLOAD DE MÚLTIPLAS FOTOS E CONTADORES ---
col_upload, col_stats = st.columns([2.0, 1.0])

with col_upload:
    arquivos_enviados = st.file_uploader(
        "📂 Selecione ou arraste o lote de fotos aqui", 
        type=["jpg", "jpeg", "png"], 
        accept_multiple_files=True
    )

with col_stats:
    st.markdown("##### 📊 Painel do Lote")
    tot_enviadas = len(arquivos_enviados) if arquivos_enviados else 0
    tot_prontas = len(st.session_state.fila_recortes)
    
    st.markdown(f"""
        <div class="metric-card" style="margin-bottom: 10px;">
            <div class="metric-value">{tot_enviadas}</div>
            <div class="metric-label">FOTOS CARREGADAS</div>
        </div>
        <div class="metric-card">
            <div class="metric-value">{tot_prontas}</div>
            <div class="metric-label">RECORTES PRONTOS</div>
        </div>
    """, unsafe_allow_html=True)

# --- BOTÃO DE AÇÃO PRINCIPAL ---
if arquivos_enviados:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🚀 INICIAR PROCESSAMENTO DAS FOTOS", use_container_width=True):
        st.session_state.fila_recortes = {}
        st.session_state.duvidas_pendentes = {}
        
        barra_progresso = st.progress(0)
        status_texto = st.empty()
        total_fotos = len(arquivos_enviados)
        
        for idx, arquivo in enumerate(arquivos_enviados):
            nome_arquivo = arquivo.name
            status_texto.write(f"🔍 Analisando imagem ({idx+1}/{total_fotos}): **{nome_arquivo}**")
            
            file_bytes = np.asarray(bytearray(arquivo.read()), dtype=np.uint8)
            img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
            if img is None:
                continue
            h_img, w_img, _ = img.shape
            
            # Detecção YOLO
            resultados = model(img, conf=0.35, verbose=False)
            candidatas = []
            
            for r in resultados:
                for box in r.boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().numpy())
                    candidatas.append({
                        'coords': (x1, y1, x2, y2),
                        'altura': y2 - y1,
                        'texto_valido': False
                    })
            
            if not candidatas:
                continue
                
            etiqueta_escolhida = None
            
            if len(candidatas) == 1:
                etiqueta_escolhida = candidatas[0]
            else:
                for cand in candidatas:
                    cx1, cy1, cx2, cy2 = cand['coords']
                    crop_teste = img[max(0, cy1-5):min(h_img, cy2+5), max(0, cx1-5):min(w_img, cx2+5)]
                    crop_gray = cv2.cvtColor(crop_teste, cv2.COLOR_BGR2GRAY)
                    
                    try:
                        texto_extraido = pytesseract.image_to_string(crop_gray, config='--psm 11').lower()
                        if any(termo in texto_extraido for termo in TERMOS_CHAVE):
                            cand['texto_valido'] = True
                    except Exception:
                        pass
                
                validadas = [c for c in candidatas if c['texto_valido']]
                
                if len(validadas) == 1:
                    etiqueta_escolhida = validadas[0]
                else:
                    st.session_state.duvidas_pendentes[nome_arquivo] = {
                        "imagem": img,
                        "candidatas": candidatas
                    }
            
            if etiqueta_escolhida is not None:
                x1, y1, x2, y2 = etiqueta_escolhida['coords']
                y1, y2 = max(0, y1 - 10), min(h_img, y2 + 10)
                x1, x2 = max(0, x1 - 10), min(w_img, x2 + 10)
                recorte = img[y1:y2, x1:x2]
                _, buffer = cv2.imencode('.png', recorte)
                st.session_state.fila_recortes[nome_arquivo] = buffer.tobytes()
                
            barra_progresso.progress((idx + 1) / total_fotos)
            
        status_texto.success(f"🎉 Processamento concluído com sucesso!")
        st.rerun()

# --- PAINEL DE RESOLUÇÃO DE DÚVIDAS ---
if st.session_state.duvidas_pendentes:
    st.markdown("---")
    st.markdown("### ⚠️ Decisões Manuais Necessárias")
    st.write("A IA encontrou múltiplas etiquetas em algumas fotos. Clique na opção correta para cada uma:")
    
    fotos_com_duvida = list(st.session_state.duvidas_pendentes.keys())
    
    for nome_foto in fotos_com_duvida:
        dados = st.session_state.duvidas_pendentes[nome_foto]
        img = dados["imagem"]
        h_img, w_img, _ = img.shape
        candidatas = dados["candidatas"]
        
        st.markdown(f"**Foto:** `{nome_foto}`")
        colunas = st.columns(len(candidatas))
        
        for idx, cand in enumerate(candidatas):
            cx1, cy1, cx2, cy2 = cand['coords']
            cy1_m, cy2_m = max(0, cy1 - 10), min(h_img, cy2 + 10)
            cx1_m, cx2_m = max(0, cx1 - 10), min(h_img, cx2 + 10)
            crop_opcao = img[cy1_m:cy2_m, cx1_m:cx2_m]
            crop_rgb = cv2.cvtColor(crop_opcao, cv2.COLOR_BGR2RGB)
            
            with colunas[idx]:
                st.image(crop_rgb, caption=f"Opção {idx + 1}", use_container_width=True)
                if st.button(f"✓ Selecionar {idx + 1}", key=f"btn_{nome_foto}_{idx}"):
                    x1, y1, x2, y2 = cand['coords']
                    y1, y2 = max(0, y1 - 10), min(h_img, y2 + 10)
                    x1, x2 = max(0, x1 - 10), min(w_img, x2 + 10)
                    recorte = img[y1:y2, x1:x2]
                    _, buffer = cv2.imencode('.png', recorte)
                    
                    st.session_state.fila_recortes[nome_foto] = buffer.tobytes()
                    del st.session_state.duvidas_pendentes[nome_foto]
                    st.rerun()

# --- GALERIA DE RESULTADOS & DOWNLOADS ---
if st.session_state.fila_recortes:
    st.markdown("---")
    
    col_titulo, col_dl_zip = st.columns([2.5, 1.5])
    with col_titulo:
        st.markdown(f"### 📥 Recortes Prontos ({len(st.session_state.fila_recortes)})")
    
    # Gerar arquivo ZIP
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
        for nome_foto, bytes_img in st.session_state.fila_recortes.items():
            zip_file.writestr(f"recorte_{nome_foto}", bytes_img)
            
    with col_dl_zip:
        st.download_button(
            label="📦 BAIXAR TODOS EM .ZIP",
            data=zip_buffer.getvalue(),
            file_name="recortes_etiquetas.zip",
            mime="application/zip",
            use_container_width=True
        )
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Exibição da Galeria em Grid
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
                use_container_width=True
            )
            st.markdown('</div>', unsafe_allow_html=True)