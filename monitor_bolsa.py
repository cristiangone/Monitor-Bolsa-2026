import streamlit as st
import yfinance as yf
import requests
from datetime import datetime

# --- CONFIGURACIÓN DE TELEGRAM (¡PON TUS DATOS AQUÍ!) ---
TELEGRAM_TOKEN = "8544416493:AAFm0odmHAqexutmqN843o-vcNNqMj2dQbY" 
TELEGRAM_CHAT_ID = "31667656"

# --- Configuración de la Página ---
st.set_page_config(page_title="Monitor Pro v2", layout="wide")
st.title("🇨🇱 Monitor Estratégico - Alertas Activas")

# --- Inicializar Estado (Para no repetir alertas) ---
if 'alertas_enviadas' not in st.session_state:
    st.session_state['alertas_enviadas'] = []

# --- Función para enviar mensaje a Telegram ---
def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    params = {"chat_id": TELEGRAM_CHAT_ID, "text": mensaje}
    try:
        requests.get(url, params=params)
        return True
    except Exception as e:
        return False

# --- Función obtener datos ---
def obtener_datos(ticker):
    stock = yf.Ticker(ticker)
    hist = stock.history(period="5d")
    if len(hist) > 0:
        actual = hist['Close'].iloc[-1]
        ayer = hist['Close'].iloc[-2] if len(hist) > 1 else actual
        delta = ((actual - ayer) / ayer) * 100
        return actual, delta, hist
    return 0, 0, None

# --- Definición de Activos y Alertas ---
# Aquí definimos el precio objetivo para la alerta
portafolio = {
    "SQM-B": {"symbol": "SQM-B.SN", "alerta_precio": 60000}, 
    "CMPC": {"symbol": "CMPC.SN", "alerta_precio": 1480},
    "CCU": {"symbol": "CCU.SN", "alerta_precio": 6200},
    "Dólar": {"symbol": "CLP=X", "alerta_precio": 950}
}

# --- Panel Principal ---
col1, col2, col3, col4 = st.columns(4)
cols = [col1, col2, col3, col4]

for i, (nombre, data) in enumerate(portafolio.items()):
    precio, var, hist = obtener_datos(data["symbol"])
    
    # Mostrar Métrica en pantalla
    with cols[i]:
        st.metric(label=nombre, value=f"${precio:,.0f}", delta=f"{var:.2f}%")
        
    # LÓGICA DE ALERTA INTELIGENTE
    target = data["alerta_precio"]
    
    # Si el precio supera el target Y no hemos avisado hoy
    if precio >= target:
        alert_id = f"{nombre}_{datetime.now().strftime('%Y-%m-%d')}"
        
        if alert_id not in st.session_state['alertas_enviadas']:
            msg = f"🚀 ¡ATENCIÓN INVERSIONISTA! \n\n{nombre} acaba de romper los ${target:,.0f} \nPrecio actual: ${precio:,.0f}"
            enviar_telegram(msg)
            st.session_state['alertas_enviadas'].append(alert_id)
            st.toast(f"Alerta enviada a Telegram por {nombre}", icon="✅")

st.markdown("---")
st.caption("Nota: Las alertas se envían una vez por día cuando se cumple la condición.")

st.sidebar.markdown("---")
st.sidebar.header("🔧 Zona de Pruebas")
if st.sidebar.button("Enviar Mensaje de Prueba"):
    test = enviar_telegram("🔔 ¡Hola! Si lees esto, la conexión funciona.")
    if test:
        st.sidebar.success("✅ Mensaje enviado correctamente.")
    else:
        st.sidebar.error("❌ Error. Revisa que el TOKEN y CHAT_ID estén dentro de comillas y sean correctos.")

        
