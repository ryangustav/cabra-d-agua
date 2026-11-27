"""
EcoMangue - Boia de vigilancia ambiental do Rio Poxim (Farolandia)
MicroPython / ESP32

Sensores:
  - Turbidez (GPIO 34 / ADC1)
  - pH (GPIO 35 / ADC1, com compensacao termica de Nernst no hardware real)
  - Oxigenio Dissolvido / OD (GPIO 39 / VN / ADC1, saturacao por temp/salinidade)
  - TDS / Salinidade (GPIO 32 / ADC1, compensado a 25 C)
  - Bateria LiPo/Solar (GPIO 33 / ADC1)
  - Gases / Mau cheiro MQ (AOUT GPIO 36 / VP + DOUT GPIO 19)
  - Temperatura da agua DS18B20 (GPIO 4, 1-Wire assincrono)
  - Profundidade / Nivel HC-SR04 / JSN-SR04T (TRIG GPIO 17, ECHO GPIO 18)
  - Placa Solar + Carregador (DO/CHRG GPIO 14, LED Solar GPIO 23)

Toda configuracao fica em config.py
"""

import gc
import math
import time
import network
import ntptime
import onewire
import ds18x20
from machine import ADC, PWM, Pin, time_pulse_us

try:
    import urequests as requests
except ImportError:
    import requests

import config

# ---------------- Pinos (analogicos apenas em ADC1: GPIO 32-39) ----------------
PIN_TURBIDITY = 34
PIN_PH = 35
PIN_DO = 39            # esp:VN no diagram.json (Oxigenio Dissolvido)
PIN_TDS = 32
PIN_BATTERY = 33
PIN_GAS_AOUT = 36      # esp:VP no diagram.json
PIN_GAS_DOUT = 19      # comparador digital de gas/odor
PIN_DS18B20 = 4
PIN_DEPTH_TRIG = 17
PIN_DEPTH_ECHO = 18
PIN_SOLAR_OK = 14      # placa solar / pino CHRG (LOW = gerando carga)
PIN_BUTTON = 15        # simular despejo (PULL_UP)
PIN_BUZZER = 25
PIN_LED_OK = 27
PIN_LED_ALERT = 26
PIN_LED_SOLAR = 23     # LED azul: placa solar sustentando/carregando


def clamp(val, lo, hi):
    if val < lo:
        return lo
    if val > hi:
        return hi
    return val


class Baseline:
    """Linha de base EWMA (media e variancia moveis exponenciais) por sensor."""

    def __init__(self, min_std):
        self.mean = 0.0
        self.var = 0.0
        self.min_std = min_std
        self.count = 0

    def update(self, x):
        if self.count == 0:
            self.mean = x
            self.var = 0.0
        else:
            diff = x - self.mean
            incr = config.EWMA_ALPHA * diff
            self.mean += incr
            self.var = (1.0 - config.EWMA_ALPHA) * (self.var + diff * incr)
        self.count += 1

    def ready(self):
        return self.count >= config.WARMUP_SAMPLES

    def stddev(self):
        sd = math.sqrt(self.var) if self.var > 0.0 else 0.0
        return sd if sd >= self.min_std else self.min_std

    def zscore(self, x):
        if not self.ready():
            return 0.0
        return abs(x - self.mean) / self.stddev()


