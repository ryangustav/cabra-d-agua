# Cabra d’Água v2
Documentação técnica e funcional • Revisão 1.5 | 26 de novembro de 2026

## 1. Visão geral e objetivos
O Cabra d’Água é um projeto acadêmico de Internet das Coisas para monitoramento ambiental do Rio Poxim, no bairro Farolândia, em Aracaju-SE. A proposta é coletar parâmetros da água e do ambiente, processá-los em um ESP32 e disponibilizar indicadores e alertas para acompanhamento remoto.

O projeto investiga a degradação ambiental do rio e dos manguezais e propõe monitoramento complementar de alterações locais.

### 1.1. Problema local e evidências

O estuário do Rio Poxim integra a paisagem urbana de Aracaju e margeia a Farolândia. A degradação de suas águas afeta não apenas o equilíbrio ecológico dos manguezais, mas também as condições de trabalho e subsistência de comunidades ligadas à pesca artesanal e à mariscagem. O problema escolhido é a dificuldade de acompanhar, com resolução temporal suficiente, alterações ambientais em pontos específicos do rio. Não se presume ausência de fiscalização ou de monitoramento público.

Em 2016, uma pesquisa da Universidade Federal de Sergipe avaliou três pontos do estuário, incluindo a Farolândia (P2). Em abril daquele ano, os ensaios com água indicaram redução significativa da sobrevivência de organismos-teste nos três pontos. Os autores associaram esse resultado, como possível explicação, à baixa concentração de oxigênio dissolvido (1,00–3,19 ppm) e à amônia elevada (3,00 ppm). Esses resultados são históricos, não medições atuais [A].

Outro estudo da UFS, de 2021, relacionou alterações no oxigênio dissolvido e fósforo total a impactos do esgotamento sanitário e classificou como ruim o índice de conformidade de pontos do estuário central no período seco. O trabalho recomenda monitoramento contínuo e gestão integrada [B].

A dimensão social também é documentada: a Caravana das Águas, iniciativa do PEAC/Observatório Social dos Royalties em parceria com pescadores e marisqueiras, percorreu o braço do Poxim que margeia a Farolândia e relatou esgotos abertos e impactos percebidos pelas comunidades pesqueiras [C]. A Adema inclui o Poxim no monitoramento estadual de rios [D]. Essas evidências justificam investigar o trecho, mas não quantificam a poluição atual nem demonstram a origem de um evento específico.

O Sistema Poxim é estratégico para a segurança hídrica: segundo o Governo de Sergipe, responde por aproximadamente 30% da produção de água tratada destinada a Aracaju [E]. A captação para abastecimento ocorre em outros trechos e integra um sistema de tratamento; a estação proposta na Farolândia monitora o estuário e não a água distribuída à população. A preservação da bacia é relevante para a gestão dos recursos hídricos, sem que se possa atribuir ao protótipo proteção direta da captação.

O rio também integra espaços de lazer e bem-estar. A Prefeitura destaca o Parque Ecológico Poxim, com píer de contemplação e atividades recreativas [F]. No Parque dos Cajueiros há registros de remo, canoagem e pesca esportiva no Poxim [G]. A degradação ambiental pode comprometer a qualidade da paisagem e o aproveitamento recreativo, além de afetar a biodiversidade e a economia pesqueira. Esses usos não demonstram que a água seja segura para banho.

### 1.2. Justificativa da solução IoT

Coletas laboratoriais e visitas de fiscalização são essenciais, porém medições pontuais podem não registrar alterações transitórias entre campanhas. Uma estação de baixo custo, ancorada e conectada, poderá produzir séries temporais de parâmetros ambientais, identificar desvios da referência local e registrar horários de ocorrência. O ESP32 permite processamento na borda e envio remoto ao ThingSpeak, reduzindo a necessidade de presença constante junto ao equipamento. A proposta é complementar, e não substituir, o monitoramento institucional.

O benefício esperado é oferecer indícios que orientem novas coletas e investigações, apoiem a pesquisa universitária e ampliem a compreensão pública das condições ambientais. Pescadores, marisqueiras, moradores, pesquisadores e órgãos ambientais são potenciais beneficiários. A efetividade deverá ser avaliada por comparação com instrumentos de referência, disponibilidade das medições e desempenho dos alertas, incluindo falsos positivos e falhas de sensores.

