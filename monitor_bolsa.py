import streamlit as st
import yfinance as yf
import requests
import time
from datetime import datetime

# --- CONFIGURACIÓN DE LA PÁGINA WEB ---
st.set_page_config(
    page_title="Monitor Bolsa Chile Pro",
    page_icon="🇨🇱",
    layout="wide"
)

# Estilo CSS "Dark Finance" mejorado
st.markdown("""
<style>
    [data-testid="stMetricValue"] {
        font-size: 24px;
        font-weight: 700;
    }
    [data-testid="stMetricDelta"] {
        font-size: 16px;
    }
    div[data-testid="metric-container"] {
        background-color: #1E1E1E;
        border: 1px solid #444;
        padding: 10px;
        border-radius: 8px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.5);
    }
</style>
""", unsafe_allow_html=True)

# --- GESTIÓN DE CREDENCIALES (TELEGRAM) ---
# Intentamos leer de secrets (Nube), si no, usamos valores vacíos para que no falle localmente
try:
    TELEGRAM_TOKEN = st.secrets["TELEGRAM_TOKEN"]
    TELEGRAM_CHAT_ID = st.secrets["TELEGRAM_CHAT_ID"]
except:
    # Valores por defecto para que el script corra sin error en tu PC
    TELEGRAM_TOKEN = "" 
    TELEGRAM_CHAT_ID = ""

# --- CONFIGURACIÓN DE ACTIVOS ---
UMBRAL_ALERTA = 2.5 # % para gatillar alerta visual

TICKERS = {
    # >> MACROECONOMÍA
    "USD/CLP": "CLP=X",
    "Cobre": "HG=F",
    "Petróleo WTI": "CL=F",
    
    # >> COMMODITIES & ENERGÍA
    "SQM-B (Litio)": "SQM-B.SN",
    "Copec": "COPEC.SN",
    
    # >> BANCA
    "Banco de Chile": "CHILE.SN",
    "Banco Bci": "BCI.SN",
    
    # >> RETAIL & MALLS
    "Falabella": "FALABELLA.SN",
    "Cencosud": "CENCOSUD.SN",
    "Ripley": "RIPLEY.SN",
    "Parque Arauco": "PARAUCO.SN",
    
    # >> OTROS SECTORES
    "LATAM": "LTM.SN",
    "Sonda (Tech)": "SONDA.SN",
    "Socovesa": "SOCOVESA.SN"
}

# --- FUNCIONES ---

def enviar_telegram(mensaje):
    """Envía alerta solo si las credenciales existen"""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: return
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mensaje, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=2)
    except:
        pass

def obtener_datos():
    """Descarga datos de mercado"""
    data_display = []
    codigos = list(TICKERS.values())
    
    try:
        # Descarga masiva optimizada
        df = yf.download(codigos, period="1d", interval="1d", progress=False)
        
        for nombre, symbol in TICKERS.items():
            try:
                # Lógica para manejar si yfinance devuelve 1 o varios activos
                if len(codigos) > 1:
                    precio = df['Close'][symbol].iloc[-1]
                    apertura = df['Open'][symbol].iloc[-1]
                else:
                    precio = df['Close'].iloc[-1]
                    apertura = df['Open'].iloc[-1]

                # Evitar división por cero
                if apertura == 0: continue

                var_pct = ((precio - apertura) / apertura) * 100
                es_alerta = abs(var_pct) >= UMBRAL_ALERTA
                
                data_display.append({
                    "Nombre": nombre, 
                    "Precio": precio, 
                    "Var": var_pct, 
                    "Alerta": es_alerta
                })
            except:
                continue
    except Exception as e:
        st.error(f"Error conectando a Yahoo Finance. Revisa tu internet.")
        return []
    
    return data_display

# --- INTERFAZ DE USUARIO (DASHBOARD) ---

col_t1, col_t2 = st.columns([4,1])
with col_t1:
    st.title("📊 Bolsa de Santiago Pro")
    st.caption("Monitoreo en tiempo real (15 min delay) | Fuente: Yahoo Finance")
with col_t2:
    if st.button("🔄 Refrescar"):
        st.rerun()

st.markdown("---")

datos = obtener_datos()

if not datos:
    st.info("⏳ Conectando con el mercado... espera unos segundos.")
else:
    # Grid responsivo: 4 tarjetas por fila
    columnas_por_fila = 4
    cols = st.columns(columnas_por_fila)
    
    for index, item in enumerate(datos):
        col_actual = cols[index % columnas_por_fila]
        
        with col_actual:
            # Determinamos el color de la flecha
            st.metric(
                label=item['Nombre'],
                value=f"$ {item['Precio']:,.2f}",
                delta=f"{item['Var']:.2f}%"
            )
            
            if item['Alerta']:
                st.warning("🔥 Alta Volatilidad")
                # Control de estado para no spamear Telegram
                clave_sesion = f"msg_{item['Nombre']}_{datetime.now().hour}"
                if clave_sesion not in st.session_state:
                     enviar_telegram(f"⚠️ *ALERTA*: {item['Nombre']} se mueve un {item['Var']:.2f}%")
                     st.session_state[clave_sesion] = True

# --- RECARGA AUTOMÁTICA ---
time.sleep(60)
st.rerun()
