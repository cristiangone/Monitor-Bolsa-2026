import streamlit as st
import yfinance as yf
import requests
import time
import pandas as pd # Necesario para la manipulación de datos en la nueva lógica
from datetime import datetime

# --- CONFIGURACIÓN DE LA PÁGINA WEB ---
st.set_page_config(
    page_title="Monitor Bolsa Chile Pro | Dashboard Mejorado",
    page_icon="📈",
    layout="wide"
)

# Estilo CSS "Dark Finance" mejorado con un tema más moderno
st.markdown("""
<style>
    /* Fondo general más oscuro */
    body {
        background-color: #0d1117;
    }
    
    /* Títulos y texto en general */
    h1, h2, h3, h4, .stApp {
        color: #f0f6fc;
    }
    
    /* Mejorar la apariencia del st.metric (las tarjetas) */
    div[data-testid="metric-container"] {
        background-color: #161b22; /* Fondo de la tarjeta */
        border: 1px solid #30363d; /* Borde más sutil */
        padding: 15px;
        border-radius: 12px;
        box-shadow: 0 4px 8px rgba(0,0,0,0.3); /* Sombra suave */
        margin-bottom: 20px;
        transition: transform 0.2s;
    }
    div[data-testid="metric-container"]:hover {
        transform: translateY(-3px); /* Efecto hover para interactividad */
    }
    
    /* Valores grandes del precio */
    [data-testid="stMetricValue"] {
        font-size: 28px !important; /* Más grande que el original */
        font-weight: 700;
        color: #58a6ff; /* Color de énfasis */
    }
    
    /* Variación (Delta) */
    [data-testid="stMetricDelta"] {
        font-size: 18px !important;
        font-weight: 600;
    }
    
    /* Contenedor de gráficos/tarjetas */
    .stContainer {
        border: none !important;
        box-shadow: none !important;
    }
</style>
""", unsafe_allow_html=True)

# --- GESTIÓN DE CREDENCIALES (TELEGRAM) ---
try:
    TELEGRAM_TOKEN = st.secrets["TELEGRAM_TOKEN"]
    TELEGRAM_CHAT_ID = st.secrets["TELEGRAM_CHAT_ID"]
except:
    TELEGRAM_TOKEN = "" 
    TELEGRAM_CHAT_ID = ""

# --- CONFIGURACIÓN DE ACTIVOS (REESTRUCTURADO POR CATEGORÍA PARA PESTAÑAS) ---
UMBRAL_ALERTA = 2.5 # % para gatillar alerta visual

TICKER_CATEGORIES = {
    "MACROECONOMÍA": {
        "USD/CLP": "CLP=X",
        "Cobre": "HG=F",
        "Petróleo WTI": "CL=F",
    },
    "COMMODITIES & ENERGÍA": {
        "SQM-B (Litio)": "SQM-B.SN",
        "Copec": "COPEC.SN",
    },
    "BANCA": {
        "Banco de Chile": "CHILE.SN",
        "Banco Bci": "BCI.SN",
    },
    "RETAIL & MALLS": {
        "Falabella": "FALABELLA.SN",
        "Cencosud": "CENCOSUD.SN",
        "Ripley": "RIPLEY.SN",
        "Parque Arauco": "PARAUCO.SN",
    },
    "OTROS SECTORES": {
        "LATAM": "LTM.SN",
        "Sonda (Tech)": "SONDA.SN",
        "Socovesa": "SOCOVESA.SN"
    }
}

# Crear un diccionario plano para la descarga masiva
TICKERS_PLANO = {nombre: symbol for cat in TICKER_CATEGORIES.values() for nombre, symbol in cat.items()}


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

