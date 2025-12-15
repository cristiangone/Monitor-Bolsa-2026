import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime
import plotly.graph_objects as go
from alpha_vantage.timeseries import TimeSeries # Importamos la librería AV

# --- CONFIGURACIÓN DE LA PÁGINA WEB ---
st.set_page_config(
    page_title="Monitor Bolsa Chile | Alpha Vantage Edition",
    page_icon="📈",
    layout="wide"
)

# --- CONFIGURACIÓN DE CREDENCIALES ALPHA VANTAGE ---
try:
    ALPHA_VANTAGE_API_KEY = st.secrets["ALPHA_VANTAGE_API_KEY"]
except KeyError:
    st.error("🛑 ERROR: Clave ALPHA_VANTAGE_API_KEY no encontrada. Por favor, añádela a secrets.toml.")
    ALPHA_VANTAGE_API_KEY = "DEMO"
    
# Inicializar cliente Alpha Vantage
TS = TimeSeries(key=ALPHA_VANTAGE_API_KEY, output_format='pandas')


# --- DEFINICIÓN DE PALETAS DE COLOR (Se mantiene igual) ---
# ... (PALETTES, theme, CURRENT_THEME, y asignación de COLOR_... se mantienen) ...

PALETTES = {
    "Dark": {
        "BACKGROUND": "#0d1117",
        "CARD_BG": "#161b22",
        "BORDER": "#30363d",
        "TEXT_NEUTRAL": "#e0e0e0",
        "POSITIVE": "#00b894", 
        "NEGATIVE": "#d63031", 
        "ACCENT": "#58a6ff", 
    },
    "Light": {
        "BACKGROUND": "#f0f2f6",
        "CARD_BG": "#ffffff",
        "BORDER": "#e6e6e6",
        "TEXT_NEUTRAL": "#1c1e21",
        "POSITIVE": "#00a382", 
        "NEGATIVE": "#cc3333", 
        "ACCENT": "#007bff",
    }
}

if 'theme' not in st.session_state:
    st.session_state['theme'] = "Dark"

CURRENT_THEME = PALETTES[st.session_state['theme']]
COLOR_BACKGROUND = CURRENT_THEME["BACKGROUND"]
COLOR_CARD_BG = CURRENT_THEME["CARD_BG"]
COLOR_BORDER = CURRENT_THEME["BORDER"]
COLOR_TEXT_NEUTRAL = CURRENT_THEME["TEXT_NEUTRAL"]
COLOR_POSITIVE = CURRENT_THEME["POSITIVE"]
COLOR_NEGATIVE = CURRENT_THEME["NEGATIVE"]
COLOR_ACCENT = CURRENT_THEME["ACCENT"]


# --- ESTILOS CSS (Se mantienen igual) ---
st.markdown(f"""
<style>
    .stApp {{ background-color: {COLOR_BACKGROUND}; color: {COLOR_TEXT_NEUTRAL}; }}
    h1, h2, h3, h4, p, label {{ color: {COLOR_TEXT_NEUTRAL} !important; }}
    
    /* ... (resto del CSS) ... */
    div[data-testid="metric-container"] {{
        background-color: {COLOR_CARD_BG}; border: 1px solid {COLOR_BORDER};
        padding: 20px; border-radius: 16px; box-shadow: 0 6px 12px rgba(0,0,0,0.4);
        margin-bottom: 25px; transition: transform 0.3s ease-in-out, box-shadow 0.3s ease-in-out;
    }}
    div[data-testid="metric-container"]:hover {{ transform: translateY(-5px); box-shadow: 0 10px 20px rgba(0,0,0,0.6); }}
    [data-testid="stMetricValue"] {{ font-size: 32px !important; font-weight: 800; color: {COLOR_ACCENT}; margin-bottom: 8px; }}
    [data-testid="stMetricDelta"] {{ font-size: 20px !important; font-weight: 700; }}
    [data-testid="stMetricDelta"] svg[fill="#009943"] + div {{ color: {COLOR_POSITIVE} !important; }}
    [data-testid="stMetricDelta"] svg[fill="#ff4b4b"] + div {{ color: {COLOR_NEGATIVE} !important; }}

    .volume-subtitle {{
        font-size: 13px; color: #959da5; margin-top: -10px; margin-bottom: 5px; font-weight: 500;
    }}
    
    .stTabs [data-baseweb="tab-list"] {{ gap: 15px; }}
    .stTabs [data-baseweb="tab"] {{ border-radius: 6px 6px 0 0; background: {COLOR_CARD_BG}; color: {COLOR_TEXT_NEUTRAL}; }}
    .stTabs [aria-selected="true"] {{ border-bottom: 3px solid {COLOR_ACCENT} !important; color: {COLOR_ACCENT} !important; }}
</style>
""", unsafe_allow_html=True)

