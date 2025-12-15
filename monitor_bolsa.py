import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime
from plotly.subplots import make_subplots 
import plotly.graph_objects as go
# import yfinance as yf # <-- YA NO ES NECESARIO

# --- CONFIGURACIÓN DE LA PÁGINA WEB ---
st.set_page_config(
    page_title="Monitor Bolsa Chile | AV Stable Edition", # Cambiamos el título
    page_icon="📈",
    layout="wide"
)

# --- CONFIGURACIÓN DE CREDENCIALES ---
try:
    ALPHA_VANTAGE_API_KEY = st.secrets["ALPHA_VANTAGE_API_KEY"]
    TELEGRAM_TOKEN = st.secrets.get("TELEGRAM_TOKEN")
    TELEGRAM_CHAT_ID = st.secrets.get("TELEGRAM_CHAT_ID")
except KeyError:
    st.error("🛑 ERROR: Clave ALPHA_VANTAGE_API_KEY no encontrada.")
    ALPHA_VANTAGE_API_KEY = "DEMO"
    
# --- DEFINICIÓN DE PALETAS Y ESTILOS (Se mantienen) ---
# ... (Bloque de PALETTES, colores y CSS se mantiene) ...

# --- CONFIGURACIÓN DE ACTIVOS (SÓLO GLOBALES ESTABLES) ---
UMBRAL_ALERTA = 2.5 

TICKER_CATEGORIES = {
    # Lista estable y sin riesgo para AV
    "ACCIONES GIGANTES 🚀": {
        "Apple (AAPL)": "AAPL",
        "Microsoft (MSFT)": "MSFT",
        "Amazon (AMZN)": "AMZN",
        "Google (GOOGL)": "GOOGL",
    },
    "SECTORES ESTABLES 🛡️": {
        "Coca Cola (KO)": "KO",
        "Walmart (WMT)": "WMT",
        "Johnson & Johnson (JNJ)": "JNJ",
        "Visa (V)": "V",
    },
}

# --- LÓGICA DE MAPEO SIMPLIFICADA (SOLUCIÓN DEL KEYERROR) ---
TICKERS_PLANO = {nombre: symbol for cat in TICKER_CATEGORIES.values() for nombre, symbol in cat.items()}

# --- FUNCIONES DE ANÁLISIS TÉCNICO (Se mantienen) ---
def calcular_bollinger_bands(df, window=20, num_std=2): # ... (cuerpo se mantiene)
    df['SMA'] = df['close'].rolling(window=window).mean()
    df['STD'] = df['close'].rolling(window=window).std()
    df['Upper'] = df['SMA'] + (df['STD'] * num_std)
    df['Lower'] = df['SMA'] - (df['STD'] * num_std)
    return df.dropna()
# ... (calcular_rsi y calcular_macd se mantienen) ...
def calcular_rsi(df, window=14): # ... (cuerpo se mantiene)
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.ewm(com=window - 1, min_periods=window).mean()
    avg_loss = loss.ewm(com=window - 1, min_periods=window).mean()
    rs = avg_gain / avg_loss
    df['RSI'] = 100 - (100 / (1 + rs))
    return df