A maré, a chuva e a mistura de água doce e salgada podem causar variações naturais de pH, turbidez e condutividade. O sistema deverá distinguir, na medida do possível, esses padrões de alterações suspeitas, sem atribuir automaticamente causas. O MVP físico não mede oxigênio dissolvido, amônia ou microrganismos; portanto, não determina potabilidade, segurança para banho, consumo de pescado ou hipóxia. O sensor de OD permanece como expansão prioritária, precisamente pela relevância indicada nas pesquisas locais.

Pergunta norteadora: como uma estação IoT experimental de baixo custo pode apoiar a identificação e o registro de alterações ambientais no trecho do Rio Poxim próximo à Farolândia?

Objetivos específicos: coletar medições; filtrar ruídos; identificar falhas dos sensores; reconhecer padrões multissensoriais; registrar eventos com data e localização; apresentar gráficos no ThingSpeak; demonstrar o funcionamento no Wokwi e planejar a montagem física.

**Estado do projeto:** o README v2 descreve o firmware e o roteiro de simulação. Os arquivos de código e os resultados de execução não foram disponibilizados para esta documentação. A implementação física, a calibração e a validação em campo permanecem propostas, não resultados comprovados.

**Decisão de escopo (revisão 1.2): o sensor de oxigênio dissolvido SEN0237-A é implementação física futura devido ao custo. Permanece na simulação do Wokwi, com dados identificados como simulados. Antes da migração física, adaptar o firmware para desabilitar a leitura de OD, deixar o campo 5 do ThingSpeak sem medição, desabilitar alertas dependentes de OD (incluindo hipóxia), revisar a fusão multissensor, o score e o indicador de qualidade. Não preencher OD ausente com zero ou valor simulado. Sem OD, o sistema não avalia diretamente a disponibilidade de oxigênio para a fauna. O código ainda não foi alterado nem testado nesta revisão.**

## 2. Escopo e requisitos
| ID | Requisito funcional descrito ou proposto |
|---|---|
| RF01 | Coletar seis parâmetros ambientais no protótipo físico e monitorar a bateria; OD apenas simulado até expansão futura. |
| RF02 | Filtrar amostras analógicas e medições ultrassônicas. |
| RF03 | Aplicar compensações e detectar falhas de sensores. |
| RF04 | Classificar padrões de anomalia e calcular indicador ambiental experimental. |
| RF05 | Indicar estado local por LEDs e buzzer. |
| RF06 | Registrar eventos com horário, coordenadas GPS válidas, classificação e indicadores; sinalizar ausência de fixação GPS. |
| RF07 | Enviar oito campos na simulação; no físico, sete campos ativos, com campo 5 reservado ao OD; manter saída serial sem chave. |
| RF08 | Simular alterações ambientais por controles e botão D no Wokwi. |

Requisitos não funcionais propostos: proteger credenciais; garantir compatibilidade elétrica de 3,3 V; registrar unidades e falhas; permitir calibração e manutenção; proteger eletrônica contra umidade; documentar origem simulada ou real dos dados. Frequência de amostragem, autonomia, latência e tolerâncias devem ser definidas após testes.

## 3. Arquitetura e hardware
Fluxo: sensores → aquisição pelo ESP32 → filtragem e compensação → diagnóstico e fusão multissensor → alertas locais e saída serial → Wi-Fi → ThingSpeak.

| Parâmetro | Componente físico / etapa | Simulação / faixa descrita |
|---|---|---|
| Turbidez | SEN0189 | Potenciômetro; 0–1000 NTU |
| pH | PH-4502C | Potenciômetro; 0–14 |
| Oxigênio dissolvido (OD) | SEN0237 — futuro | Potenciômetro; 0–12 mg/L |
| TDS | Sonda TDS/condutividade | Potenciômetro; 0–2000 ppm |
| Temperatura | DS18B20 | DS18B20; controle interativo |
| Distância/nível | JSN-SR04T | HC-SR04; 2–400 cm |
| Gases/odor | MQ-135/MQ-4 | Sensor de gás virtual |
| Bateria | Monitor de tensão LiPo | Potenciômetro; 3,0–4,2 V |
| Localização | GPS NEO-6M (UART) | Coordenadas fictícias identificadas |

O ESP32 centraliza os sinais; os sensores não precisam comunicar-se diretamente. Os módulos analógicos e o ECHO do ultrassônico exigem adequação de tensão quando operam acima de 3,3 V. As sondas de água devem ser adequadas à imersão e à água salobra; módulos eletrônicos permanecem protegidos. Pinagem, alimentação, divisores e eventual conversor ADC externo dependem do diagram.json e dos modelos comprados; não estão confirmados.

