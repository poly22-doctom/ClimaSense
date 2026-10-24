ClimaSense

Monitoramento Meteorológico e Ambiental com IoT

O ClimaSense é um projeto de monitoramento meteorológico e ambiental que utiliza sensores conectados a um ESP32 para coletar dados do ambiente e disponibilizá-los em um dashboard web intuitivo e responsivo.

A proposta é transformar dados ambientais em informações acessíveis para a população, facilitando o acompanhamento das condições do ambiente.

✨Funcionalidades

-  Monitoramento de temperatura e umidade do ar.
-  Acompanhamento da pressão atmosférica.
- Monitoramento indicativo da qualidade do ar.
-  Medição relativa da intensidade luminosa.
-  Dashboard com gráficos e histórico de medições.
-  Alertas para condições ambientais configuradas.
-  Interface responsiva para computadores, tablets e celulares.
-  Integração entre sensores, ESP32, API e banco de dados.

 🛠️ Tecnologias

| Tecnologia | Aplicação |
|---|---|
| Python | Backend e processamento de dados |
| FastAPI | API REST |
| ESP32 | Coleta e envio de dados |
| DHT22 | Temperatura e umidade |
| BMP280 | Pressão atmosférica |
| MQ-135 | Resposta a gases |
| LDR | Intensidade luminosa relativa |
| SQLite / MySQL | Armazenamento de dados |
| HTML, CSS e JavaScript | Interface web |
| Chart.js | Visualização de dados |

 🏗️ Arquitetura

O sistema conecta a coleta de dados físicos à visualização das informações em uma aplicação web.

Sensores → ESP32 → API Python → Banco de dados → Dashboard

O desenvolvimento do dashboard pode ocorrer antes da montagem do hardware, utilizando dados simulados para testar as funcionalidades e a interface.

🎯 Objetivo

Desenvolver uma solução acessível de monitoramento meteorológico e ambiental, integrando Internet das Coisas (IoT), desenvolvimento web e visualização de dados.


👩‍💻 Desenvolvido por

- Bianca 
- Emanuelly 
- Joab
- Polianny Santos 
- Pedro

Projeto acadêmico de tecnologia, IoT e monitoramento ambiental.


ClimaSense — Dados ambientais ao alcance de todos.🌎
