<p align="center">
  <img src="https://github.com/user-attachments/assets/ed8a1d92-3b4a-461e-a0e8-d030c258701d" alt="ClimaSense" width="100%">
</p>

<h1 align="center">🌱 ClimaSense</h1>

<p align="center">
  <b>Monitoramento Meteorológico e Ambiental com IoT</b><br>
  <i>Dados ambientais ao alcance de todos 🌎</i>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-2F7A5E?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-API-7C5CC4?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/ESP32-IoT-2F7A5E?style=for-the-badge&logo=espressif&logoColor=white" alt="ESP32">
  <img src="https://img.shields.io/badge/Projeto-Acadêmico-7C5CC4?style=for-the-badge" alt="Projeto acadêmico">
</p>

---

Monitoramento Meteorológico e Ambiental com IoT

O ClimaSense é um projeto de monitoramento meteorológico e ambiental que utiliza sensores conectados a um ESP32 para coletar dados do ambiente e disponibilizá-los em um dashboard web intuitivo e responsivo.

A proposta é transformar dados ambientais em informações acessíveis para a população, facilitando o acompanhamento das condições do ambiente por meio de indicadores, gráficos, histórico de medições e alertas.

✨ Funcionalidades

- Monitoramento de temperatura e umidade relativa do ar.
- Acompanhamento da pressão atmosférica.
- Monitoramento indicativo da resposta a gases.
- Medição relativa da intensidade luminosa.
- Dashboard com indicadores, gráficos e histórico de medições.
- Alertas para condições ambientais configuradas.
- Interface responsiva para computadores, tablets e celulares.
- Integração entre sensores, ESP32, API REST e banco de dados.
- Recebimento de medições via HTTP/JSON com autenticação por chave de API.
- Modo de demonstração com dados simulados, identificados como demonstração.
- Testes automatizados para verificar o funcionamento da aplicação.

🛠️ Tecnologias

| Tecnologia | Aplicação |
|---|---|
| Python | Backend e processamento de dados |
| FastAPI | API REST e documentação dos endpoints |
| ESP32 | Coleta e envio de dados dos sensores |
| DHT22 | Medição de temperatura e umidade relativa do ar |
| BMP280 | Medição da pressão atmosférica |
| MQ-135 | Leitura analógica da resposta a gases |
| LDR | Medição relativa da intensidade luminosa |
| SQLite / MySQL | Armazenamento de dados |
| SQLAlchemy | Mapeamento objeto-relacional e acesso ao banco |
| Pydantic | Validação e estruturação dos dados da API |
| HTML, CSS e JavaScript | Interface web |
| Chart.js | Visualização de dados em gráficos |
| Pytest | Testes automatizados |

🏗️ Arquitetura

O sistema conecta a coleta de dados físicos à visualização das informações em uma aplicação web.

Sensores → ESP32 → API Python (FastAPI) → Banco de dados → Dashboard

A aplicação utiliza uma arquitetura organizada em rotas HTTP, serviços, repositórios, modelos e esquemas de validação, separando as responsabilidades de cada camada.

O desenvolvimento do dashboard pode ocorrer antes da montagem do hardware, utilizando dados simulados para testar as funcionalidades e a interface. Nesse modo, as medições são identificadas como demonstração.

Sensores e medições

| Sensor | Medição | Observação |
|---|---|---|
| DHT22 | Temperatura e umidade relativa do ar | Fonte principal da temperatura exibida no painel |
| BMP280 | Pressão atmosférica | Também fornece uma leitura auxiliar de temperatura, sem substituir a do DHT22 |
| MQ-135 | Resposta analógica a gases | Sem calibração, não determina concentração de gases nem índice oficial de qualidade do ar |
| LDR | Intensidade luminosa relativa | A leitura não representa lux e depende do circuito utilizado |

O conjunto atual não possui sensor de chuva. Quando um sensor apresenta falha, o sistema exibe “Sem leitura”, sem inventar valores.

🎯 Objetivo

Desenvolver uma solução acessível de monitoramento meteorológico e ambiental, integrando Internet das Coisas (IoT), desenvolvimento web, armazenamento de dados e visualização de informações para facilitar o acompanhamento das condições ambientais.

⚙️ Como Executar

Pré-requisitos

- Windows 10/11.
- Python 3.11 ou superior.
- PowerShell.

Instalação

```powershell
cd weather-dashboard
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Se o PowerShell bloquear a ativação do ambiente virtual, execute:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

Configuração

Configure as variáveis de ambiente no arquivo `.env`, incluindo as chaves de API e as opções de banco de dados. Esse arquivo contém configurações locais e não deve ser enviado ao GitHub.

Para gerar uma chave segura, execute o comando abaixo duas vezes, uma para cada chave:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

- `STATION_API_KEY`: chave enviada pelo ESP32 no cabeçalho `X-API-Key`. Se estiver vazia, o recebimento de medições fica desativado.
- `ADMIN_API_KEY`: chave para alterações nas configurações de alertas.
- `DATABASE_URL`: define o banco utilizado. O padrão é SQLite, com possibilidade de configuração para MySQL.
- `DEMO_MODE`: ativa ou desativa o simulador de dados.
- `STATION_ID`, `STATION_NAME`, `STATION_LOCATION` e `TIMEZONE`: identificam e configuram a estação.

Executar a aplicação

```powershell
uvicorn app.main:app --reload --port 8000
```

- Painel: http://localhost:8000
- Swagger (documentação da API): http://localhost:8000/docs

A interface utiliza o Chart.js localmente. A documentação Swagger pode precisar de conexão com a internet para carregar recursos externos.

🧪 Testes

Para executar os testes automatizados:

```powershell
python -m pytest -q
```

👩‍💻 Desenvolvido por

- Bianca
- Emanuelly
- Joab
- Polianny Santos
- Pedro

<p align="center">
  <img src="https://github.com/user-attachments/assets/ed8a1d92-3b4a-461e-a0e8-d030c258701d" alt="ClimaSense - dados ambientais ao alcance de todos" width="85%">
</p>

Projeto acadêmico de tecnologia, IoT e monitoramento ambiental.
Projeto acadêmico de tecnologia, IoT e monitoramento ambiental.
ClimaSense — Dados ambientais ao alcance de todos.🌎
