# EcoMangue v2 — Firmware da boia (MicroPython / ESP32 / Wokwi)

## Rodar no Wokwi (3 min)

1. Abra o template **MicroPython ESP32**: https://wokwi.com/projects/new/micropython-esp32
2. Cole os arquivos nas abas correspondentes:
   - `main.py` → aba **main.py**
   - `diagram.json` → aba **diagram.json** (o circuito inteiro aparece sozinho)
   - `config.py` → clique em **▾ > New file…** e crie `config.py`
   *(Não precisa de `libraries.txt`: `network`, `ntptime`, `onewire`, `ds18x20` e `urequests` já vêm embutidos no MicroPython do ESP32 no Wokwi.)*
3. Clique em ▶ **Start**. O terminal serial mostra as leituras em tempo real.

## Ligar os gráficos (ThingSpeak — 8 campos)

1. Crie um canal em https://thingspeak.mathworks.com → **New Channel**
2. Ative os **8 campos**:
   - `Field 1`: `Turbidez (NTU)`
   - `Field 2`: `pH`
   - `Field 3`: `Temperatura (C)`
   - `Field 4`: `Profundidade (cm)`
   - `Field 5`: `Oxigenio Dissolvido (mg/L)`
   - `Field 6`: `TDS / Salinidade (ppm)`
   - `Field 7`: `Gases / Odor (ppm)`
   - `Field 8`: `Score Anomalia` (`>= 3.0` indica alerta)
3. Em **Sharing**, marque *Share channel view with everyone* (link público para os jurados)
4. Aba **API Keys** → copie a **Write API Key** e cole em `THINGSPEAK_API_KEY` no `config.py`

Sem a chave, tudo funciona igual no terminal serial.

## Controles da simulação

| Componente | Simula | Como usar |
|---|---|---|
| Potenciômetro **Turbidez** | Sensor óptico SEN0189 (0–1000 NTU) | Girar para a direita = água mais turva |
| Potenciômetro **pH** | Sonda PH-4502C (0–14) | Meio = ~7,5 (faixa CONAMA: 6,5–8,5) |
| Potenciômetro **Oxig. Diss. (OD)** | Sonda SEN0237 (0–12 mg/L) | Abaixo de `5,0 mg/L` = hipóxia (CONAMA 357) |
| Potenciômetro **TDS / Sal** | Sonda TDS/Condutividade (0–2000 ppm) | Compensado automaticamente pela temperatura |
| Potenciômetro **Bateria** | Tensão da LiPo (ajuste manual) | `3,0–4,2 V` · Girar ajusta a tensão instantânea; abaixo de `3,35 V` sem sol ativa economia (`60 s`) |
| **Placa Solar** (`wokwi-photoresistor-sensor`) | Painel solar 5V/2W (`CN3065` / `TP4056`) | Clique e ajuste o slider de luz: com sol (`> ~350 lux`) recarrega e sustenta a LiPo até `4,20 V`; à noite (`< 100 lux`) descarrega |
| **DS18B20** | Temperatura da água (`+ pull-up 4,7 kΩ`) | Clique nele e mova o slider |
| **HC-SR04** | Profundidade / Nível (JSN-SR04T no real) | Clique nele e mova o slider (`2–400 cm`) |
| **Sensor de Gás** | Mau cheiro / $H_2S$ e $CH_4$ (MQ-135/MQ-4) | Clique nele e aumente o gás no slider |
| Botão vermelho / tecla **D** | Despejo clandestino | Injeta pluma de esgoto (turbidez, pH, queda de OD, TDS, odor e nível) por 30 s |
| LEDs verde / vermelho / azul (`+ R 220 Ω`) / Buzzer | Status local | Verde = OK (`GPIO 27`); Vermelho + beep = **ALERTA** (`GPIO 26/25`); Azul = **Placa Solar** (`GPIO 23`) |

## Arquitetura de sensoriamento em MicroPython

