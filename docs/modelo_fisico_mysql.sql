-- Modelo físico (MySQL). Gerado a partir dos modelos SQLAlchemy em app/models.
-- Uso: CREATE DATABASE clima CHARACTER SET utf8mb4; USE clima; depois execute este arquivo.

CREATE TABLE stations (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	station_id VARCHAR(64) NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	location VARCHAR(200) NOT NULL, 
	created_at DATETIME NOT NULL, 
	latitude FLOAT, 
	longitude FLOAT, 
	coverage_radius_km FLOAT, 
	PRIMARY KEY (id)
);

CREATE UNIQUE INDEX ix_stations_station_id ON stations (station_id);

CREATE TABLE alert_settings (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	station_id VARCHAR(64) NOT NULL, 
	temp_min_c FLOAT NOT NULL, 
	temp_max_c FLOAT NOT NULL, 
	humidity_min_pct FLOAT NOT NULL, 
	humidity_max_pct FLOAT NOT NULL, 
	pressure_change_hpa_3h FLOAT NOT NULL, 
	mq135_change_pct FLOAT NOT NULL, 
	offline_after_minutes INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (station_id), 
	FOREIGN KEY(station_id) REFERENCES stations (station_id)
);


CREATE TABLE readings (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	station_id VARCHAR(64) NOT NULL, 
	timestamp DATETIME NOT NULL, 
	received_at DATETIME NOT NULL, 
	source VARCHAR(16) NOT NULL, 
	temperature_c FLOAT, 
	humidity_pct FLOAT, 
	pressure_hpa FLOAT, 
	bmp280_temperature_c FLOAT, 
	mq135_raw INTEGER, 
	ldr_raw INTEGER, 
	sensor_errors VARCHAR(64) NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_reading_station_ts_source UNIQUE (station_id, timestamp, source), 
	FOREIGN KEY(station_id) REFERENCES stations (station_id)
);

CREATE INDEX ix_readings_station_source_ts ON readings (station_id, source, timestamp);
