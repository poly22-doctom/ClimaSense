"""Avaliação de alertas. Cada alerta informa se é MEDIDO (fato) ou ESTIMADO (interpretação).
Os limites vêm da tabela alert_settings: são definições do projeto, não normas oficiais."""
from datetime import timedelta
from statistics import median

from sqlalchemy.orm import Session

from app.core.timeutils import utcnow
from app.repositories import readings as repo

SENSOR_LABEL = {"dht22": "DHT22 (temperatura e umidade)", "bmp280": "BMP280 (pressão)",
                "mq135": "MQ-135 (gases)", "ldr": "LDR (luminosidade)"}


def _fmt(v: float, d: int = 1) -> str:
    return f"{v:.{d}f}".replace(".", ",")


def evaluate(db: Session, station_id: str, source: str) -> list[dict]:
    cfg = repo.get_alert_settings(db, station_id)
    alerts: list[dict] = []

    def add(code, severity, basis, title, message):
        alerts.append({"code": code, "severity": severity, "basis": basis, "title": title, "message": message})

    last_rx = repo.last_received_at(db, station_id, source)
    if last_rx is None:
        add("waiting", "informativo", "medido", "Aguardando primeira leitura",
            "A estação ainda não enviou nenhuma medição.")
        return alerts
    minutes = int((utcnow() - last_rx).total_seconds() // 60)
    if minutes > cfg.offline_after_minutes:
        add("offline", "atencao", "medido", "Sem comunicação com a estação",
            f"A última medição chegou há {minutes} min (limite configurado: {cfg.offline_after_minutes} min). "
            "Os valores exibidos podem estar desatualizados.")

    latest = repo.latest_any(db, station_id, source)
    if latest is None:
        return alerts

    if latest.sensor_errors:
        nomes = ", ".join(SENSOR_LABEL.get(s, s) for s in latest.sensor_errors.split(",") if s)
        add("sensor_failure", "atencao", "medido", "Sensor sem leitura",
            f"Falha reportada pela estação em: {nomes}. Esses valores aparecem como “Sem leitura”.")

    t = latest.temperature_c
    if t is not None and t > cfg.temp_max_c:
        add("temp_high", "atencao", "medido", "Temperatura acima do limite",
            f"Medido: {_fmt(t)} °C. Limite configurado: {_fmt(cfg.temp_max_c)} °C.")
    if t is not None and t < cfg.temp_min_c:
        add("temp_low", "atencao", "medido", "Temperatura abaixo do limite",
            f"Medido: {_fmt(t)} °C. Limite configurado: {_fmt(cfg.temp_min_c)} °C.")
    h = latest.humidity_pct
    if h is not None and h > cfg.humidity_max_pct:
        add("humidity_high", "atencao", "medido", "Umidade acima da faixa",
            f"Medido: {_fmt(h, 0)} %. Faixa configurada: {_fmt(cfg.humidity_min_pct, 0)} a {_fmt(cfg.humidity_max_pct, 0)} %.")
    if h is not None and h < cfg.humidity_min_pct:
        add("humidity_low", "atencao", "medido", "Umidade abaixo da faixa",
            f"Medido: {_fmt(h, 0)} %. Faixa configurada: {_fmt(cfg.humidity_min_pct, 0)} a {_fmt(cfg.humidity_max_pct, 0)} %.")

    # Pressão: variação em até 3 h (a variação é medida; o significado para o tempo é estimativa)
    if latest.pressure_hpa is not None:
        rows = repo.rows_in_range(db, station_id, source, latest.timestamp - timedelta(hours=3), latest.timestamp)
        pts = [(r[0], r[3]) for r in rows if r[3] is not None]
        if len(pts) >= 3 and (pts[-1][0] - pts[0][0]) >= timedelta(hours=1, minutes=30):
            delta = pts[-1][1] - pts[0][1]
            if abs(delta) >= cfg.pressure_change_hpa_3h:
                sentido = "queda" if delta < 0 else "alta"
                add("pressure_change", "informativo", "estimado", f"Variação relevante de pressão ({sentido})",
                    f"A pressão variou {_fmt(delta)} hPa nas últimas 3 h (limite: {_fmt(cfg.pressure_change_hpa_3h)} hPa). "
                    "Estimativa: variações rápidas costumam acompanhar mudanças no tempo, mas isso não é uma previsão.")

    # MQ-135: desvio em relação à mediana das 24 h anteriores (sem calibração, só variação relativa)
    if latest.mq135_raw is not None:
        rows = repo.rows_in_range(db, station_id, source, latest.timestamp - timedelta(hours=24),
                                  latest.timestamp - timedelta(minutes=30))
        base_vals = [r[4] for r in rows if r[4] is not None]
        if len(base_vals) >= 12:
            base = median(base_vals)
            if base > 0:
                dev = (latest.mq135_raw - base) / base * 100
                if abs(dev) >= cfg.mq135_change_pct:
                    sentido = "acima" if dev > 0 else "abaixo"
                    add("mq135_change", "informativo", "estimado", "Sinal do sensor de gases fora do habitual",
                        f"A leitura bruta ({latest.mq135_raw}) está {_fmt(abs(dev), 0)} % {sentido} da mediana das últimas 24 h "
                        f"({_fmt(base, 0)}). Estimativa: o sensor não é calibrado e não mede concentração nem índice oficial de qualidade do ar.")
    return alerts