@st.cache_data(ttl=60) # Cachear los datos por 60 segundos
def obtener_datos():
    """Descarga datos de mercado (30 días de historial) para el gráfico y el métrico diario"""
    data_display = []
    codigos = list(TICKERS_PLANO.values())
    
    try:
        # Descarga masiva para 30 días, incluyendo Open para el cálculo de variación diaria
        # Al usar .copy(deep=True) se evita el SettingWithCopyWarning que puede ocurrir en Streamlit
        df_hist = yf.download(codigos, period="30d", interval="1d", progress=False).copy(deep=True)
        
        # Tomar los datos de hoy (última fila)
        df_hoy = df_hist.iloc[-1].copy()
        
        for nombre, symbol in TICKERS_PLANO.items():
            try:
                if len(codigos) > 1:
                    precio = df_hoy['Close'][symbol]
                    apertura = df_hoy['Open'][symbol]
                    # Solo tomamos los últimos 20 días hábiles para un gráfico más claro
                    precios_hist = df_hist['Close'][symbol].tail(20).rename('Cierre') 
                else:
                    precio = df_hoy['Close']
                    apertura = df_hoy['Open']
                    precios_hist = df_hist['Close'].tail(20).rename('Cierre')

                # Evitar división por cero
                if pd.isna(apertura) or apertura == 0: continue

                var_pct = ((precio - apertura) / apertura) * 100
                es_alerta = abs(var_pct) >= UMBRAL_ALERTA
                
                data_display.append({
                    "Nombre": nombre, 
                    "Symbol": symbol,
                    "Precio": precio, 
                    "Var": var_pct, 
                    "Alerta": es_alerta,
                    "Historico": precios_hist
                })
            except:
                continue
    except Exception as e:
        st.error(f"Error conectando a Yahoo Finance: {e}. Revisa tu conexión a internet o los tickers.")
        return []
    
    return data_display

# --- INTERFAZ DE USUARIO (DASHBOARD) ---

st.title("📈 Monitor Bolsa de Santiago Pro")
st.caption("Monitoreo en tiempo real (15 min delay) | Fuente: Yahoo Finance")

col_info, col_refresh = st.columns([5,1])
with col_refresh:
    # Usar un container para que el botón esté siempre en la misma posición vertical
    with st.container():
        st.write("") # Espacio para alinear
        if st.button("🔄 Refrescar Datos", help="Forzar la actualización inmediata de la información"):
            st.cache_data.clear() # Limpiar el caché antes de la recarga
            st.rerun()

st.divider()

datos_completos = obtener_datos()

if not datos_completos:
    st.info("⏳ Conectando con el mercado... espera unos segundos. Si el error persiste, los tickers podrían estar caídos.")
else:
    # 1. Crear un diccionario de datos por categoría para la visualización en pestañas
    datos_por_categoria = {}
    for cat_name, tickers in TICKER_CATEGORIES.items():
        datos_por_categoria[cat_name] = [
            item for item in datos_completos if item['Nombre'] in tickers.keys()
        ]

    # 2. Implementar las pestañas
    tabs = st.tabs(list(TICKER_CATEGORIES.keys()))
    
    for i, categoria in enumerate(TICKER_CATEGORIES.keys()):
        with tabs[i]:
            datos_tab = datos_por_categoria[categoria]
            
            # Grid: 3 tarjetas por fila para dar espacio al gráfico
            columnas_por_fila = 3
            
            # Usar un layout más flexible para las tarjetas
            cols = st.columns(columnas_por_fila)
            
            for index, item in enumerate(datos_tab):
                col_actual = cols[index % columnas_por_fila]
                
                with col_actual:
                    # Usar un container para dar un aspecto de tarjeta flotante
                    with st.container(border=True): 
                        # Mostrar la Métrica de precio y variación
                        st.metric(
                            label=item['Nombre'],
                            value=f"$ {item['Precio']:,.2f}",
                            delta=f"{item['Var']:.2f}%",
                            delta_color="normal" # Usar el color automático de Streamlit (verde/rojo)
                        )
                        
                        # Añadir un gráfico de línea con el historial de precios (20 días)
                        if not item['Historico'].empty:
                            st.line_chart(
                                item['Historico'], 
                                height=150, 
                                use_container_width=True,
                                color="#58a6ff" # Color de línea azul claro
                            )

                        # Mostrar alerta de volatilidad
                        if item['Alerta']:
                            st.warning("🔥 ALTA VOLATILIDAD")
                            # Control de estado para no spamear Telegram
                            clave_sesion = f"msg_{item['Nombre']}_{datetime.now().hour}"
                            if clave_sesion not in st.session_state:
                                 enviar_telegram(f"⚠️ *ALERTA*: {item['Nombre']} se mueve un {item['Var']:.2f}%")
                                 st.session_state[clave_sesion] = True
                            
# --- RECARGA AUTOMÁTICA ---
time.sleep(60) # Esperar 60 segundos
st.rerun() # Recargar la aplicación para obtener datos frescos
