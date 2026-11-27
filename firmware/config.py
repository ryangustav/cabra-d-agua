# =====================================================================
#  EcoMangue - Configuracao da boia (MicroPython / ESP32)
#  Edite APENAS este arquivo para adaptar a boia (Wokwi ou hardware real).
# =====================================================================

# ---------------------------------------------------------------------
# MODO DE OPERACAO
#   True  = Wokwi: potenciometros/sliders mapeados direto em unidades
#   False = Hardware real: curvas dos sensores (SEN0189 / PH-4502C / TDS / MQ)
# ---------------------------------------------------------------------
WOKWI_SIMULATION = True

# ---------------------------------------------------------------------
# WI-FI
# ---------------------------------------------------------------------
if WOKWI_SIMULATION:
    WIFI_SSID = "Wokwi-GUEST"   # rede aberta do simulador
    WIFI_PASSWORD = ""
else:
    WIFI_SSID = "SUA_REDE"
    WIFI_PASSWORD = "SUA_SENHA"

# ---------------------------------------------------------------------
# THINGSPEAK (graficos em tempo real - 8 campos)
#   1. Crie conta em https://thingspeak.mathworks.com
#   2. New Channel -> ative Field 1..8 -> Save
#   3. Aba "API Keys" -> copie a "Write API Key" e cole abaixo
#   Sem chave, a boia funciona normalmente e mostra tudo no Serial.
# ---------------------------------------------------------------------
THINGSPEAK_API_KEY = "COLE_SUA_WRITE_API_KEY"
THINGSPEAK_URL = "http://api.thingspeak.com/update"
# field1 = Turbidez (NTU)         field2 = pH
# field3 = Temperatura (C)        field4 = Profundidade / Nivel (cm)
# field5 = Oxigenio Diss. (mg/L)  field6 = TDS / Salinidade (ppm)
# field7 = Gases / Odor (ppm)     field8 = Score de Anomalia (>=3.0 = ALERTA)

# ---------------------------------------------------------------------
# IDENTIFICACAO E GEOLOCALIZACAO DA BOIA (estacionaria -> sem GPS)
#   Coordenada aproximada do Rio Poxim junto a Farolandia (Aracaju/SE).
# ---------------------------------------------------------------------
BUOY_ID = "ECOMANGUE-01"
BUOY_LAT = -10.973500
BUOY_LON = -37.062000

# ---------------------------------------------------------------------
# HORA (NTP) - carimbo de tempo das evidencias
# ---------------------------------------------------------------------
NTP_SERVER = "pool.ntp.org"
TZ_OFFSET_SEC = -3 * 3600       # UTC-3 (Sergipe)
TZ_ISO_SUFFIX = "-03:00"

# ---------------------------------------------------------------------
# TEMPOS E RECURSOS LOCAIS
# ---------------------------------------------------------------------
SAMPLE_INTERVAL_MS = 2000       # leitura + fusao na borda
SEND_INTERVAL_NORMAL_MS = 20000 # envio em condicao normal
SEND_INTERVAL_ALERT_MS = 15000  # envio em alerta (minimo ThingSpeak gratis)
SEND_INTERVAL_POWERSAVE_MS = 60000  # economia se bateria baixa sem sol
ENABLE_BUZZER = True            # True = beep curto ao entrar/sair de alerta
ENABLE_SPILL_BUTTON = True      # True = botao vermelho / tecla D simula despejo

# ---------------------------------------------------------------------
# PAINEL SOLAR + BATERIA LiPo (sustentacao autonoma)
#   Wokwi: wokwi-photoresistor-sensor simula irradiancia solar no painel;
#          quando ha sol (DO == LOW), o carregador virtual recarrega e
#          sustenta a LiPo em ~4.20 V (girar pot3 continua ajustando manual).
# ---------------------------------------------------------------------
ENABLE_SOLAR_SIM = True         # True = simula carga/descarga LiPo no Wokwi
BAT_FULL_V = 4.20               # LiPo 100% carregada (flutuacao)
SOLAR_CHARGE_STEP_V = 0.025     # ganho de tensao por ciclo (2 s) com sol
BAT_DISCHARGE_NORMAL_V = 0.005  # descarga por ciclo (2 s) sem sol (noite)
BAT_DISCHARGE_ALERT_V = 0.010   # descarga em alerta ativo (envio a 15 s)