GPS NEO-6M (escopo físico atual): comunicação UART com o ESP32, pinagem e alimentação a confirmar. Registrar latitude, longitude e validade da posição; detectar deslocamento fora de um raio de ancoragem definido após testes, evitando alertas por imprecisão ou movimento normal. Na simulação, usar coordenadas fictícias identificadas; integração e testes do GPS ainda pendentes.

## 4. Firmware e processamento na borda
O README descreve MicroPython e três arquivos: main.py (firmware), config.py (configuração) e diagram.json (circuito virtual). As funções e técnicas abaixo são descritas no README, não auditadas no código.

| Técnica | Funcionamento descrito |
|---|---|
| Filtro ADC | read_voltage_filtered: ordena 15 amostras e descarta as 3 menores e 3 maiores. O cálculo final não é especificado. |
| Ultrassônico | read_depth_cm: mediana de três disparos via machine.time_pulse_us. |
| Compensação | DS18B20; TDS com 2%/°C, correção de Nernst para pH real e curva de saturação de OD. |
| Diagnóstico | Desconexão do DS18B20 e timeout ultrassônico sem falso alerta ambiental. |
| Índice | Simulação: indicador 0–100 ponderado por OD, turbidez e pH; pesos não informados. No físico, suspender ou reformular sem OD e validar. |
| Tendência | ENCHENDO, VAZANDO ou ESTAVEL. |

O LED verde pisca durante a aprendizagem inicial (~20 segundos na demonstração), permanece aceso em condição normal e o LED vermelho com buzzer indica alerta. Tensão abaixo de 3,35 V gera aviso de manutenção. A aprendizagem inicial representa uma referência simulada, não o estado normal comprovado do Rio Poxim.

## 5. Classificação de anomalias
| Identificador do firmware | Interpretação e ressalva |
|---|---|
| DESPEJO_ORGANICO | Padrão simulado de aumento de turbidez, TDS, gás e nível, com queda de pH e OD. No físico, adaptar a regra sem OD; emitir apenas suspeita. |
| HIPOXIA_EUTROFIZACAO | Somente simulação / expansão futura: OD inferior a 5 mg/L na demonstração; não confirma eutrofização. |
| DESPEJO_QUIMICO | Classe descrita; regra exata não fornecida. |
| ODOR_FETIDO | Aumento da leitura virtual de gás; não comprova composição do odor. |
| ASSOREAMENTO_RESIDUOS | Distância inferior a 60 cm na demonstração; não comprova resíduos ou assoreamento. |
| ENXURRADA_MARE | Classe descrita; regra exata não fornecida. |
| NIVEL_ELEVADO | Classe descrita; regra exata não fornecida. |
| TURBIDEZ_ALTA | Classe descrita; regra exata não fornecida. |
| DESCARGA_TERMICA | Classe descrita; regra exata não fornecida. |

O score de anomalia >= 3,0 indica alerta conforme README. O bloco EVIDÊNCIA contém horário, coordenada, link do mapa, saturação de OD e indicador de qualidade. Esses registros são indícios para investigação, não provas de autoria ou de despejo ilegal. No físico, recalibrar o limiar sem OD e não incluir saturação de OD no registro. Na revisão 1.5, o GPS NEO-6M integra o escopo físico previsto; sua integração ao firmware ainda está pendente.

Os limites de pH 6,5–8,5 e OD 5 mg/L mencionados no README são referências usadas na demonstração. Sua aplicabilidade regulatória depende do enquadramento e da classe da água. O indicador 0–100 é experimental e não equivale ao IQA oficial. TDS não é sinônimo de salinidade; sensores MQ não identificam seletivamente H₂S e CH₄ sem validação específica.

## 6. Comunicação e plataforma ThingSpeak
| Campo | Nome no canal |
|---|---|
| 1 | Turbidez (NTU) |
| 2 | pH |
| 3 | Temperatura (C) |
| 4 | Profundidade (cm) |
| 5 | Oxigenio Dissolvido (mg/L) — reservado; somente simulação por enquanto |
| 6 | TDS / Salinidade (ppm) |
| 7 | Gases / Odor (ppm) |
| 8 | Score Anomalia |