# --- CONFIGURACIÓN DE ACTIVOS (Ajustamos Tickers) ---
# Nota: Alpha Vantage utiliza tickers estándar. Las divisas son robustas.
# Los tickers Chilenos (.SN) pueden requerir el sufijo de Alpha Vantage, pero probaremos con el ticker base.
UMBRAL_ALERTA = 2.5 

TICKER_CATEGORIES = {
    "MACROECONOMÍA 🌎": {
        "USD/CLP": "USDCLP", 
        "Cobre": "HG", 
        "Petróleo WTI": "WTI",
    },
    "COMMODITIES & ENERGÍA 🔋": {
        "SQM-B (Litio)": "SQM", 
        "Copec": "COPEC",
    },
    "BANCA 🏦": {
        "Banco de Chile": "CHILE", 
        "Banco Bci": "BCI",
    },
    "RETAIL & MALLS 🛍️": {
        "Falabella": "FALABELLA", 
        "Cencosud": "CENCOSUD",
        "Ripley": "RIPLEY", 
        "Parque Arauco": "PARAUCO",
    },
    "OTROS SECTORES 🚀": {
        "LATAM": "LTM", 
        "Sonda (Tech)": "SONDA", 
        "Socovesa": "SOCOVESA"
    },
    "PRUEBA (Global) 🌐": {
        "Apple (AAPL)": "AAPL",
        "Amazon (AMZN)": "AMZN",
    }
}

TICKERS_PLANO = {nombre: symbol for cat in TICKER_CATEGORIES.values() for nombre, symbol in cat.items()}


# --- FUNCIONES ---
# (enviar_telegram se mantiene igual)
def enviar_telegram(mensaje):
    try:
        TELEGRAM_TOKEN = st.secrets.get("TELEGRAM_TOKEN")
        TELEGRAM_CHAT_ID = st.secrets.get("TELEGRAM_CHAT_ID")
    except:
        return 

    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: return
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mensaje, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=2)
    except:
        pass


@st.cache_data(ttl=60)
# --- NUEVA FUNCIÓN DE ANÁLISIS TÉCNICO ---
def calcular_bollinger_bands(df, window=20, num_std=2):
    """Calcula el Promedio Móvil Simple (SMA) y las Bandas de Bollinger."""
    # Promedio Móvil Simple (SMA)
    df['SMA'] = df['close'].rolling(window=window).mean()
    
    # Desviación Estándar (Std Dev)
    df['STD'] = df['close'].rolling(window=window).std()
    
    # Bandas de Bollinger
    df['Upper'] = df['SMA'] + (df['STD'] * num_std)
    df['Lower'] = df['SMA'] - (df['STD'] * num_std)
    
    return df.dropna()

