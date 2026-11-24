# Geometria analítica no ClimaSense (item 4.8)

Onde a geometria analítica aparece no projeto, a fórmula usada e onde está o código.

## Plano cartesiano local

A **estação é a origem** O = (0, 0). O eixo **x** aponta para o **leste** e o eixo **y** para o **norte**, ambos em km.
Um ponto (latitude φ, longitude λ) é levado ao plano pela projeção equiretangular centrada na estação (φ₀, λ₀):

    x = R · (λ − λ₀) · cos(φ₀)        y = R · (φ − φ₀)        R = 6371,0088 km, ângulos em radianos

Código: `app/services/geometry.py` → `project_km()`.

## 1. Distância entre dois pontos

    d = √((x₂ − x₁)² + (y₂ − y₁)²)        → entre estação (0,0) e visitante (x, y): d = √(x² + y²)

Código: `geometry.distance()`. A API devolve também a distância de Haversine (sobre a esfera) só para conferência:
para distâncias curtas as duas diferem menos de 0,5 % (validado em `tests/test_geo.py`).

## 2. Equação da circunferência (área de cobertura)

Área de cobertura de raio r centrada na estação:

    (x − x₀)² + (y − y₀)² = r²     →     x² + y² = r²

O visitante está **dentro** da cobertura se **x² + y² ≤ r²**. Código: `geometry.inside_circle()`.
No mapa, é o círculo roxo (`L.circle`).

## 3. Equação da reta estação → visitante

A reta passa pela origem e por P = (x, y). Forma geral e reduzida:

    y·X − x·Y = 0          →          Y = m·X,   m = y / x   (coeficiente angular)

Se x = 0 a reta é vertical (`X = 0`). Código: `geometry.line_through_origin()`. No mapa, é a linha tracejada laranja.

## 4. Direção (azimute)

Ângulo medido a partir do norte, no sentido horário: **θ = atan2(x, y)** (de 0° a 360°), convertido em ponto cardeal
(N, NE, L, SE, S, SO, O, NO). Código: `geometry.azimuth_deg()` e `geometry.compass()`.

## 5. Reta de tendência (regressão linear por mínimos quadrados)

Para cada grandeza, ajusta-se a reta **y = a·x + b** aos pontos (xᵢ, yᵢ), com x = horas desde o primeiro registro:

    a = (n·Σxy − Σx·Σy) / (n·Σx² − (Σx)²)        b = (Σy − a·Σx) / n        R² = 1 − SQres / SQtot

- **a** (coeficiente angular) = variação média da grandeza por hora; **b** = valor em x = 0.
- **R²** perto de 1 = pontos bem alinhados; perto de 0 = a reta explica pouco.
- Só é calculada com ≥ 3 pontos e janela ≥ 30 min; senão aparece "indisponível" (nunca inventa tendência).

Código: `geometry.linear_regression()` e `services/readings.py → trendlines()`. Endpoint: `GET /api/trendline`.
No painel, é a linha tracejada sobre cada gráfico, com a equação escrita embaixo.

## Endpoints relacionados

| Endpoint | O que faz |
|---|---|
| `GET /api/geo/proximity?lat=..&lon=..` | Distância, direção, dentro/fora da cobertura, equações da circunferência e da reta |
| `GET /api/trendline?period=24h` | Coeficientes a, b, R² e variação estimada de cada grandeza |
| `GET /api/station/status` | Inclui `latitude`, `longitude` e `coverage_radius_km` da estação |