Criar um canal em https://thingspeak.mathworks.com, habilitar os oito campos e copiar a Write API Key para THINGSPEAK_API_KEY em config.py. Para apresentação, habilitar compartilhamento público somente se os dados forem apropriados à divulgação. Sem chave, o README informa que a saída serial continua disponível. Não publicar a chave de escrita nem senhas no GitHub; usar configuração local e exemplo sem segredos.

A bateria, as classes textuais, as coordenadas e o índice experimental não possuem campos próprios no esquema descrito. A persistência remota desses itens não está confirmada. Protocolo de envio, frequência, retentativas e tratamento de indisponibilidade devem ser conferidos no firmware. Para localização remota, usar metadados de localização do ThingSpeak ou canal complementar, após validação da integração; preservar os oito campos existentes.

## 7. Estrutura física e ancoragem
Decisão de projeto: boia ancorada no fundo do rio. Dimensões preliminares: base de 30 × 30 cm e altura total de 30–35 cm, sujeitas a revisão devido aos sensores adicionais. Caixa vedada, flutuadores, prensa-cabos, suportes de sondas e alimentação por bateria/painel solar são propostas físicas, ainda não dimensionadas.

A ancoragem prevê ponto estrutural de fixação inferior, cabo náutico, girador antitorção, conectores resistentes à corrosão e âncora adequada ao sedimento. Peso, comprimento do cabo e raio de movimentação dependem de profundidade, marés, correnteza, cargas e estabilidade. Não instalar em campo sem avaliação e autorização; evitar danos a raízes, fauna e navegação.

Os sensores medem localmente a água em contato com as sondas, sem raio fixo de cobertura. Uma rede de estações pode ampliar a representatividade espacial. O alcance de Wi-Fi depende da infraestrutura e do ambiente; LoRa ou rede móvel são alternativas futuras, não funcionalidades confirmadas.

O ultrassônico aéreo mede distância à superfície. Em uma boia que acompanha a maré, não fornece profundidade absoluta do rio. A solução descrita no README prevê referência fixa (estaca/ponte) e DEPTH_MOUNT_HEIGHT_CM; altura menos distância estima nível relativo. Para profundidade do fundo seria necessário outro método. A estação fixa complementar é uma decisão de engenharia pendente.

## 8. Reprodução no Wokwi e migração física
1. Abrir https://wokwi.com/projects/new/micropython-esp32.
2. Inserir main.py e diagram.json nas respectivas abas e criar config.py pelo menu New file.
3. Iniciar a simulação e observar o terminal serial. O README indica que network, ntptime, onewire, ds18x20 e urequests estão disponíveis sem libraries.txt.
4. Configurar o ThingSpeak opcionalmente. Usar os potenciômetros para pH, turbidez, OD, TDS e bateria; controles próprios para temperatura, distância e gás.
5. Pressionar D ou o botão vermelho para injetar uma pluma simulada durante 30 segundos.

Para migrar ao hardware: gravar main.py e config.py via Thonny ou mpremote; ajustar WOKWI_SIMULATION = False; configurar WIFI_SSID e WIFI_PASSWORD; calibrar PH_NEUTRAL_VOLTAGE e PH_SLOPE; DO_CAL_VOLTAGE somente na expansão futura; conferir tensões, vedação e referência do ultrassônico antes de energizar. A lista não substitui o esquema elétrico definitivo.

## 9. Plano de testes e validação
| Teste | Resultado esperado (não executado nesta documentação) |
|---|---|
| T01 — Inicialização | LED verde para de piscar após ~20 s de aprendizagem simulada. |
| T02 — Botão D | Evento DESPEJO_ORGANICO, LED vermelho, beep e bloco EVIDÊNCIA. |
| T03 — OD baixo | Somente simulação: abaixo de 5 mg/L, classe HIPOXIA_EUTROFIZACAO. |
| T04 — Distância | Abaixo de 60 cm, classe ASSOREAMENTO_RESIDUOS no cenário simulado. |
| T05 — Gás | Aumento do gás virtual gera ODOR_FETIDO. |
| T06 — Bateria | Abaixo de 3,35 V, aviso de manutenção. |
| T07 — Falha de sensor | Desconexão/timeout identificado sem falso alerta ambiental. |
| T08 — ThingSpeak | Oito campos na simulação; sete ativos no físico, sem valor fictício de OD; serial disponível sem chave. |
| T09 — Hardware | Calibração com referências, repetibilidade, comparação com instrumento de referência. |
| T10 — Boia | Flutuação, estabilidade, vedação, autonomia e ancoragem em ambiente controlado. |

