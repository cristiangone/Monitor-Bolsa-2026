import yfinance as yf
import pandas as pd
import time
import requests  # Nueva librería para conectar con Telegram
from datetime import datetime
from colorama import init, Fore, Back, Style
import os
import platform

# Inicializar colores
init(autoreset=True)

# --- TUS CREDENCIALES DE TELEGRAM ---
# Reemplaza esto con lo que te dio @BotFather y @userinfobot
# --- CONFIGURACIÓN DE TELEGRAM (¡PON TUS DATOS AQUÍ!) ---
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
ARCHIVO_LOG = "bitacora_mercado.txt"

TICKERS = {
    # Macro
    "USD/CLP": "CLP=X",
    "Cobre (Futuros)": "HG=F",
    "Petróleo WTI": "CL=F",
    "Petróleo Brent": "BZ=F",
    # Acciones Chile
    "LATAM Airlines": "LTM.SN",
    "Falabella": "FALABELLA.SN",
    "Socovesa": "SOCOVESA.SN",
    "Banco de Chile": "CHILE.SN",
    "Cencosud": "CENCOSUD.SN",
    "Mallplaza": "MALLPLAZA.SN",
    "Ripley": "RIPLEY.SN"
}

UF_VALOR_REF = 38500.00 

def limpiar_pantalla():
    os.system('cls' if os.name == 'nt' else 'clear')

def enviar_telegram(mensaje):
    """Envía notificación al celular"""
    if TELEGRAM_TOKEN == "PEGA_AQUI_TU_TOKEN_DEL_BOTFATHER":
        return # No enviamos nada si no está configurado

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensaje,
        "parse_mode": "Markdown" # Para usar negritas
    }
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"{Fore.YELLOW}[W] Error enviando Telegram: {e}{Style.RESET_ALL}")

def sonar_alarma():
    sistema = platform.system()
    try:
        if sistema == "Windows":
            import winsound
            winsound.Beep(1000, 200)
        else:
            print('\a')
    except:
        pass 

def registrar_evento(item):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Emoji según movimiento
    emoji = "🚀" if item['Cambio_Pct'] > 0 else "🔻"
    tipo = "ALZA FUERTE" if item['Cambio_Pct'] > 0 else "CAIDA FUERTE"

    # Texto para el Log
    log_msg = (f"[{timestamp}] {tipo}: {item['Activo']} ({item['Simbolo']}) "
               f"| Precio: {item['Precio']:.2f} | Var: {item['Cambio_Pct']:.2f}%\n")
    
    # Texto para Telegram (Formato Markdown)
    tele_msg = (f"{emoji} *ALERTA DE MERCADO* {emoji}\n\n"
                f"*Activo:* {item['Activo']}\n"
                f"*Precio:* ${item['Precio']:,.2f}\n"
                f"*Variación:* {item['Cambio_Pct']:+.2f}%\n"
                f"⏰ {timestamp}")

    # 1. Guardar en disco
    try:
        with open(ARCHIVO_LOG, "a", encoding="utf-8") as f:
            f.write(log_msg)
    except Exception as e:
        print(f"Error Log: {e}")

    # 2. Enviar al Celular
    print(f"{Fore.YELLOW}>> Enviando alerta a Telegram...{Style.RESET_ALL}")
    enviar_telegram(tele_msg)

def obtener_datos():
    data_list = []
    alertas_activas = False
    
    tickers_list = list(TICKERS.values())
    try:
        data = yf.download(tickers_list, period="1d", interval="1m", progress=False)['Close']
    except Exception:
        return [], False

    for nombre, symbol in TICKERS.items():
        try:
            ticker = yf.Ticker(symbol)
            todays_data = ticker.history(period="1d")
            
            if not todays_data.empty:
                current_price = todays_data['Close'].iloc[-1]
                open_price = todays_data['Open'].iloc[0]
                
                change = current_price - open_price
                pct_change = (change / open_price) * 100
                
                es_volatil = abs(pct_change) >= UMBRAL_ALERTA
                
                item = {
                    "Activo": nombre,
                    "Precio": current_price,
                    "Cambio_Pct": pct_change,
                    "Simbolo": symbol,
                    "Alerta": es_volatil
                }

                if es_volatil:
                    alertas_activas = True
                    # Aquí llamamos al registro y notificación
                    registrar_evento(item)

                data_list.append(item)
            else:
                data_list.append({"Activo": nombre, "Precio": 0.0, "Cambio_Pct": 0.0, "Simbolo": symbol, "Alerta": False})
                
        except Exception:
            continue
            
    return data_list, alertas_activas

def imprimir_tabla(datos, hay_alerta):
    limpiar_pantalla()
    ahora = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    
    header_color = Fore.RED if hay_alerta else Fore.CYAN
    estado_msg = "¡ALERTA!" if hay_alerta else "CONECTADO"
    
    print(f"{Style.BRIGHT}{header_color}=== MONITOR BOLSA CHILE BOT V4 [{estado_msg}] ==={Style.RESET_ALL}")
    print(f"Telegram: {'ACTIVADO' if TELEGRAM_TOKEN != 'PEGA_AQUI_TU_TOKEN_DEL_BOTFATHER' else 'DESACTIVADO'}")
    print("-" * 75)
    print(f"{'ACTIVO':<20} | {'PRECIO':<15} | {'VARIACIÓN 24H':<15} | {'ESTADO':<10}")
    print("-" * 75)

    for item in datos:
        render_fila(item)

    print("-" * 75)
    
    if hay_alerta:
        print(f"\n{Back.RED}{Fore.WHITE} NOTIFICACIÓN ENVIADA AL MÓVIL {Style.RESET_ALL}")
        sonar_alarma()

def render_fila(item):
    precio_fmt = f"{item['Precio']:,.2f}"
    if "CLP=X" in item['Simbolo']: precio_fmt = f"$ {item['Precio']:,.2f} CLP"
    elif "HG=F" in item['Simbolo']: precio_fmt = f"$ {item['Precio']:,.2f} USD"
    
    pct = item['Cambio_Pct']
    alerta = item['Alerta']
    
    if alerta:
        if pct > 0:
            estilo = f"{Back.GREEN}{Fore.BLACK}"
            estado = "¡ALZA!"
        else:
            estilo = f"{Back.RED}{Fore.WHITE}"
            estado = "¡CAIDA!"
        print(f"{estilo}{item['Activo']:<20} | {precio_fmt:<15} | {pct:+.2f}%{' '*9} | {estado:<10}{Style.RESET_ALL}")
    else:
        color_pct = Fore.GREEN if pct > 0 else (Fore.RED if pct < 0 else Fore.WHITE)
        signo = "+" if pct > 0 else ""
        print(f"{item['Activo']:<20} | {precio_fmt:<15} | {color_pct}{signo}{pct:.2f}%{Style.RESET_ALL}{' '*9} | OK")

if __name__ == "__main__":
    print("Iniciando Bot de Monitoreo...")
    # Pequeño chequeo de seguridad
    if TELEGRAM_TOKEN == "PEGA_AQUI_TU_TOKEN_DEL_BOTFATHER":
        print(f"{Fore.YELLOW}ADVERTENCIA: No has configurado el Token de Telegram. El script correrá solo en modo local.{Style.RESET_ALL}")
        time.sleep(3)

    try:
        while True:
            datos, alerta = obtener_datos()
            imprimir_tabla(datos, alerta)
            time.sleep(60) 
    except KeyboardInterrupt:
        print("\nMonitor detenido.")

