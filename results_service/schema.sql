CREATE TABLE IF NOT EXISTS public.races (
    race_id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    circuit VARCHAR(255) NOT NULL,
    country VARCHAR(100) NOT NULL,
    date DATE,
    total_laps INTEGER NOT NULL,
    status VARCHAR(20) DEFAULT 'scheduled' CHECK (status IN ('scheduled', 'live', 'completed')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.race_results (
    result_id SERIAL PRIMARY KEY,
    race_id INTEGER REFERENCES public.races(race_id) ON DELETE CASCADE,
    driver_id INTEGER NOT NULL,
    driver_name VARCHAR(255) NOT NULL,
    team VARCHAR(255) NOT NULL,
    position INTEGER NOT NULL,
    points INTEGER DEFAULT 0,
    fastest_lap VARCHAR(20),
    total_time VARCHAR(20),
    status VARCHAR(20) DEFAULT 'finished' CHECK (status IN ('finished', 'dnf', 'dns', 'dsq')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.laps (
    lap_id SERIAL PRIMARY KEY,
    race_id INTEGER REFERENCES public.races(race_id) ON DELETE CASCADE,
    driver_id INTEGER NOT NULL,
    driver_name VARCHAR(255) NOT NULL,
    lap_number INTEGER NOT NULL,
    lap_time VARCHAR(20) NOT NULL,
    sector1 VARCHAR(20),
    sector2 VARCHAR(20),
    sector3 VARCHAR(20),
    position INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(race_id, driver_id, lap_number)
);

CREATE TABLE IF NOT EXISTS public.standings (
    standing_id SERIAL PRIMARY KEY,
    driver_id INTEGER UNIQUE NOT NULL,
    driver_name VARCHAR(255) NOT NULL,
    team VARCHAR(255) NOT NULL,
    position INTEGER NOT NULL,
    points INTEGER DEFAULT 0,
    wins INTEGER DEFAULT 0,
    podiums INTEGER DEFAULT 0,
    fastest_laps INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_race_results_race_id ON public.race_results(race_id);
CREATE INDEX IF NOT EXISTS idx_race_results_driver_id ON public.race_results(driver_id);
CREATE INDEX IF NOT EXISTS idx_laps_race_id ON public.laps(race_id);
CREATE INDEX IF NOT EXISTS idx_laps_driver_id ON public.laps(driver_id);
CREATE INDEX IF NOT EXISTS idx_standings_position ON public.standings(position);