Registrar por teste: data, versão do firmware, entrada, resultado observado, evidência, aprovação e responsável. Todos os testes estão pendentes de comprovação nesta revisão. A validação ambiental requer comparação com métodos de referência e amostras reais autorizadas.

Teste adicional T11: validar coordenadas, ausência de fixação e alerta de deslocamento em ambiente controlado.

## 10. Orçamento e viabilidade

| Componente | Qtd. | Provisão unitária | Total |
|---|---:|---:|---:|
| ESP32 DevKit | 1 | R$ 50,00 | R$ 50,00 |
| pH PH-4502C (sonda + módulo) | 1 | R$ 225,00 | R$ 225,00 |
| Turbidez SEN0189 | 1 | R$ 100,00 | R$ 100,00 |
| DS18B20 encapsulado | 1 | R$ 15,00 | R$ 15,00 |
| TDS / condutividade (kit) | 1 | R$ 65,00 | R$ 65,00 |
| JSN-SR04T ultrassônico | 1 | R$ 60,00 | R$ 60,00 |
| MQ-135 (gases) | 1 | R$ 25,00 | R$ 25,00 |
| Monitor de tensão (divisor resistivo) | 1 | R$ 5,00 | R$ 5,00 |
| ADS1115 (opcional, verificar pinagem) | 1 | R$ 30,00 | R$ 30,00 |
| LEDs, buzzer, botão e resistores | 1 | R$ 20,00 | R$ 20,00 |
| Protoboard, jumpers e cabo USB | 1 | R$ 40,00 | R$ 40,00 |
| Placa perfurada, conectores e divisores | 1 | R$ 35,00 | R$ 35,00 |
| Calibração e consumíveis (pH, TDS, turbidez; reserva mantida) | 1 | R$ 150,00 | R$ 150,00 |
| Caixa vedada, flutuadores, suportes, vedações | 1 | R$ 150,00 | R$ 150,00 |
| Ancoragem experimental (cabo, peso e ferragens) | 1 | R$ 80,00 | R$ 80,00 |
| Painel solar (provisão) | 1 | R$ 100,00 | R$ 100,00 |
| Bateria protegida (provisão) | 1 | R$ 80,00 | R$ 80,00 |
| Controlador solar e conversores (provisão) | 1 | R$ 100,00 | R$ 100,00 |
| Suporte fixo para sensor de nível (provisão) | 1 | R$ 60,00 | R$ 60,00 |
| GPS NEO-6M (provisão) | 1 | R$ 50,00 | R$ 50,00 |
| **Total** | | | **R$ 1.440,00** |

Planejamento v2 — 26/11/2026. Bancada: R$ 870,00; boia ancorada, sem solar e sem suporte fixo: R$ 1.100,00; configuração completa experimental sem OD: R$ 1.440,00; com contingência de 15%: R$ 1.656,00. Simulação Wokwi/ThingSpeak: R$ 0 em modalidades gratuitas, sujeitas a limites.

Expansão futura: SEN0237-A, provisão de R$ 1.200,00, excluída dos totais atuais. A configuração completa com esse sensor voltaria a R$ 2.640,00 (R$ 3.036,00 com 15% de reserva), antes de custos adicionais de calibração, integração e importação. Mantida a reserva de R$ 150,00 para calibração dos demais sensores por prudência.