# ---------------------------------------------------------------------
# PROFUNDIDADE / NIVEL (HC-SR04 no Wokwi / JSN-SR04T a prova d'agua no real)
#   DEPTH_MOUNT_HEIGHT_CM = 0.0 -> leitura direta (2..400 cm)
#   DEPTH_MOUNT_HEIGHT_CM > 0.0 -> sensor fixo acima do rio (ex: 350.0):
#                                  lamina = altura_montagem - distancia
# ---------------------------------------------------------------------
DEPTH_MOUNT_HEIGHT_CM = 0.0
DEPTH_MIN_VALID_CM = 2.0
DEPTH_MAX_VALID_CM = 400.0
DEPTH_PINGS = 3
DEPTH_TIMEOUT_US = 30000

# ---------------------------------------------------------------------
# DETECCAO DE ANOMALIA (CONAMA 357 + Picos Estatisticos EWMA)
# ---------------------------------------------------------------------
PH_MIN = 6.5
PH_MAX = 8.5
DO_MIN_MG_L = 5.0               # abaixo disso: hipoxia (CONAMA 357 salobra C1)
TURBIDITY_MAX_NTU = 100.0
TDS_MAX_PPM = 1400.0
DEPTH_MIN_CM = 60.0             # abaixo disso: assoreamento / entulho
DEPTH_MAX_CM = 320.0            # acima disso: cheia / descarga volumosa
GAS_MAX_PPM = 1050.0            # acima disso (ou DOUT LOW): mau cheiro / H2S / CH4
BAT_LOW_V = 3.35                # aviso de manutencao da bateria LiPo

Z_THRESHOLD = 3.0               # desvios-padrao acima da linha de base
EWMA_ALPHA = 0.10               # taxa de aprendizado da linha de base
WARMUP_SAMPLES = 10             # leituras iniciais de aprendizado (~20 s)
CLEAR_SAMPLES = 3               # leituras normais seguidas para encerrar alerta

# Desvio-padrao minimo por sensor (evita alarme falso em sinal muito estavel)
MIN_STD_TURBIDITY = 10.0        # NTU
MIN_STD_PH = 0.15
MIN_STD_DO = 0.40               # mg/L
MIN_STD_TEMP = 0.50             # C
MIN_STD_DEPTH = 8.0             # cm
MIN_STD_TDS = 35.0              # ppm
MIN_STD_GAS = 40.0              # ppm

# ---------------------------------------------------------------------
# DEMO: botao "simular despejo clandestino"
# ---------------------------------------------------------------------
SPILL_DURATION_MS = 30000
SPILL_TURBIDITY_ADD = 350.0     # NTU no pico
SPILL_PH_DROP = 1.8             # queda de pH no pico
SPILL_DO_DROP = 4.2             # queda de OD (mg/L) por consumo organico (DBO)
SPILL_TEMP_ADD = 2.5            # C no pico (efluente mais quente)
SPILL_TDS_ADD = 480.0           # ppm (sais e detergentes)
SPILL_GAS_ADD = 360.0           # ppm (H2S / CH4)
SPILL_DEPTH_ADD = 20.0          # cm (onda de descarga)

# ---------------------------------------------------------------------
# CALIBRACAO E FILTRO (Wokwi vs Hardware Real)
# ---------------------------------------------------------------------
ADC_VREF = 3.3
ADC_SAMPLES = 15                # amostras para filtro mediano aparado
ADC_TRIM_COUNT = 3              # descarta 3 menores e 3 maiores

TURBIDITY_DIVIDER = 1.5         # divisor 10k/20k
PH_DIVIDER = 1.5                # divisor 10k/20k
GAS_DIVIDER = 1.5               # divisor 10k/20k (MQ-135/MQ-4 opera em 5V)
BATTERY_DIVIDER = 2.0           # divisor 100k/100k

PH_NEUTRAL_VOLTAGE = 2.50       # tensao em pH 7 a 25 C
PH_SLOPE = 0.18                 # V/pH a 25 C (compensado por temp)
TDS_FACTOR = 0.5                # fator classico TDS = 0.5 * EC
DO_CAL_VOLTAGE = 2.10           # tensao da sonda SEN0237 saturada (calibrar!)
DO_CAL_TEMP_C = 25.0            # temperatura da calibracao em agua saturada

# Faixas dos componentes no Wokwi
WOKWI_TURBIDITY_MAX = 1000.0    # NTU
WOKWI_DO_MAX = 12.0             # mg/L
WOKWI_TDS_MAX = 2000.0          # ppm
WOKWI_GAS_MAX = 1000.0          # ppm (alem de DOUT para >3.3V)
WOKWI_BAT_MIN = 3.0             # V
WOKWI_BAT_MAX = 4.2             # V