class BuoyHardware:
    """Encapsula pinos, ADCs, DS18B20, HC-SR04, painel solar, LEDs e buzzer."""

    def __init__(self):
        self.adc_turb = self._make_adc(PIN_TURBIDITY)
        self.adc_ph = self._make_adc(PIN_PH)
        self.adc_do = self._make_adc(PIN_DO)
        self.adc_tds = self._make_adc(PIN_TDS)
        self.adc_bat = self._make_adc(PIN_BATTERY)
        self.adc_gas = self._make_adc(PIN_GAS_AOUT)

        self.gas_dout = Pin(PIN_GAS_DOUT, Pin.IN)
        self.solar_ok = Pin(PIN_SOLAR_OK, Pin.IN)
        self.depth_trig = Pin(PIN_DEPTH_TRIG, Pin.OUT, value=0)
        self.depth_echo = Pin(PIN_DEPTH_ECHO, Pin.IN)
        self.button = Pin(PIN_BUTTON, Pin.IN, Pin.PULL_UP)
        self.led_ok = Pin(PIN_LED_OK, Pin.OUT, value=0)
        self.led_alert = Pin(PIN_LED_ALERT, Pin.OUT, value=0)
        self.led_solar = Pin(PIN_LED_SOLAR, Pin.OUT, value=0)

        self.buzzer = None
        self.buzzer_off_at = None
        if config.ENABLE_BUZZER:
            try:
                self.buzzer = PWM(Pin(PIN_BUZZER), freq=1800)
                self._set_pwm_duty(0)
            except Exception:
                self.buzzer = None

        self.ds = ds18x20.DS18X20(onewire.OneWire(Pin(PIN_DS18B20)))
        self.roms = []
        self.last_valid_temp = 27.0
        self.last_valid_depth = 180.0
        self.sim_bat_v = None
        self._last_pot_bat_v = None
        self.temp_conv_at = None
        self._init_ds18b20()

    @staticmethod
    def _make_adc(pin_num):
        adc = ADC(Pin(pin_num))
        adc.atten(ADC.ATTN_11DB)
        return adc

    def _set_pwm_duty(self, duty_u16):
        if self.buzzer is None:
            return
        if hasattr(self.buzzer, "duty_u16"):
            self.buzzer.duty_u16(duty_u16)
        else:
            self.buzzer.duty(duty_u16 >> 6)

    def beep(self, freq=1800, duration_ms=180):
        if self.buzzer is None:
            return
        try:
            self.buzzer.freq(freq)
            self._set_pwm_duty(32768)
            self.buzzer_off_at = time.ticks_add(time.ticks_ms(), duration_ms)
        except Exception:
            pass

    def update_buzzer(self, now):
        if self.buzzer_off_at is not None and time.ticks_diff(now, self.buzzer_off_at) >= 0:
            self._set_pwm_duty(0)
            self.buzzer_off_at = None

    def silence(self):
        self.led_ok.value(0)
        self.led_alert.value(0)
        self.led_solar.value(0)
        self._set_pwm_duty(0)

    def _init_ds18b20(self):
        try:
            self.roms = self.ds.scan()
            if self.roms:
                self.ds.convert_temp()
                time.sleep_ms(750)
                t = self.ds.read_temp(self.roms[0])
                if -40.0 < t < 85.0:
                    self.last_valid_temp = t
                self.ds.convert_temp()
                self.temp_conv_at = time.ticks_ms()
        except Exception:
            self.roms = []

    def read_voltage_filtered(self, adc):
        """Filtro mediano aparado: rejeita picos eletricos e ruido de Wi-Fi."""
        samples = []
        has_u16 = hasattr(adc, "read_u16")
        for _ in range(config.ADC_SAMPLES):
            samples.append(adc.read_u16() if has_u16 else adc.read() * 16)
            time.sleep_us(100)
        samples.sort()
        trim = config.ADC_TRIM_COUNT
        core = samples[trim:len(samples) - trim]
        mean_u16 = sum(core) / len(core)
        ok = True if config.WOKWI_SIMULATION else (250 < mean_u16 < 65250)
        return (mean_u16 / 65535.0) * config.ADC_VREF, ok

    def read_temperature(self):
        try:
            if not self.roms:
                self.roms = self.ds.scan()
                if not self.roms:
                    return self.last_valid_temp, False
                self.ds.convert_temp()
                self.temp_conv_at = time.ticks_ms()
                return self.last_valid_temp, True

            if self.temp_conv_at is None or time.ticks_diff(time.ticks_ms(), self.temp_conv_at) < 750:
                return self.last_valid_temp, True

            t = self.ds.read_temp(self.roms[0])
            self.ds.convert_temp()
            self.temp_conv_at = time.ticks_ms()
            if -40.0 < t < 85.0:
                self.last_valid_temp = t
                return t, True
        except Exception:
            self.roms = []
            self.temp_conv_at = None
        return self.last_valid_temp, False

    def read_turbidity(self):
        v, ok = self.read_voltage_filtered(self.adc_turb)
        if config.WOKWI_SIMULATION:
            return (v / config.ADC_VREF) * config.WOKWI_TURBIDITY_MAX, ok
        v_real = clamp(v * config.TURBIDITY_DIVIDER, 2.5, 4.2)
        ntu = -1120.4 * v_real * v_real + 5742.3 * v_real - 4352.9
        return max(ntu, 0.0), ok

    def read_ph(self, temp_c):
        v, ok = self.read_voltage_filtered(self.adc_ph)
        if config.WOKWI_SIMULATION:
            return (v / config.ADC_VREF) * 14.0, ok
        v_real = v * config.PH_DIVIDER
        temp_factor = (temp_c + 273.15) / 298.15
        slope_t = config.PH_SLOPE * temp_factor
        return clamp(7.0 + (config.PH_NEUTRAL_VOLTAGE - v_real) / slope_t, 0.0, 14.0), ok

    def read_tds(self, temp_c):
        v, ok = self.read_voltage_filtered(self.adc_tds)
        comp = max(1.0 + 0.02 * (temp_c - 25.0), 0.5)  # 2%/C ref 25 C
        if config.WOKWI_SIMULATION:
            tds_raw = (v / config.ADC_VREF) * config.WOKWI_TDS_MAX
            return max(tds_raw / comp, 0.0), ok
        v_comp = v / comp
        tds = (133.42 * v_comp ** 3 - 255.86 * v_comp ** 2 + 857.39 * v_comp) * config.TDS_FACTOR
        return max(tds, 0.0), ok

    def read_do(self, temp_c, tds_ppm):
        v, ok = self.read_voltage_filtered(self.adc_do)
        if config.WOKWI_SIMULATION:
            return (v / config.ADC_VREF) * config.WOKWI_DO_MAX, ok
        # Sonda analogica (ex: SEN0237): calibracao 1 ponto contra saturacao em T
        sat_now = do_sat_mg_l(temp_c, tds_ppm)
        do_val = (v / max(config.DO_CAL_VOLTAGE, 0.1)) * sat_now
        return clamp(do_val, 0.0, 20.0), ok

    def read_depth_cm(self):
        valid = []
        for i in range(config.DEPTH_PINGS):
            self.depth_trig.value(0)
            time.sleep_us(2)
            self.depth_trig.value(1)
            time.sleep_us(10)
            self.depth_trig.value(0)

            us = time_pulse_us(self.depth_echo, 1, config.DEPTH_TIMEOUT_US)
            if us > 0:
                dist = us / 58.0
                if config.DEPTH_MIN_VALID_CM <= dist <= config.DEPTH_MAX_VALID_CM:
                    valid.append(dist)
            if i + 1 < config.DEPTH_PINGS:
                time.sleep_ms(15)

        if not valid:
            return self.last_valid_depth, False

        valid.sort()
        dist = valid[len(valid) // 2]  # mediana descarta ecos falsos
        depth = (
            max(config.DEPTH_MOUNT_HEIGHT_CM - dist, 0.0)
            if config.DEPTH_MOUNT_HEIGHT_CM > 0.0
            else dist
        )
        self.last_valid_depth = depth
        return depth, True

    def read_gas(self):
        v, ok = self.read_voltage_filtered(self.adc_gas)
        digital_alarm = (self.gas_dout.value() == 0)
        if config.WOKWI_SIMULATION:
            ppm = (v / config.ADC_VREF) * config.WOKWI_GAS_MAX
        else:
            v_real = v * config.GAS_DIVIDER
            ppm = (v_real / 5.0) * 2000.0
        # Garante disparo caso AOUT passe de 3.3 V (saturacao do ADC)
        if digital_alarm:
            ppm = max(ppm, config.GAS_MAX_PPM + 250.0)
        return ppm, digital_alarm, ok

    def read_power(self, alert_active=False):
        """Le bateria LiPo e estado da placa solar; simula carga/sustentacao no Wokwi."""
        v, _ = self.read_voltage_filtered(self.adc_bat)
        solar_active = (self.solar_ok.value() == 0)

        if config.WOKWI_SIMULATION:
            pot_v = config.WOKWI_BAT_MIN + (v / config.ADC_VREF) * (
                config.WOKWI_BAT_MAX - config.WOKWI_BAT_MIN
            )
            if config.ENABLE_SOLAR_SIM:
                if self.sim_bat_v is None:
                    self.sim_bat_v = pot_v
                    self._last_pot_bat_v = pot_v
                elif abs(pot_v - self._last_pot_bat_v) > 0.08:
                    # Permite ajuste manual imediato pelo potenciometro na bancada
                    self.sim_bat_v = pot_v
                    self._last_pot_bat_v = pot_v
                elif solar_active:
                    self.sim_bat_v = min(config.BAT_FULL_V, self.sim_bat_v + config.SOLAR_CHARGE_STEP_V)
                else:
                    step = config.BAT_DISCHARGE_ALERT_V if alert_active else config.BAT_DISCHARGE_NORMAL_V
                    self.sim_bat_v = max(config.WOKWI_BAT_MIN, self.sim_bat_v - step)
                bat_v = self.sim_bat_v
            else:
                bat_v = pot_v
        else:
            bat_v = v * config.BATTERY_DIVIDER

        if solar_active:
            solar_state = "SUSTENT" if bat_v >= (config.BAT_FULL_V - 0.02) else "CARREG"
        else:
            solar_state = "BATERIA"
        return bat_v, solar_active, solar_state


# ---------------- Utilitarios ambientais e de rede ----------------
def do_sat_mg_l(temp_c, tds_ppm=0.0):
    """Saturacao de Oxigenio Dissolvido (mg/L) em funcao da temperatura e salinidade."""
    t = clamp(temp_c, 0.0, 45.0)
    sat_fresh = 14.62 - 0.3898 * t + 0.006969 * t * t - 5.897e-5 * t * t * t
    sal_factor = clamp(1.0 - tds_ppm * 5.5e-6, 0.75, 1.0)
    return max(sat_fresh * sal_factor, 1.0)


def do_sat_percent(do_mg_l, temp_c, tds_ppm=0.0):
    return round(clamp((do_mg_l / do_sat_mg_l(temp_c, tds_ppm)) * 100.0, 0.0, 200.0))


def battery_percent(v):
    return round(clamp((v - 3.30) / (4.20 - 3.30) * 100.0, 0.0, 100.0))


def compute_iqa(r):
    pen = 0.0
    pen += clamp((7.0 - r["do_mg_l"]) / 5.0 * 30.0, 0.0, 30.0)
    pen += clamp((r["turbidity"] - 5.0) / 100.0 * 25.0, 0.0, 25.0)
    pen += clamp((abs(r["ph"] - 7.2) - 0.5) / 1.5 * 20.0, 0.0, 20.0)
    pen += clamp((r["tds"] - 400.0) / 600.0 * 12.0, 0.0, 12.0)
    pen += clamp((r["gas_ppm"] - 300.0) / 500.0 * 8.0, 0.0, 8.0)
    pen += clamp((abs(r["temperature"] - 26.0) - 2.0) / 6.0 * 5.0, 0.0, 5.0)
    return round(clamp(100.0 - pen, 0.0, 100.0))


def iqa_label(iqa):
    if iqa >= 80:
        return "OTIMA"
    if iqa >= 60:
        return "BOA"
    if iqa >= 40:
        return "REGULAR"
    if iqa >= 20:
        return "RUIM"
    return "CRITICA"


def depth_trend(depth_cm, base_depth):
    if not base_depth.ready():
        return "--"
    delta = depth_cm - base_depth.mean
    if delta > 6.0:
        return "ENCHENDO"
    if delta < -6.0:
        return "VAZANDO"
    return "ESTAVEL"


def health_summary(health):
    labels = (
        ("temp", "TEMP"),
        ("depth", "PROF"),
        ("turb", "TURB"),
        ("ph", "PH"),
        ("do", "OD"),
        ("tds", "TDS"),
        ("gas", "GAS"),
    )
    return " ".join(tag for key, tag in labels if not health[key])


def url_encode(text):
    safe = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_.~"
    out = []
    for b in text.encode("utf-8"):
        ch = chr(b)
        if ch in safe:
            out.append(ch)
        else:
            out.append("%{:02X}".format(b))
    return "".join(out)


def time_synced():
    return time.localtime()[0] >= 2024


def iso_timestamp():
    if not time_synced():
        return ""
    tm = time.localtime(time.time() + config.TZ_OFFSET_SEC)
    return "{:04d}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}{}".format(
        tm[0], tm[1], tm[2], tm[3], tm[4], tm[5], config.TZ_ISO_SUFFIX
    )


def human_timestamp():
    if not time_synced():
        return "--/-- --:--:--"
    tm = time.localtime(time.time() + config.TZ_OFFSET_SEC)
    return "{:02d}/{:02d} {:02d}:{:02d}:{:02d}".format(
        tm[2], tm[1], tm[3], tm[4], tm[5]
    )


def sync_ntp():
    try:
        ntptime.host = config.NTP_SERVER
        ntptime.settime()
        print("[NTP] Hora sincronizada:", human_timestamp())
        return True
    except Exception:
        return False


def thingspeak_configured():
    return bool(config.THINGSPEAK_API_KEY) and config.THINGSPEAK_API_KEY != "COLE_SUA_WRITE_API_KEY"


class EcoMangueApp:
    def __init__(self):
        self.hw = BuoyHardware()
        self.wlan = network.WLAN(network.STA_IF)

        self.bases = {
            "turb": Baseline(config.MIN_STD_TURBIDITY),
            "ph": Baseline(config.MIN_STD_PH),
            "do": Baseline(config.MIN_STD_DO),
            "temp": Baseline(config.MIN_STD_TEMP),
            "depth": Baseline(config.MIN_STD_DEPTH),
            "tds": Baseline(config.MIN_STD_TDS),
            "gas": Baseline(config.MIN_STD_GAS),
        }

        self.alert_active = False
        self.pending_recovery = False
        self.solar_active = False
        self.normal_streak = 0
        self.sample_count = 0
        self.event_count = 0

        self.last_sample_ms = 0
        self.last_send_ms = None
        self.last_wifi_try = 0
        self.last_ntp_try = 0

        self.spill_active = False
        self.spill_start_ms = 0

        self._btn_stable = 1
        self._btn_last_raw = 1
        self._btn_changed_at = 0

        self.last_reading = None
        self.last_score = 0.0
        self.last_iqa = 100
        self.last_iso = ""

        self.window_has_alert = False
        self.window_peak_score = 0.0
        self.window_peak_iqa = 100
        self.window_peak_reading = None
        self.window_peak_tag = ""
        self.window_peak_reason = ""
        self.window_peak_iso = ""
        self.window_peak_human = ""

    def print_banner(self):
        print()
        print("======================================================")
        print("  EcoMangue v2 (MicroPython) - Rio Poxim / Farolandia")
        print("======================================================")
        print("  Boia:     {}".format(config.BUOY_ID))
        print("  Local:    {:.6f}, {:.6f}".format(config.BUOY_LAT, config.BUOY_LON))
        print("  Modo:     {}".format("Wokwi (simulacao)" if config.WOKWI_SIMULATION else "Hardware real"))
        print("  Sensores: Turbidez + pH + OD + Temp + Prof + TDS + Gas")
        print("  Energia:  Painel Solar + LiPo (carga e economia auto)")
        print("  Nuvem:    {}".format("ThingSpeak (8 campos)" if thingspeak_configured() else "desativada (sem API key)"))
        print("  Demo:     botao vermelho ou tecla D = despejo")
        print("======================================================")

    def connect_wifi(self):
        print("[NET] Conectando a {}".format(config.WIFI_SSID), end="")
        self.wlan.active(True)
        if not self.wlan.isconnected():
            self.wlan.connect(config.WIFI_SSID, config.WIFI_PASSWORD)
            start = time.ticks_ms()
            while not self.wlan.isconnected() and time.ticks_diff(time.ticks_ms(), start) < 15000:
                print(".", end="")
                time.sleep_ms(250)
        if self.wlan.isconnected():
            print(" conectado! IP", self.wlan.ifconfig()[0])
        else:
            print(" falhou (seguindo offline, tentando de novo depois)")
        self.last_wifi_try = time.ticks_ms()

    def maintain_network(self, now):
        if not self.wlan.isconnected():
            if time.ticks_diff(now, self.last_wifi_try) >= 10000:
                self.last_wifi_try = now
                print("[NET] Wi-Fi desconectado, reconectando...")
                try:
                    self.wlan.disconnect()
                except Exception:
                    pass
                try:
                    self.wlan.connect(config.WIFI_SSID, config.WIFI_PASSWORD)
                except Exception:
                    pass
            return

        if not time_synced() and time.ticks_diff(now, self.last_ntp_try) >= 30000:
            self.last_ntp_try = now
            sync_ntp()

    def check_button(self, now):
        if not config.ENABLE_SPILL_BUTTON:
            return
        raw = self.hw.button.value()
        if raw != self._btn_last_raw:
            self._btn_last_raw = raw
            self._btn_changed_at = now
        if time.ticks_diff(now, self._btn_changed_at) > 30 and raw != self._btn_stable:
            self._btn_stable = raw
            if self._btn_stable == 0:
                self.spill_active = True
                self.spill_start_ms = now
                print("\n>> [DEMO] Despejo clandestino simulado! Pluma de esgoto + odor + queda de OD...")

    def update_leds(self, now):
        self.solar_active = (self.hw.solar_ok.value() == 0)
        self.hw.led_solar.value(1 if self.solar_active else 0)
        if self.alert_active:
            self.hw.led_alert.value((now // 250) % 2)
            self.hw.led_ok.value(0)
        elif self.sample_count < config.WARMUP_SAMPLES:
            self.hw.led_alert.value(0)
            self.hw.led_ok.value((now // 500) % 2)
        else:
            self.hw.led_alert.value(0)
            self.hw.led_ok.value(1)

    def apply_spill(self, r, now):
        if not self.spill_active:
            return
        elapsed = time.ticks_diff(now, self.spill_start_ms)
        if elapsed >= config.SPILL_DURATION_MS:
            self.spill_active = False
            print(">> [DEMO] Pluma de despejo dispersou.")
            return
        t = elapsed / config.SPILL_DURATION_MS
        intensity = (t / 0.15) if t < 0.15 else (1.0 - (t - 0.15) / 0.85)
        r["turbidity"] += config.SPILL_TURBIDITY_ADD * intensity
        r["ph"] -= config.SPILL_PH_DROP * intensity
        r["do_mg_l"] -= config.SPILL_DO_DROP * intensity
        r["temperature"] += config.SPILL_TEMP_ADD * intensity
        r["tds"] += config.SPILL_TDS_ADD * intensity
        r["gas_ppm"] += config.SPILL_GAS_ADD * intensity
        r["depth_cm"] += config.SPILL_DEPTH_ADD * intensity

    def evaluate(self, r):
        h = r["health"]
        b = self.bases

        z_t = b["turb"].zscore(r["turbidity"]) if h["turb"] else 0.0
        z_p = b["ph"].zscore(r["ph"]) if h["ph"] else 0.0
        z_o = b["do"].zscore(r["do_mg_l"]) if h["do"] else 0.0
        z_c = b["temp"].zscore(r["temperature"]) if h["temp"] else 0.0
        z_d = b["depth"].zscore(r["depth_cm"]) if h["depth"] else 0.0
        z_s = b["tds"].zscore(r["tds"]) if h["tds"] else 0.0
        z_g = b["gas"].zscore(r["gas_ppm"]) if h["gas"] else 0.0
        z_max = max(z_t, z_p, z_o, z_c, z_d, z_s, z_g)

        ph_conama = h["ph"] and (r["ph"] < config.PH_MIN or r["ph"] > config.PH_MAX)
        do_conama = h["do"] and (r["do_mg_l"] < config.DO_MIN_MG_L)
        turb_limit = h["turb"] and (r["turbidity"] > config.TURBIDITY_MAX_NTU)
        tds_limit = h["tds"] and (r["tds"] > config.TDS_MAX_PPM)
        depth_low = h["depth"] and (r["depth_cm"] < config.DEPTH_MIN_CM)
        depth_high = h["depth"] and (r["depth_cm"] > config.DEPTH_MAX_CM)
        gas_limit = h["gas"] and (r["gas_digital"] or r["gas_ppm"] > config.GAS_MAX_PPM)

        reasons = []
        hard_limit = False

        if do_conama:
            hard_limit = True
            reasons.append("OD {:.1f} mg/L CONAMA".format(r["do_mg_l"]))
        if ph_conama:
            hard_limit = True
            reasons.append("pH {:.2f} CONAMA".format(r["ph"]))
        if turb_limit:
            hard_limit = True
            reasons.append("turbidez {:.0f} NTU".format(r["turbidity"]))
        if tds_limit:
            hard_limit = True
            reasons.append("TDS {:.0f} ppm".format(r["tds"]))
        if depth_low:
            hard_limit = True
            reasons.append("assoreamento/lixo ({:.0f} cm)".format(r["depth_cm"]))
        if depth_high:
            hard_limit = True
            reasons.append("nivel alto ({:.0f} cm)".format(r["depth_cm"]))
        if gas_limit:
            hard_limit = True
            reasons.append("gas/odor {:.0f} ppm".format(r["gas_ppm"]))

        if z_t > config.Z_THRESHOLD:
            reasons.append("pico turbidez z={:.1f}".format(z_t))
        if z_o > config.Z_THRESHOLD:
            reasons.append("queda OD z={:.1f}".format(z_o))
        if z_p > config.Z_THRESHOLD:
            reasons.append("salto pH z={:.1f}".format(z_p))
        if z_s > config.Z_THRESHOLD:
            reasons.append("pico TDS z={:.1f}".format(z_s))
        if z_g > config.Z_THRESHOLD:
            reasons.append("pico odor/gas z={:.1f}".format(z_g))
        if z_d > config.Z_THRESHOLD:
            reasons.append("variacao nivel z={:.1f}".format(z_d))
        if z_c > config.Z_THRESHOLD:
            reasons.append("choque termico z={:.1f}".format(z_c))

        score = max(z_max, config.Z_THRESHOLD + 1.0) if hard_limit else z_max
        if not reasons:
            return False, score, "NORMAL", ""

        # Fusao multi-sensor: classifica a provavel causa
        turb_flag = turb_limit or (z_t > config.Z_THRESHOLD)
        ph_flag = ph_conama or (z_p > config.Z_THRESHOLD)
        do_flag = do_conama or (z_o > config.Z_THRESHOLD)
        tds_flag = tds_limit or (z_s > config.Z_THRESHOLD)
        gas_flag = gas_limit or (z_g > config.Z_THRESHOLD)
        depth_low_flag = depth_low or (
            b["depth"].ready()
            and (b["depth"].mean - r["depth_cm"]) > config.Z_THRESHOLD * b["depth"].stddev()
        )
        depth_high_flag = depth_high or (
            b["depth"].ready()
            and (r["depth_cm"] - b["depth"].mean) > config.Z_THRESHOLD * b["depth"].stddev()
        )

        if turb_flag and (ph_flag or do_flag or tds_flag or gas_flag):
            tag = "DESPEJO_ORGANICO"
        elif do_flag and not turb_flag and not ph_flag and not tds_flag:
            tag = "HIPOXIA_EUTROFIZACAO"
        elif depth_high_flag and turb_flag and not ph_flag and not gas_flag and not do_flag:
            tag = "ENXURRADA_MARE"
        elif depth_low_flag and not turb_flag and not ph_flag and not do_flag:
            tag = "ASSOREAMENTO_RESIDUOS"
        elif depth_high_flag:
            tag = "NIVEL_ELEVADO"
        elif gas_flag:
            tag = "ODOR_FETIDO"
        elif ph_flag or tds_flag:
            tag = "DESPEJO_QUIMICO"
        elif turb_flag:
            tag = "TURBIDEZ_ALTA"
        else:
            tag = "DESCARGA_TERMICA"

        return True, score, tag, "; ".join(reasons)

    def process_sample(self, now):
        temp, temp_ok = self.hw.read_temperature()
        turb, turb_ok = self.hw.read_turbidity()
        ph, ph_ok = self.hw.read_ph(temp)
        tds, tds_ok = self.hw.read_tds(temp)
        do_mg_l, do_ok = self.hw.read_do(temp, tds)
        depth, depth_ok = self.hw.read_depth_cm()
        gas_ppm, gas_dig, gas_ok = self.hw.read_gas()
        bat, solar_active, solar_state = self.hw.read_power(self.alert_active)
        self.solar_active = solar_active
        self.hw.led_solar.value(1 if solar_active else 0)

        r = {
            "turbidity": turb,
            "ph": ph,
            "do_mg_l": do_mg_l,
            "temperature": temp,
            "tds": tds,
            "depth_cm": depth,
            "gas_ppm": gas_ppm,
            "gas_digital": gas_dig,
            "battery": bat,
            "solar_active": solar_active,
            "solar_state": solar_state,
            "health": {
                "temp": temp_ok,
                "turb": turb_ok,
                "ph": ph_ok,
                "do": do_ok,
                "tds": tds_ok,
                "depth": depth_ok,
                "gas": gas_ok,
            },
        }

        self.apply_spill(r, now)
        r["turbidity"] = max(r["turbidity"], 0.0)
        r["ph"] = clamp(r["ph"], 0.0, 14.0)
        r["do_mg_l"] = clamp(r["do_mg_l"], 0.0, 20.0)
        r["tds"] = max(r["tds"], 0.0)
        r["depth_cm"] = max(r["depth_cm"], 0.0)
        r["gas_ppm"] = max(r["gas_ppm"], 0.0)
        self.sample_count += 1

        anomaly, score, tag, reason = self.evaluate(r)
        learning = self.sample_count <= config.WARMUP_SAMPLES
        iqa = compute_iqa(r)

        if anomaly:
            self.normal_streak = 0
            if not self.alert_active:
                self.alert_active = True
                self.pending_recovery = False
                self.event_count += 1
                self.hw.beep(1800, 180)
                print("\n!!! ALERTA #{} [{}] !!!".format(self.event_count, tag))
        elif self.alert_active:
            self.normal_streak += 1
            if self.normal_streak >= config.CLEAR_SAMPLES:
                self.alert_active = False
                self.pending_recovery = True
                self.hw.beep(900, 100)
                print("\n=== Qualidade e nivel do rio normalizados ===\n")

        if learning or (not self.alert_active and not anomaly):
            h = r["health"]
            if h["turb"]:
                self.bases["turb"].update(r["turbidity"])
            if h["ph"]:
                self.bases["ph"].update(r["ph"])
            if h["do"]:
                self.bases["do"].update(r["do_mg_l"])
            if h["temp"]:
                self.bases["temp"].update(r["temperature"])
            if h["depth"]:
                self.bases["depth"].update(r["depth_cm"])
            if h["tds"]:
                self.bases["tds"].update(r["tds"])
            if h["gas"]:
                self.bases["gas"].update(r["gas_ppm"])
            if self.sample_count == config.WARMUP_SAMPLES:
                print("[SYS] Linha de base aprendida. Monitorando.\n")

        human = human_timestamp()
        iso = iso_timestamp()
        bad = health_summary(r["health"])
        trend = depth_trend(r["depth_cm"], self.bases["depth"])
        state_txt = (
            "{}: {}".format(tag, reason)
            if anomaly
            else ("aprendendo" if self.sample_count < config.WARMUP_SAMPLES else "OK")
        )

        line = (
            "[{}] Turb:{:4.0f} | pH:{:4.2f} | OD:{:4.1f} | T:{:4.1f}C | Prof:{:3.0f}cm({}) | "
            "TDS:{:4.0f} | Gas:{:4.0f} | Bat:{:4.2f}V({}%,{}) | IQA:{} | z:{:4.1f} | {}"
        ).format(
            human,
            r["turbidity"],
            r["ph"],
            r["do_mg_l"],
            r["temperature"],
            r["depth_cm"],
            trend,
            r["tds"],
            r["gas_ppm"],
            r["battery"],
            battery_percent(r["battery"]),
            r["solar_state"],
            iqa,
            score,
            state_txt,
        )
        if r["battery"] < config.BAT_LOW_V:
            line += " [ECONOMIA_SOLAR]" if not solar_active else " [RECARREGANDO]"
        if bad:
            line += " [FALHA_SENSOR:{}]".format(bad)
        print(line)

        self.last_reading = r
        self.last_score = score
        self.last_iqa = iqa
        self.last_iso = iso

        if anomaly and (not self.window_has_alert or score >= self.window_peak_score):
            self.window_has_alert = True
            self.window_peak_score = score
            self.window_peak_iqa = iqa
            self.window_peak_reading = r
            self.window_peak_tag = tag
            self.window_peak_reason = reason
            self.window_peak_iso = iso
            self.window_peak_human = human

    def print_evidence(self, r, score, iqa, tag, reason, human_ts):
        trend = depth_trend(r["depth_cm"], self.bases["depth"])
        sat_pct = do_sat_percent(r["do_mg_l"], r["temperature"], r["tds"])
        print("+----------------------- EVIDENCIA -----------------------+")
        print("| Boia:      {} | Classe: {}".format(config.BUOY_ID, tag))
        print("| Data/hora: {} (UTC-3)".format(human_ts))
        print("| Local:     {:.6f}, {:.6f}".format(config.BUOY_LAT, config.BUOY_LON))
        print("| Mapa:      https://maps.google.com/?q={:.6f},{:.6f}".format(config.BUOY_LAT, config.BUOY_LON))
        print("| Agua:      Turb {:.0f} NTU | pH {:.2f} | OD {:.1f} mg/L ({}% sat)".format(
            r["turbidity"], r["ph"], r["do_mg_l"], sat_pct
        ))
        print("| Fis-Quim:  Temp {:.1f} C | TDS {:.0f} ppm | Prof {:.0f} cm ({})".format(
            r["temperature"], r["tds"], r["depth_cm"], trend
        ))
        print("| Ar/Energ:  Gases/Odor {:.0f} ppm | Bat {:.2f} V ({}%, {})".format(
            r["gas_ppm"], r["battery"], battery_percent(r["battery"]), r["solar_state"]
        ))
        print("| IQA/Score: {}/100 ({}) | Score z = {:.1f}".format(
            iqa, iqa_label(iqa), score
        ))
        print("| Motivo:    {}".format(reason))
        print("+---------------------------------------------------------+")

    def send_thingspeak(self, r, score, is_evidence, status, iso_ts):
        if not thingspeak_configured():
            print("[NET] THINGSPEAK_API_KEY nao configurada -> dados apenas no Serial")
            return False
        if not self.wlan.isconnected():
            print("[NET] Sem Wi-Fi, envio adiado")
            return False

        parts = [
            "api_key=" + config.THINGSPEAK_API_KEY,
            "field1={:.1f}".format(r["turbidity"]),
            "field2={:.2f}".format(r["ph"]),
            "field3={:.2f}".format(r["temperature"]),
            "field4={:.1f}".format(r["depth_cm"]),
            "field5={:.2f}".format(r["do_mg_l"]),
            "field6={:.0f}".format(r["tds"]),
            "field7={:.0f}".format(r["gas_ppm"]),
            "field8={:.2f}".format(score),
            "lat={:.6f}".format(config.BUOY_LAT),
            "long={:.6f}".format(config.BUOY_LON),
        ]
        if status:
            parts.append("status=" + url_encode(status))
        if iso_ts:
            parts.append("created_at=" + url_encode(iso_ts))
        body = "&".join(parts)

        resp = None
        try:
            resp = requests.post(
                config.THINGSPEAK_URL,
                data=body,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            code = resp.status_code
            text = resp.text.strip()
            try:
                entry_id = int(text)
            except ValueError:
                entry_id = 0
            if code == 200 and entry_id > 0:
                print("[NET] ThingSpeak OK - entrada #{}{}".format(
                    entry_id, " (EVIDENCIA)" if is_evidence else ""
                ))
                return True
            print("[NET] Falha no envio (HTTP {}, resposta '{}')".format(code, text))
            return False
        except Exception as exc:
            print("[NET] Erro HTTP:", exc)
            return False
        finally:
            if resp is not None:
                resp.close()
            gc.collect()

    def publish(self):
        alert = self.window_has_alert
        r = self.window_peak_reading if alert else self.last_reading
        score = self.window_peak_score if alert else self.last_score
        iqa = self.window_peak_iqa if alert else self.last_iqa
        iso_ts = self.window_peak_iso if alert else self.last_iso
        status = ""

        if alert:
            status = "{} [{}] {} IQA={}: {}".format(
                config.BUOY_ID, self.window_peak_tag, self.window_peak_human, iqa, self.window_peak_reason
            )
            if r["battery"] < config.BAT_LOW_V:
                status += " [BAT_BAIXA:{}]".format(r["solar_state"])
            self.print_evidence(r, score, iqa, self.window_peak_tag, self.window_peak_reason, self.window_peak_human)
        elif self.pending_recovery:
            status = "{} [NORMALIZADO] {} IQA={} ({})".format(
                config.BUOY_ID, human_timestamp(), iqa, iqa_label(iqa)
            )
        elif r["battery"] < config.BAT_LOW_V and not r["solar_active"]:
            status = "{} [ECONOMIA] Bateria LiPo baixa ({:.2f}V) aguardando sol".format(
                config.BUOY_ID, r["battery"]
            )

        bad = health_summary(r["health"])
        if bad and status:
            status += " [FALHA:{}]".format(bad)
        if len(status) > 250:
            status = status[:250]

        ok = self.send_thingspeak(r, score, alert, status, iso_ts)
        if ok or not thingspeak_configured():
            self.window_has_alert = False
            self.window_peak_score = 0.0
            self.pending_recovery = False

    def send_interval_ms(self):
        if self.alert_active or self.window_has_alert:
            return config.SEND_INTERVAL_ALERT_MS
        if (
            self.last_reading is not None
            and self.last_reading["battery"] < config.BAT_LOW_V
            and not self.solar_active
        ):
            return config.SEND_INTERVAL_POWERSAVE_MS
        return config.SEND_INTERVAL_NORMAL_MS

    def run(self):
        self.print_banner()
        self.connect_wifi()
        if self.wlan.isconnected():
            if not sync_ntp():
                print("[NTP] Sem hora ainda (sincronizando em segundo plano)")
        self.last_ntp_try = time.ticks_ms()
        print("[SYS] Aprendendo linha de base multi-sensor ({} leituras)...\n".format(config.WARMUP_SAMPLES))

        try:
            while True:
                now = time.ticks_ms()
                self.check_button(now)
                self.maintain_network(now)
                self.update_leds(now)
                self.hw.update_buzzer(now)

                if time.ticks_diff(now, self.last_sample_ms) >= config.SAMPLE_INTERVAL_MS:
                    self.last_sample_ms = now
                    self.process_sample(now)

                if self.sample_count > 0 and (
                    self.last_send_ms is None
                    or time.ticks_diff(time.ticks_ms(), self.last_send_ms) >= self.send_interval_ms()
                ):
                    self.publish()
                    self.last_send_ms = time.ticks_ms()

                time.sleep_ms(50)
        except KeyboardInterrupt:
            self.hw.silence()
            print("\n[SYS] Encerrado (Ctrl+C -> REPL).")


if __name__ == "__main__":
    EcoMangueApp().run()