Os valores são provisões de planejamento, não propostas comerciais fechadas. Referências consultadas em 26/11/2026: DFRobot SEN0237-A US$ 169 (https://www.dfrobot.com/product-1628.html); Newark US$ 210,65 (https://www.newark.com/pt-BR/dfrobot/sen0237-a/dev-kit-analog-dissolved-oxygen/dp/88AH1499); DigiKey SEN0189 US$ 9,90 (https://www.digikey.com.br/pt/products/detail/dfrobot/SEN0189/6588606). A provisão futura de R$ 1.200 para OD não é conversão cambial oficial nem garantia de custo de importação.

Referências nacionais: Usinainfo pH: sonda R$ 134,41 e leitor R$ 89,71, kit indisponível na consulta (https://www.usinainfo.com.br/sensores-de-qualidade-da-agua/sensor-de-ph-para-arduino-modulo-de-leitura-bnc-ph4502c-5316.html); DS18B20 R$ 8,17 no Pix (https://www.usinainfo.com.br/sensor-de-temperatura/sensor-de-temperatura-ds-18b20-a-prova-d-agua-2645.html); JSN-SR04T anunciado em 3 × R$ 19,96 (https://www.breletronica.com.br/sensor-ultrassonico-a-prova-dagua-jsn-sr04t-20). Demais itens são estimativas sem cotação individual confirmada.

Frete, tributos de importação, manutenção recorrente, instrumentos de referência, licenças e instalação profissional não incluídos. Na expansão futura, o kit OD exige solução de preenchimento não incluída pelo fabricante e manutenção de membrana; utilizar laboratório supervisionado. TDS de baixa faixa pode saturar em água salobra; eventual sensor EC de maior faixa exige nova cotação. O consumo contínuo do MQ e a autonomia solar precisam ser dimensionados. O suporte fixo do ultrassônico é uma provisão e não resolve sozinho comunicação e alimentação de uma estação separada. A montagem em campo não está orçada nem validada.

## 11. Entregáveis e próximos passos
Entregáveis previstos: firmware e configuração de exemplo; circuito Wokwi; canal ThingSpeak; documentação técnica; evidências dos testes; apresentação; protótipo físico condicionado a orçamento e validação. Prioridades: revisar código e pinagem; executar testes virtuais; confirmar cotações e disponibilidade dos sensores; definir método de nível; montar bancada e calibrar; dimensionar boia/energia/ancoragem; testar em ambiente controlado; avaliar licenças e condições de campo. A integração física de OD fica no roadmap futuro.

## 12. Fontes e controle da revisão
Fonte técnica principal: README.md, EcoMangue v2 — Firmware (nome anterior) da boia (MicroPython / ESP32 / Wokwi), fornecido pela equipe (67 linhas). Seções: execução (3–11), ThingSpeak (13–28), controles (30–43), arquitetura (45–52), demonstração (54–60), migração física (62–67).

Decisões físicas e estimativas: planejamento anterior discutido pela equipe nesta conversa. Referências técnicas para aprofundamento: documentação Wokwi (https://docs.wokwi.com/), documentação MicroPython (https://docs.micropython.org/), ThingSpeak (https://thingspeak.mathworks.com/), Resolução CONAMA 357/2005 (enquadramento a confirmar) e pesquisa UFS sobre o estuário do Poxim (https://ri.ufs.br/handle/riufs/6792).

### Referências da justificativa ambiental (26/11/2026)

[A] UFS. Monitoramento ecotoxicológico do estuário Rio Poxim (Aracaju/Sergipe), 2016. https://ri.ufs.br/handle/riufs/6792

[B] UFS. Análise das condições ambientais do estuário do Rio Poxim e pressupostos a sua gestão, 2021. https://ri.ufs.br/handle/riufs/15771

[C] PEAC. Caravana das Águas encontra Rio Poxim com esgotos abertos e obras de grande impacto ambiental. https://programapeac.com.br/noticia/264

[D] ADEMA. Monitoramento ambiental. https://adema.se.gov.br/monitoramento-ambiental/

[E] GOVERNO DE SERGIPE. Deso reativa Adutora Poxim II para reduzir retirada de água da barragem diante dos efeitos do El Niño. https://www.se.gov.br/agencia/vge/noticia/deso_reativa_adutora_poxim_ii_para_reduzir_retirada_de_agua_da_barragem_diante_dos_efeitos_do_el_ni_o

[F] PREFEITURA DE ARACAJU. População elogia tranquilidade e contato com a natureza no Parque Ecológico Poxim. https://www.aracaju.se.gov.br/noticias/99567/populacao-elogia-tranquilidade-e-contato-com-a-natureza-no-parque-ecologico-poxim

[G] SERGIPE TURISMO. Parque dos Cajueiros. https://sergipeturismo.com/parque-dos-cajueiros/

Histórico da revisão 1.3: mudança do nome para Cabra d’Água e ampliação da justificativa científica e social. O README e o firmware originais não foram renomeados nesta entrega. Revisão 1.4: ampliação da justificativa com abastecimento público e lazer, mantendo o escopo físico e orçamento. Revisão 1.5: inclusão do GPS NEO-6M no escopo físico e orçamento.

Revisão documental 1.5 | Base técnica v2 | Responsáveis e aprovação: a definir pela equipe. Documento de projeto, não laudo ambiental nem certificação de funcionamento.
