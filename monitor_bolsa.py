import streamlit as st
import yfinance as yf
import requests
import time
from datetime import datetime

# --- CONFIGURACIÓN DE LA PÁGINA WEB ---
st.set_page_config(
    page_title="Monitor Bolsa Pro",
    page_icon="📈",
    layout="wide"  # Usa todo el ancho de la pantalla
)

# Estilo CSS para que se vea modo "Dark Finance"
st.markdown("""
<style>
    [data-testid="stMetricValue"] {
        font-size: 26px;
        font-weight: bold;
    }
    div[data-testid="metric-container"] {
        background-color: #1E1E1E;
        border: 1px solid #333;
        padding: 15px;
        border-radius: 5px;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

# --- TUS CREDENCIALES (Cámbialas tras revocar las viejas) ---
# --- CONFIGURACIÓN DE TELEGRAM (SEGURA) ---
# Ahora le decimos al código: "Busca las llaves en la caja fuerte de Streamlit, no aquí"
try:
    TELEGRAM_TOKEN = st.secrets["TELEGRAM_TOKEN"]
    TELEGRAM_CHAT_ID = st.secrets["TELEGRAM_CHAT_ID"]
except:
    # Esto es por si lo corres en tu PC y no has configurado secrets locales
    st.error("Error: No se encontraron las claves de Telegram.")
    TELEGRAM_TOKEN = ""
    TELEGRAM_CHAT_ID = ""

# --- CONFIGURACIÓN ---
UMBRAL_ALERTA = 3.0
TICKERS = {
    "USD/CLP": "CLP=X",
    "Cobre": "HG=F",
    "WTI Oil": "CL=F",
    "LATAM": "LTM.SN",
    "Falabella": "FALABELLA.SN",
    "Banco Chile": "CHILE.SN",
    "Cencosud": "CENCOSUD.SN",
    "Ripley": "RIPLEY.SN"
}

def enviar_telegram(mensaje):
    if TELEGRAM_TOKEN == "TU_NUEVO_TOKEN_AQUI": return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mensaje, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=2)
    except:
        pass

def obtener_datos():
    data_display = []
    codigos = list(TICKERS.values())
    
    try:
        # Descargamos datos de 1 día con intervalo de 1 minuto o día
        df = yf.download(codigos, period="1d", interval="1d", progress=False)
        
        for nombre, symbol in TICKERS.items():
            try:
                # Acceso seguro a los datos de Yahoo (manejo de MultiIndex)
                if len(codigos) > 1:
                    precio = df['Close'][symbol].iloc[-1]
                    apertura = df['Open'][symbol].iloc[-1]
                else:
                    precio = df['Close'].iloc[-1]
                    apertura = df['Open'].iloc[-1]

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
        st.error(f"Error de conexión con Yahoo Finance: {e}")
        return []
    
    return data_display

# --- INTERFAZ VISUAL (LO QUE SE VE EN LA WEB) ---

st.title("📊 Monitor Bolsa Chile - Inversionista Pro")
st.markdown(f"**Última actualización:** {datetime.now().strftime('%H:%M:%S')} | *Refresco automático cada 60s*")
st.markdown("---")

datos = obtener_datos()

if not datos:
    st.warning("Cargando datos... espera un momento.")
else:
    # Crear filas de 4 columnas para las tarjetas
    cols = st.columns(4)
    
    for index, item in enumerate(datos):
        col_actual = cols[index % 4]
        
        with col_actual:
            # Formato de color automático (Verde si sube, Rojo si baja)
            st.metric(
                label=item['Nombre'],
                value=f"$ {item['Precio']:,.2f}",
                delta=f"{item['Var']:.2f}%"
            )
            
            # Si hay alerta, mostrar un aviso visual y mandar Telegram
            if item['Alerta']:
                st.error("🚨 ¡ALERTA DE VOLATILIDAD!")
                # Lógica simple para no spamear Telegram en cada recarga (opcional)
                if "alerta_enviada" not in st.session_state:
                     enviar_telegram(f"⚠️ *ALERTA WEB*: {item['Nombre']} varió un {item['Var']:.2f}%")
                     st.session_state.alerta_enviada = True

# --- RECARGA AUTOMÁTICA ---
# Esto reemplaza al "while True"
time.sleep(60)
st.rerun()
