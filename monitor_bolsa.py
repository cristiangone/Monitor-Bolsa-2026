import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime, timedelta
# VOLVEMOS A YFINANCE
import yfinance as yf
from plotly.subplots import make_subplots 
import plotly.graph_objects as go

# --- CONFIGURACIÓN DE LA PÁGINA WEB ---
st.set_page_config(
    page_title="Monitor Bolsa Chile | YFinance Estable",
    page_icon="📈",
    layout="wide"
)

# --- DEFINICIÓN DE PALETAS DE COLOR (Sin cambios) ---
PALETTES = {
    "Dark": {
        "BACKGROUND": "#0d1117", "CARD_BG": "#161b22", "BORDER": "#30363d",
        "TEXT_NEUTRAL": "#e0e0e0", "POSITIVE": "#00b894", "NEGATIVE": "#d63031", 
        "ACCENT": "#58a6ff", 
    },
    "Light": {
        "BACKGROUND": "#f0f2f6", "CARD_BG": "#ffffff", "BORDER": "#e6e6e6",
        "TEXT_NEUTRAL": "#1c1e21", "POSITIVE": "#00a382", "NEGATIVE": "#cc3333", 
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

# --- ESTILOS CSS (Sin cambios) ---
st.markdown(f"""
<style>
    .stApp {{ background-color: {COLOR_BACKGROUND}; color: {COLOR_TEXT_NEUTRAL}; }}
    h1, h2, h3, h4, p, label {{ color: {COLOR_TEXT_NEUTRAL} !important; }}
    
    div[data-testid="metric-container"] {{
        background-color: {COLOR_CARD_BG}; border: 1px solid {COLOR_BORDER};
        padding: 20px; border-radius: 16px; box-shadow: 0 6px 12px rgba(0,0,0,0.4);
        margin-bottom: 25px; transition: transform 0.3s ease-in-out, box-shadow 0.3s ease-in-out;
    }}
    div[data-testid="metric-container"]:hover {{ transform: translateY(-5px); box-shadow: 0 10px 20px rgba(0,0,0,0.6); }}
    
    [data-testid="stMetricValue"] {{ 
        font-size: 32px !important; font-weight: 800; 
        color: {COLOR_ACCENT}; margin-bottom: 8px; 
    }}
    
    [data-testid="stMetricDelta"] {{ font-size: 20px !important; font-weight: 700; }}
    
    .positive-name {{
        font-size: 16px; font-weight: 600; color: {COLOR_POSITIVE} !important;
    }}
    .negative-name {{
        font-size: 16px; font-weight: 600; color: #959da5 !important;
    }}
    
    .volume-subtitle {{
        font-size: 13px; color: #959da5; margin-top: -10px; margin-bottom: 5px; font-weight: 500;
    }}
    /* Clases para los indicadores de análisis técnico */
    .indicator-box {{
        padding: 4px 8px; border-radius: 6px; font-size: 12px; font-weight: 600;
        display: inline-block; margin-right: 8px; margin-bottom: 5px;
        color: {COLOR_CARD_BG};
    }}
    .rsi-overbought {{ background-color: {COLOR_NEGATIVE}; }}
    .rsi-oversold {{ background-color: {COLOR_POSITIVE}; }}
    .macd-buy {{ background-color: {COLOR_POSITIVE}; }}
    .macd-sell {{ background-color: {COLOR_NEGATIVE}; }}

    
    .stTabs [data-baseweb="tab-list"] {{ gap: 15px; }}
    .stTabs [data-baseweb="tab"] {{ border-radius: 6px 6px 0 0; background: {COLOR_CARD_BG}; color: {COLOR_TEXT_NEUTRAL}; }}
    .stTabs [aria-selected="true"] {{ border-bottom: 3px solid {COLOR_ACCENT} !important; color: {COLOR_ACCENT} !important; }}
</style>
""", unsafe_allow_html=True)


# --- GESTIÓN DE CREDENCIALES (SOLO TELEGRAM) ---
try:
    TELEGRAM_TOKEN = st.secrets["TELEGRAM_TOKEN"]
    TELEGRAM_CHAT_ID = st.secrets["TELEGRAM_CHAT_ID"]
except:
    TELEGRAM_TOKEN = "" 
    TELEGRAM_CHAT_ID = ""


# --- CONFIGURACIÓN DE ACTIVOS (VOLVEMOS A LOS TICKERS DE YFINANCE) ---
UMBRAL_ALERTA = 2.5 

TICKER_CATEGORIES = {
    "MACROECONOMÍA 🌎": {
        "USD/CLP": "CLP=X",
        "Cobre": "HG=F",
        "Petróleo WTI": "CL=F",
    },
    "COMMODITIES & ENERGÍA 🔋": {
        "SQM-B (Litio)": "SQM-B.SN",
        "Copec": "COPEC.SN",
    },
    "BANCA 🏦": {
        "Banco de Chile": "CHILE.SN",
        "Banco Bci": "BCI.SN",
    },
    "RETAIL & MALLS 🛍️": {
        "Falabella": "FALABELLA.SN",
        "Cencosud": "CENCOSUD.SN",
        "Ripley": "RIPLEY.SN",
        "Parque Arauco": "PARAUCO.SN",
    },
    "OTROS SECTORES 🚀": {
        "LATAM": "LTM.SN",
        "Sonda (Tech)": "SONDA.SN",
        "Socovesa": "SOCOVESA.SN"
    }
}

TICKERS_PLANO = {nombre: symbol for cat in TICKER_CATEGORIES.values() for nombre, symbol in cat.items()}


# --- FUNCIONES DE ANÁLISIS TÉCNICO (Sin cambios) ---
def calcular_bollinger_bands(df, window=20, num_std=2):
    df['SMA'] = df['close'].rolling(window=window).mean()
    df['STD'] = df['close'].rolling(window=window).std()
    df['Upper'] = df['SMA'] + (df['STD'] * num_std)
    df['Lower'] = df['SMA'] - (df['STD'] * num_std)
    return df

def calcular_rsi(df, window=14):
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.ewm(com=window - 1, min_periods=window).mean()
    avg_loss = loss.ewm(com=window - 1, min_periods=window).mean()
    rs = avg_gain / avg_loss
    df['RSI'] = 100 - (100 / (1 + rs))
    return df

def calcular_macd(df, fast_period=12, slow_period=26, signal_period=9):
    df['EMA_Fast'] = df['close'].ewm(span=fast_period, adjust=False).mean()
    df['EMA_Slow'] = df['close'].ewm(span=slow_period, adjust=False).mean()
    df['MACD'] = df['EMA_Fast'] - df['EMA_Slow']
    df['Signal_Line'] = df['MACD'].ewm(span=signal_period, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['Signal_Line']
    return df

def enviar_telegram(mensaje):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: return
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mensaje, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=2)
    except:
        pass


@st.cache_data(ttl=60)
def obtener_datos():
    """Descarga datos de mercado y aplica análisis técnico usando YFinance."""
    data_display = []
    codigos = list(TICKERS_PLANO.values())
    
    try:
        # Descarga masiva para 50 días 
        # Usamos period="60d" para dar margen de días no hábiles.
        df_hist = yf.download(codigos, period="60d", interval="1d", progress=False).copy(deep=True)
        
        for nombre, symbol in TICKERS_PLANO.items():
            try:
                # 1. PREPARACIÓN DEL DATAFRAME
                # Manejo de dataframe individual cuando hay múltiples tickers
                if len(codigos) > 1:
                    # Intenta acceder al MultiIndex, si falla (ej. si solo es un ticker), usa el dataframe completo
                    try:
                        df_hist_individual = df_hist.loc[:, (slice(None), symbol)].copy()
                        df_hist_individual.columns = df_hist_individual.columns.droplevel(1)
                    except KeyError:
                         df_hist_individual = df_hist.copy()
                         
                else:
                    df_hist_individual = df_hist.copy()

                df_hist_individual = df_hist_individual.rename(columns={'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume', 'Adj Close': 'adjusted close'})
                df_hist_individual.index.name = 'Date'
                
                # 2. APLICAR CÁLCULOS DE ANÁLISIS TÉCNICO
                if len(df_hist_individual) < 30:
                    continue 

                df_hist_individual = calcular_bollinger_bands(df_hist_individual)
                df_hist_individual = calcular_rsi(df_hist_individual) 
                df_hist_individual = calcular_macd(df_hist_individual) 
                
                # Nos aseguramos de tener 20 días para el gráfico
                data_velas = df_hist_individual.dropna().tail(20).copy()

                if len(data_velas) < 2: # Necesitamos al menos 2 días para calcular la variación
                    continue

                # 3. EXTRACCIÓN DE DATOS DIARIOS
                df_hoy = data_velas.iloc[-1].copy()
                df_ayer = data_velas.iloc[-2].copy() # El día anterior más reciente

                precio = df_hoy['close']
                volumen = df_hoy['volume']
                
                # CÁLCULO DE VARIACIÓN (close de HOY vs close de AYER)
                close_ayer = df_ayer['close']
                var_pct = ((precio - close_ayer) / close_ayer) * 100 if close_ayer != 0 else 0
                es_alerta = abs(var_pct) >= UMBRAL_ALERTA
                
                # 4. EXTRACCIÓN DE INDICADORES CLAVE PARA LA TARJETA
                rsi_hoy = df_hoy['RSI'] if 'RSI' in df_hoy else None
                macd_hist_hoy = df_hoy['MACD_Hist'] if 'MACD_Hist' in df_hoy else None
                macd_hist_ayer = df_ayer['MACD_Hist'] if 'MACD_Hist' in df_ayer else 0
                
                
                # 5. CREACIÓN DE FIGURA PLOTLY (4 SUBPLOTS)
                fig = make_subplots(
                    rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.02,
                    row_heights=[0.45, 0.15, 0.20, 0.20] 
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
                
                # --- Subplot 4: Volumen (Barra) ---
                fig.add_trace(go.Bar(
                    x=data_velas.index, 
                    y=data_velas['volume'],
                    marker_color='rgba(150, 150, 150, 0.6)', 
                    name='Volumen'
                ), row=4, col=1)


                # --- Configuración de la Figura ---
                fig.update_layout(
                    height=600, margin=dict(l=10, r=10, t=20, b=20),
                    paper_bgcolor=COLOR_CARD_BG, plot_bgcolor=COLOR_CARD_BG,
                    showlegend=False, xaxis_rangeslider_visible=False,
                    font=dict(color=COLOR_TEXT_NEUTRAL)
                )

                # Configuración de Ejes
                fig.update_yaxes(title_text="Precio / BB", row=1, col=1, showgrid=False)
                fig.update_yaxes(title_text="RSI", range=[0, 100], row=2, col=1, showgrid=True, gridcolor=COLOR_BORDER)
                fig.update_yaxes(title_text="MACD", row=3, col=1, showgrid=True, gridcolor=COLOR_BORDER)
                fig.update_yaxes(title_text="Vol", row=4, col=1, showgrid=False)
                fig.update_xaxes(row=4, col=1, showgrid=False)
                
                # --- Guardar datos ---
                data_display.append({
                    "Nombre": nombre, 
                    "Symbol": symbol,
                    "Precio": precio, 
                    "Var": var_pct, 
                    "Alerta": es_alerta,
                    "Figura_Plotly": fig,
                    "Volumen": volumen,
                    "Positivo": var_pct > 0,
                    "RSI_Hoy": rsi_hoy,
                    "MACD_Hist_Hoy": macd_hist_hoy,
                    "MACD_Hist_Ayer": macd_hist_ayer
                })
            except Exception as e:
                #st.error(f"Error procesando {nombre} con YFinance: {e}") # Descomentar para debug
                continue
    except Exception as e:
        st.error(f"Error general al conectar a Yahoo Finance: {e}. Revisa tu conexión o los tickers.")
        return []
    
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

st.title("📈 Monitor Bolsa de Santiago Pro")
st.caption("Gráfico de Velas con BB, RSI y MACD | Fuente: Yahoo Finance (Delay de 15 min)")

col_info, col_refresh = st.columns([5,1])
with col_refresh:
    with st.container():
        st.write("") 
        if st.button("🔄 Refrescar Datos", help="Forzar la actualización inmediata de la información"):
            st.cache_data.clear() 
            st.rerun()

st.divider()

datos_completos = obtener_datos()

if not datos_completos:
    st.info("⏳ Conectando con el mercado (YFinance)... Si el error persiste, los tickers podrían estar caídos o tu conexión fallando.")
else:
    # 1. Reorganización y Cálculo de Promedios para Pestañas
    datos_por_categoria = {}
    tabs_labels = []

    for cat_name, tickers in TICKER_CATEGORIES.items():
        datos_de_esta_cat = [
            item for item in datos_completos if item['Nombre'] in tickers.keys()
        ]
        
        if datos_de_esta_cat:
            variaciones = [item['Var'] for item in datos_de_esta_cat]
            promedio_var = sum(variaciones) / len(variaciones)
            
            icono = " 🟢" if promedio_var > 0 else " 🔴"
            
            label_final = f"{cat_name}{icono} ({promedio_var:.2f}%)"
            tabs_labels.append(label_final)
            datos_por_categoria[label_final] = datos_de_esta_cat

    # 2. Implementar las pestañas
    if tabs_labels:
        tabs = st.tabs(tabs_labels)
        
        for i, label_final in enumerate(tabs_labels):
            categoria = label_final.split(" ")[0]
            
            with tabs[i]:
                datos_tab = datos_por_categoria[label_final]
                
                columnas_por_fila = 3
                cols = st.columns(columnas_por_fila)
                
                for index, item in enumerate(datos_tab):
                    col_actual = cols[index % columnas_por_fila]
                    
                    with col_actual:
                        with st.container(border=True):
                            
                            # --- RESALTADO VISUAL DEL NOMBRE ---
                            nombre_clase = "positive-name" if item['Positivo'] else "negative-name"
                            st.markdown(
                                f"<div class='{nombre_clase}'>{item['Nombre']}</div>", 
                                unsafe_allow_html=True
                            )
                            
                            # MOSTRAR EL VOLUMEN
                            volumen = item.get('Volumen', 0)
                            if volumen > 0:
                                volumen_formateado = f"{volumen:,.0f}".replace(",", "_").replace(".", ",").replace("_", ".")
                                st.markdown(
                                    f"<div class='volume-subtitle'>Vol: {volumen_formateado}</div>", 
                                    unsafe_allow_html=True
                                )
                                
                            # --- INDICADORES DE ANÁLISIS TÉCNICO EN TEXTO ---
                            indi_html = ""
                            
                            # RSI (Sobrecampra > 70, Sobreventa < 30)
                            if item['RSI_Hoy'] is not None:
                                if item['RSI_Hoy'] > 70:
                                    indi_html += f"<span class='indicator-box rsi-overbought'>RSI: Sobrecompra</span>"
                                elif item['RSI_Hoy'] < 30:
                                    indi_html += f"<span class='indicator-box rsi-oversold'>RSI: Sobreventa</span>"

                            # MACD (Cruce de la Señal)
                            # Cruce Alcista (MACD Histograma pasa de Negativo a Positivo)
                            if item['MACD_Hist_Ayer'] < 0 and item['MACD_Hist_Hoy'] > 0:
                                indi_html += f"<span class='indicator-box macd-buy'>MACD: Cruce Alcista</span>"
                            # Cruce Bajista (MACD Histograma pasa de Positivo a Negativo)
                            elif item['MACD_Hist_Ayer'] > 0 and item['MACD_Hist_Hoy'] < 0:
                                indi_html += f"<span class='indicator-box macd-sell'>MACD: Cruce Bajista</span>"
                                
                            if indi_html:
                                st.markdown(indi_html, unsafe_allow_html=True)
                                
                            
                            # Métrica de precio y variación
                            st.metric(
                                label="Precio Actual",
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
                                clave_sesion = f"msg_{item['Nombre']}_{datetime.now().hour}"
                                if clave_sesion not in st.session_state:
                                     enviar_telegram(f"⚠️ *ALERTA*: {item['Nombre']} se mueve un {item['Var']:.2f}%")
                                     st.session_state[clave_sesion] = True
                                
    # --- RECARGA AUTOMÁTICA ---
    time.sleep(60) 
    st.rerun()