def obtener_datos():
    """Descarga datos de mercado usando Alpha Vantage."""
    data_display = []
    tickers_fallidos = []
    
    for nombre, symbol in TICKERS_PLANO.items():
        try:
            # Alpha Vantage (Time Series: Daily Adjusted)
            # data_av, meta_data = TS.get_daily_adjusted(symbol=symbol, outputsize='full')
            # Usaremos una llamada directa a requests si la librería AV falla con símbolos chilenos

            # 1. LLAMADA DIRECTA A LA API (más robusta para evitar errores de librerías)
            base_url = "https://www.alphavantage.co/query"
            params = {
                "function": "TIME_SERIES_DAILY_ADJUSTED",
                "symbol": symbol,
                "outputsize": "compact", # Últimos 100 días
                "apikey": ALPHA_VANTAGE_API_KEY
            }
            response = requests.get(base_url, params=params)
            data_raw = response.json()

            # 2. VALIDACIÓN Y PARSING
            if "Time Series (Daily)" not in data_raw:
                tickers_fallidos.append(nombre)
                continue

            # Crear DataFrame con los datos
            df_hist_individual = pd.DataFrame.from_dict(data_raw["Time Series (Daily)"], orient='index')
            df_hist_individual = df_hist_individual.rename(columns=lambda x: x.split('. ')[1])
            df_hist_individual.index = pd.to_datetime(df_hist_individual.index)
            
            # Asegurar que las columnas sean numéricas
            cols_to_convert = ['open', 'high', 'low', 'close', 'volume', 'adjusted close']
            for col in cols_to_convert:
                df_hist_individual[col] = pd.to_numeric(df_hist_individual[col], errors='coerce')

            # Invertir el orden (AV devuelve del más nuevo al más viejo)
            df_hist_individual = df_hist_individual.sort_index().tail(20)

            if df_hist_individual.empty:
                tickers_fallidos.append(nombre)
                continue
            # Dentro de 'obtener_datos()' (reemplazar la sección después del parsing)

            # ... (sección de parsing de datos de AV se mantiene igual) ...
            
            # Invertir el orden y filtrar para tener suficientes datos para el cálculo BB
            df_hist_individual = df_hist_individual.sort_index()
            
            if df_hist_individual.empty:
                tickers_fallidos.append(nombre)
                continue

            # 3. APLICAR CÁLCULO DE BANDAS DE BOLLINGER
            df_hist_individual = calcular_bollinger_bands(df_hist_individual)
            
            # Nos aseguramos de tener al menos 20 días con BB calculadas para el gráfico
            data_velas = df_hist_individual.tail(20).copy()

            if data_velas.empty:
                 tickers_fallidos.append(nombre)
                 continue

            # 4. EXTRACCIÓN DE DATOS DIARIOS (ÚLTIMO DÍA DISPONIBLE)
            df_hoy = data_velas.iloc[-1].copy()
            
            precio = df_hoy['close']
            apertura = df_hoy['open']
            volumen = df_hoy['volume']
            
            # ... (el resto del cálculo de Var y Alerta se mantiene igual) ...

            # 5. CREACIÓN DE FIGURA PLOTLY (AÑADIMOS LAS LÍNEAS BB)
            fig = go.Figure(data=[
                # Serie de Velas (Candlestick)
                go.Candlestick(
                    x=data_velas.index,
                    open=data_velas['open'],
                    high=data_velas['high'],
                    low=data_velas['low'],
                    close=data_velas['close'],
                    increasing_line_color=COLOR_POSITIVE, 
                    decreasing_line_color=COLOR_NEGATIVE,
                    name='Velas'
                ),
                # Banda Superior (Upper Band)
                go.Scatter(x=data_velas.index, y=data_velas['Upper'], line=dict(color='rgba(255, 165, 0, 0.8)', width=1), name='Banda Superior'),
                # Banda Central (SMA)
                go.Scatter(x=data_velas.index, y=data_velas['SMA'], line=dict(color=COLOR_ACCENT, width=1.5), name='SMA 20'),
                # Banda Inferior (Lower Band)
                go.Scatter(x=data_velas.index, y=data_velas['Lower'], line=dict(color='rgba(255, 165, 0, 0.8)', width=1), name='Banda Inferior')
            ])

            fig.update_layout(
                # ... (el resto de update_layout se mantiene igual) ...
                showlegend=False # Ocultar leyenda para limpiar el gráfico
            )
            
            # ... (el resto de data_display.append y el bloque try/except se mantiene) ...
           
        except Exception as e:
            # st.error(f"Error AV en {nombre}: {e}") # Descomentar para debug
            tickers_fallidos.append(nombre)
            continue
    
    # Manejo de fallos (Si no hay datos, mostramos el error de conexión)
    if not data_display:
        st.error(f"🛑 Error de Conexión Severo: Alpha Vantage falló. Revise su clave API o red.")
        # Se mantiene el dato dummy para asegurar que la UI se renderice
        data_display.append({
            "Nombre": "FALLO DE CONEXIÓN", 
            "Symbol": "ERROR",
            "Precio": 0.00, 
            "Var": 0.00, 
            "Alerta": False,
            "Figura_Plotly": go.Figure(), 
            "Volumen": 0
        })
    elif tickers_fallidos:
         st.sidebar.warning(f"⚠️ Datos faltantes (AV): {', '.join(tickers_fallidos)}")
    
    return data_display