- **Filtro mediano aparado** no ADC (`read_voltage_filtered`): 15 amostras ordenadas, descarta as 3 menores e 3 maiores.
- **Mediana de 3 disparos** no ultrassônico (`read_depth_cm` via `machine.time_pulse_us`).
- **Compensação térmica e de salinidade** com o DS18B20 (`2% / °C` no TDS, Nernst no pH em hardware real e curva de saturação `% sat` do OD).
- **Sustentação solar inteligente** (`read_power`): com sol ativo carrega/mantém a bateria em `4,20 V` (`CARREG` → `SUSTENT`); à noite descarrega gradualmente (`BATERIA`) e reduz envios normais para `60 s` se cair abaixo de `3,35 V`.
- **Diagnóstico de saúde dos sensores**: detecta desconexão do DS18B20 ou timeout do ultrassônico sem gerar falso alarme ambiental.
- **Fusão multi-sensor** na borda: classifica `DESPEJO_ORGANICO`, `HIPOXIA_EUTROFIZACAO`, `DESPEJO_QUIMICO`, `ODOR_FETIDO`, `ASSOREAMENTO_RESIDUOS`, `ENXURRADA_MARE`, `NIVEL_ELEVADO`, `TURBIDEZ_ALTA` ou `DESCARGA_TERMICA`.
- **IQA (0–100)** ponderado por OD/Turbidez/pH e **tendência de nível/maré** (`ENCHENDO`, `VAZANDO`, `ESTAVEL`).

## Roteiro da demo no pitch

1. Inicie a simulação e espere ~20 s até o LED verde parar de piscar (a boia aprendeu o normal do Rio Poxim). Observe o **LED azul aceso** e a bateria subindo até `4,20 V (100%, SUSTENT)`.
2. Clique na **Placa Solar** e arraste o slider para a esquerda (noite/sombra) → LED azul apaga e a boia entra em modo `BATERIA`; volte para o sol e ela retoma a recarga.
3. Clique no diagrama e aperte **D** → turbidez, TDS, gases e nível sobem enquanto pH e **OD (`< 5,0 mg/L`)** caem. O código classifica como `DESPEJO_ORGANICO`, emite um beep curto, acende o alerta vermelho e imprime o bloco **EVIDÊNCIA** (carimbo de tempo + coordenada + link do mapa + `% sat` de OD + IQA).
4. Gire o potenciômetro **Oxig. Diss. (OD)** para `< 5,0 mg/L` → detecta `HIPOXIA_EUTROFIZACAO`.
5. Arraste o **HC-SR04** para `< 60 cm` → detecta `ASSOREAMENTO_RESIDUOS` (acúmulo de lixo/entulho).
6. Clique no **Sensor de Gás** e suba o nível → detecta `ODOR_FETIDO`.

## Passar para o ESP32 físico com MicroPython

Grave `config.py` e `main.py` na placa (via Thonny ou `mpremote`), mude `WOKWI_SIMULATION = False` em `config.py`, preencha `WIFI_SSID` / `WIFI_PASSWORD` e calibre `PH_NEUTRAL_VOLTAGE` / `PH_SLOPE` e `DO_CAL_VOLTAGE`.
- Ligue o painel solar (5–6 V / 2 W) a um controlador **CN3065** ou **TP4056** conectado à LiPo 3,7 V; ligue o pino `CHRG` (com pull-up/divisor se >3,3 V) ao `GPIO 14` para monitorar carga ativa.
- Se montar o ultrassônico à prova d'água **JSN-SR04T** acima da água (preso em estaca/ponte), ajuste `DEPTH_MOUNT_HEIGHT_CM` (ex.: `350.0`) para calcular `lamina = altura - distancia`.
- Use **divisor de tensão** (`10 kΩ / 20 kΩ`, fator `1.5` em `config.py`) nos pinos analógicos 5 V (turbidez, pH, gás) e no pino `ECHO` do ultrassônico, e `100 kΩ / 100 kΩ` na LiPo antes de ligar ao ESP32 (máx. 3,3 V).
