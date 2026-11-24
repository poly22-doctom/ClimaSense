"""Geometria analítica aplicada ao projeto (funções puras, sem banco de dados).

Plano cartesiano local: a ESTAÇÃO é a origem O = (0, 0); o eixo x aponta para LESTE e o eixo y para NORTE,
ambos em km. Um ponto (lat, lon) é levado ao plano pela projeção equiretangular centrada na estação:

    x = R · Δλ · cos(φ₀)        y = R · Δφ        (R = raio médio da Terra, ângulos em radianos)

No plano valem as fórmulas da geometria analítica:
    distância entre dois pontos ..... d = √((x₂ − x₁)² + (y₂ − y₁)²)
    equação da circunferência ....... (x − x₀)² + (y − y₀)² = r²   (ponto está DENTRO se ≤ r²)
    equação da reta por dois pontos . (y₂ − y₁)·x − (x₂ − x₁)·y + (x₂y₁ − x₁y₂) = 0  →  y = m·x + b
    reta de tendência (mínimos quadrados) .. y = a·x + b,  a = (n·Σxy − Σx·Σy) / (n·Σx² − (Σx)²)
"""
import math

EARTH_RADIUS_KM = 6371.0088
_EPS = 1e-9
_COMPASS = ("N", "NE", "L", "SE", "S", "SO", "O", "NO")  # pontos cardeais em português (L = leste, O = oeste)


def project_km(lat: float, lon: float, lat0: float, lon0: float) -> tuple[float, float]:
    """(lat, lon) → (x, y) em km no plano cuja origem é (lat0, lon0)."""
    dlon = (lon - lon0 + 180.0) % 360.0 - 180.0  # trata a passagem pelo meridiano de 180°
    x = EARTH_RADIUS_KM * math.radians(dlon) * math.cos(math.radians(lat0))
    y = EARTH_RADIUS_KM * math.radians(lat - lat0)
    return x, y


def distance(p: tuple[float, float], q: tuple[float, float]) -> float:
    """Distância entre dois pontos do plano: √((x₂−x₁)² + (y₂−y₁)²)."""
    return math.hypot(q[0] - p[0], q[1] - p[1])


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distância sobre a esfera (referência para comparar com a distância plana)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dlmb = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


def inside_circle(p: tuple[float, float], center: tuple[float, float], radius: float) -> bool:
    """P pertence ao disco de centro C e raio r ⇔ (x − x₀)² + (y − y₀)² ≤ r²."""
    return (p[0] - center[0]) ** 2 + (p[1] - center[1]) ** 2 <= radius ** 2


def azimuth_deg(p: tuple[float, float]) -> float | None:
    """Ângulo, em graus, medido a partir do norte (sentido horário), da origem até P. None se P = origem."""
    if math.hypot(*p) < _EPS:
        return None
    return (math.degrees(math.atan2(p[0], p[1])) + 360.0) % 360.0


def compass(azimuth: float | None) -> str | None:
    return None if azimuth is None else _COMPASS[int((azimuth + 22.5) // 45) % 8]


def line_through_origin(p: tuple[float, float]) -> dict | None:
    """Reta que passa pela origem (estação) e por P. Forma geral a·x + b·y = 0 e, se não for vertical, y = m·x."""
    if math.hypot(*p) < _EPS:
        return None
    x, y = p
    vertical = abs(x) < _EPS
    return {"a": y, "b": -x, "c": 0.0, "slope": None if vertical else y / x, "vertical": vertical}


def linear_regression(xs: list[float], ys: list[float]) -> dict | None:
    """Reta de mínimos quadrados y = a·x + b. Devolve None se não houver reta única (n < 2 ou x constante).
    r2 = coeficiente de determinação (1 = pontos exatamente alinhados); None se y for constante."""
    n = len(xs)
    if n < 2 or n != len(ys):
        return None
    sx, sy = sum(xs), sum(ys)
    sxx = sum(x * x for x in xs)
    sxy = sum(x * y for x, y in zip(xs, ys))
    den = n * sxx - sx * sx
    if abs(den) < 1e-12:
        return None
    a = (n * sxy - sx * sy) / den
    b = (sy - a * sx) / n
    mean_y = sy / n
    ss_tot = sum((y - mean_y) ** 2 for y in ys)
    ss_res = sum((y - (a * x + b)) ** 2 for x, y in zip(xs, ys))
    r2 = None if ss_tot < 1e-12 else max(0.0, 1.0 - ss_res / ss_tot)
    return {"slope": a, "intercept": b, "r2": r2}