# --- INTERFAZ DE USUARIO (DASHBOARD) ---
# --- SELECTOR DE TEMA ---
def switch_theme():
    if st.session_state['theme'] == "Dark":
        st.session_state['theme'] = "Light"
    else:
        st.session_state['theme'] = "Dark"
    st.rerun()

with st.sidebar:
    st.header("⚙️ Configuración")
    
    if st.session_state['theme'] == "Dark":
        st.button("☀️ Cambiar a Tema Claro", on_click=switch_theme)
    else:
        st.button("🌙 Cambiar a Tema Oscuro", on_click=switch_theme)

    st.divider()
    
st.title("📈 Monitor Bolsa de Santiago")
st.caption("Gráfico de Velas de 20 días | Fuente: Alpha Vantage")

refresh_placeholder = st.empty()
st.divider()

# Placeholder para el mensaje de carga
loading_message_placeholder = st.empty()

datos_completos = obtener_datos()

if not datos_completos:
    # Mostrar mensaje de carga si no hay datos
    with loading_message_placeholder:
        st.info("⏳ Conectando con el mercado...")
        st.caption("Esto puede tardar unos segundos...")
else:
    # Limpiar el mensaje de carga y mostrar la nota de cierre de mercado
    loading_message_placeholder.empty()
    st.caption("Nota: Los datos mostrados son del último cierre disponible.")
    
    # 1. Reorganización de datos
    datos_por_categoria = {}
    for cat_name, tickers in TICKER_CATEGORIES.items():
        datos_por_categoria[cat_name] = [
            item for item in datos_completos if item['Nombre'] in tickers.keys()
        ]

    # Botón de refresco
    with refresh_placeholder.container():
        if st.button("🔄 Refrescar Datos", help="Forzar la actualización inmediata de la información"):
            st.cache_data.clear()
            st.rerun()

    # 2. Implementar las pestañas
    tabs = st.tabs(list(TICKER_CATEGORIES.keys()))
    
    for i, categoria in enumerate(TICKER_CATEGORIES.keys()):
        with tabs[i]:
            datos_tab = datos_por_categoria[categoria]
            
            columnas_por_fila = 3
            cols = st.columns(columnas_por_fila)
            
            for index, item in enumerate(datos_tab):
                col_actual = cols[index % columnas_por_fila]
                
                with col_actual:
                    with st.container(border=False):
                        
                        # MOSTRAR EL VOLUMEN
                        volumen = item.get('Volumen', 0)
                        if volumen > 0:
                            volumen_formateado = f"{volumen:,.0f}".replace(",", "_").replace(".", ",").replace("_", ".")
                            st.markdown(
                                f"<div class='volume-subtitle'>Vol: {volumen_formateado}</div>", 
                                unsafe_allow_html=True
                            )

                        # Métrica de precio y variación
                        st.metric(
                            label=item['Nombre'],
                            value=f"$ {item['Precio']:,.2f}",
                            delta=f"{item['Var']:.2f}%",
                            delta_color="normal"
                        )
                        
                        # Gráfico de Velas de Plotly
                        if 'Figura_Plotly' in item:
                            st.plotly_chart(
                                item['Figura_Plotly'], 
                                use_container_width=True, 
                                config={'displayModeBar': False} 
                            )

                        # Alerta de volatilidad
                        if item['Alerta']:
                            st.warning("🔥 ALTA VOLATILIDAD")
                            clave_sesion = f"msg_{item['Nombre']}_alerted"
                            if clave_sesion not in st.session_state:
                                 enviar_telegram(f"⚠️ *ALERTA*: {item['Nombre']} se mueve un {item['Var']:.2f}%")
                                 st.session_state[clave_sesion] = True
            
    # --- RECARGA AUTOMÁTICA (SIMPLE) ---
    st.caption("Los datos se actualizarán al presionar el botón '🔄 Refrescar Datos'.")
