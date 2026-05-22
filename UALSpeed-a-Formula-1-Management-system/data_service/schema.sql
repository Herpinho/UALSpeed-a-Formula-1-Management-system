CREATE TABLE IF NOT EXISTS public.cars (
    car_id SERIAL PRIMARY KEY,
    race_id INTEGER NOT NULL,
    driver_id INTEGER NOT NULL,
    speed INTEGER,
    rpm INTEGER,
    throttle INTEGER,
    brake INTEGER,
    drs BOOLEAN DEFAULT FALSE,
    gear INTEGER,
    lap INTEGER,
    data_time TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.race_phases (
    id SERIAL PRIMARY KEY,
    race_id INTEGER NOT NULL,
    phase INTEGER NOT NULL,
    data JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (race_id, phase)
);

CREATE TABLE IF NOT EXISTS public.car_performance (
    perf_id       SERIAL PRIMARY KEY,
    race_id       INTEGER NOT NULL,
    driver_id     INTEGER NOT NULL,
    driver_name   VARCHAR(255) NOT NULL,
    max_speed     FLOAT,
    max_rpm       INTEGER,
    avg_throttle  FLOAT,
    avg_brake     FLOAT,
    drs_time      FLOAT,
    best_lap_time VARCHAR(50),
    total_laps    INTEGER,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(race_id, driver_id)
);

CREATE TABLE IF NOT EXISTS public.stints (
    stint_id      SERIAL PRIMARY KEY,
    race_id       INTEGER NOT NULL,
    driver_id     INTEGER NOT NULL,
    driver_name   VARCHAR(255) NOT NULL,
    stint_number  INTEGER NOT NULL,
    compound      VARCHAR(20),
    lap_start     INTEGER,
    lap_end       INTEGER,
    tyre_age      INTEGER,
    is_fresh      BOOLEAN DEFAULT TRUE,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_cars_race_driver ON public.cars(race_id, driver_id);
CREATE INDEX IF NOT EXISTS idx_race_phases_race_phase ON public.race_phases(race_id, phase);
CREATE INDEX IF NOT EXISTS idx_car_performance_race ON public.car_performance(race_id);
CREATE INDEX IF NOT EXISTS idx_stints_race_driver ON public.stints(race_id, driver_id);