def calcular_macd(df, fast_period=12, slow_period=26, signal_period=9): # ... (cuerpo se mantiene)
    df['EMA_Fast'] = df['close'].ewm(span=fast_period, adjust=False).mean()
    df['EMA_Slow'] = df['close'].ewm(span=slow_period, adjust=False).mean()
    df['MACD'] = df['EMA_Fast'] - df['EMA_Slow']
    df['Signal_Line'] = df['MACD'].ewm(span=signal_period, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['Signal_Line']
    return df

# ... (enviar_telegram se mantiene) ...

@st.cache_data(ttl=60)
def obtener_datos():
    """Descarga datos de mercado usando Alpha Vantage con la pausa de 13 segundos."""
    data_display = []
    tickers_fallidos = []

    # --- BUCLE ÚNICO Y ESTABLE (SOLO ALPHA VANTAGE) ---
    for nombre, symbol in TICKERS_PLANO.items():
        try: 
            # 1. LLAMADA DIRECTA A LA API de Alpha Vantage 
            base_url = "https://www.alphavantage.co/query"
            params = {
                "function": "TIME_SERIES_DAILY_ADJUSTED",
                "symbol": symbol,
                "outputsize": "compact", 
                "apikey": ALPHA_VANTAGE_API_KEY
            }
            response = requests.get(base_url, params=params)
            data_raw = response.json()

            # 2. VALIDACIÓN Y PARSING (Lógica de Alpha Vantage)
            if "Time Series (Daily)" not in data_raw:
                tickers_fallidos.append(nombre)
            else:
                # ... (Lógica de parsing de AV, cálculos de indicadores y creación de Plotly se mantiene) ...
                df_hist_individual = pd.DataFrame.from_dict(data_raw["Time Series (Daily)"], orient='index')
                df_hist_individual = df_hist_individual.rename(columns=lambda x: x.split('. ')[1])
                df_hist_individual.index = pd.to_datetime(df_hist_individual.index)
                
                cols_to_convert = ['open', 'high', 'low', 'close', 'volume', 'adjusted close']
                for col in cols_to_convert:
                    df_hist_individual[col] = pd.to_numeric(df_hist_individual[col], errors='coerce')

                df_hist_individual = df_hist_individual.sort_index()

                if df_hist_individual.empty:
                    tickers_fallidos.append(nombre)
                else:
                    # 3. APLICAR CÁLCULOS DE ANÁLISIS TÉCNICO
                    df_hist_individual = calcular_bollinger_bands(df_hist_individual)
                    df_hist_individual = calcular_rsi(df_hist_individual) 
                    df_hist_individual = calcular_macd(df_hist_individual) 
                    
                    data_velas = df_hist_individual.tail(20).copy()
                    df_hoy = data_velas.iloc[-1].copy()
                    
                    precio = df_hoy['close']
                    apertura = df_hoy['open']
                    volumen = df_hoy['volume']
                    
                    var_pct = 0.0
                    if len(data_velas) >= 2:
                        close_ayer = data_velas.iloc[-2]['close']
                        if close_ayer != 0:
                            var_pct = ((precio - close_ayer) / close_ayer) * 100
                        
                    es_alerta = abs(var_pct) >= UMBRAL_ALERTA

                    # 5. CREACIÓN DE FIGURA PLOTLY (mismo código de subplots)
                    fig = make_subplots(
                        rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.03,
                        row_heights=[0.5, 0.25, 0.25]
                    )
                    
                    # --- Subplot 1: GRÁFICO DE VELAS y BB ---
                    fig.add_trace(go.Candlestick(
                        x=data_velas.index, open=data_velas['open'], high=data_velas['high'],
                        low=data_velas['low'], close=data_velas['close'],
                        increasing_line_color=COLOR_POSITIVE, decreasing_line_color=COLOR_NEGATIVE,
                        name='Velas'
                    ), row=1, col=1)

                    # Bandas de Bollinger (SMA, Upper, Lower)
                    fig.add_trace(go.Scatter(x=data_velas.index, y=data_velas['Upper'], line=dict(color='rgba(255, 165, 0, 0.8)', width=1), name='Banda Superior'), row=1, col=1)
                    fig.add_trace(go.Scatter(x=data_velas.index, y=data_velas['SMA'], line=dict(color=COLOR_ACCENT, width=1.5), name='SMA 20'), row=1, col=1)
                    fig.add_trace(go.Scatter(x=data_velas.index, y=data_velas['Lower'], line=dict(color='rgba(255, 165, 0, 0.8)', width=1), name='Banda Inferior'), row=1, col=1)
                    
                    # --- Subplot 2: RSI ---
                    fig.add_trace(go.Scatter(x=data_velas.index, y=data_velas['RSI'], line=dict(color=COLOR_POSITIVE, width=1.5), name='RSI'), row=2, col=1)
                    fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1, opacity=0.5)
                    fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1, opacity=0.5)

                    # --- Subplot 3: MACD ---
                    fig.add_trace(go.Bar(
                        x=data_velas.index, y=data_velas['MACD_Hist'], 
                        marker_color=data_velas['MACD_Hist'].apply(lambda x: COLOR_POSITIVE if x > 0 else COLOR_NEGATIVE), 
                        name='MACD Hist'
                    ), row=3, col=1)
                    fig.add_trace(go.Scatter(x=data_velas.index, y=data_velas['MACD'], line=dict(color=COLOR_ACCENT, width=1.5), name='MACD'), row=3, col=1)
                    fig.add_trace(go.Scatter(x=data_velas.index, y=data_velas['Signal_Line'], line=dict(color='orange', width=1), name='Señal'), row=3, col=1)

                    # --- Configuración General de la Figura ---
                    fig.update_layout(
                        height=450, margin=dict(l=10, r=10, t=20, b=20),
                        paper_bgcolor=COLOR_CARD_BG, plot_bgcolor=COLOR_CARD_BG,
                        showlegend=False, xaxis_rangeslider_visible=False,
                        font=dict(color=COLOR_TEXT_NEUTRAL)
                    )

                    # Configuración de Ejes
                    fig.update_yaxes(title_text="Precio / BB", row=1, col=1, showgrid=False)
                    fig.update_yaxes(title_text="RSI", range=[0, 100], row=2, col=1, showgrid=True, gridcolor=COLOR_BORDER)
                    fig.update_yaxes(title_text="MACD", row=3, col=1, showgrid=True, gridcolor=COLOR_BORDER)
                    fig.update_xaxes(row=1, col=1, showgrid=False)
                    fig.update_xaxes(row=2, col=1, showgrid=False)
                    fig.update_xaxes(row=3, col=1, showgrid=False)


                    data_display.append({
                        "Nombre": nombre, "Symbol": symbol, "Precio": precio, 
                        "Var": var_pct, "Alerta": es_alerta, "Figura_Plotly": fig,
                        "Volumen": volumen
                    })
        except Exception as e: 
            tickers_fallidos.append(nombre)
            continue 

        # --- PAUSA DE SEGURIDAD EXTREMA (13 SEGUNDOS) ---
        time.sleep(13) 
    
    # Manejo de fallos 
    if not data_display and not tickers_fallidos:
        st.error(f"🛑 Error de Conexión Severo: La API falló. Revisa tu red o la clave.")
        data_display.append({
            "Nombre": "FALLO DE CONEXIÓN", "Symbol": "ERROR", "Precio": 0.00, 
            "Var": 0.00, "Alerta": False, "Figura_Plotly": go.Figure(), "Volumen": 0
        })
    elif tickers_fallidos:
         st.sidebar.warning(f"⚠️ Datos faltantes ({len(tickers_fallidos)} tickers no cargados).")
    
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
st.caption("Gráfico de Velas con BB, RSI y MACD | Fuente: Híbrido (YFinance y Alpha Vantage)")

refresh_placeholder = st.empty()
st.divider()

loading_message_placeholder = st.empty()

datos_completos = obtener_datos()

if not datos_completos:
    with loading_message_placeholder:
        st.info("⏳ Conectando con el mercado...")
        st.caption("La carga inicial con Alpha Vantage tardará unos 2 minutos. Por favor, no actualice el navegador.")
else:
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
