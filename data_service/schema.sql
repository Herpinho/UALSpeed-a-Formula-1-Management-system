CREATE TABLE IF NOT EXISTS public.cars ( 
    car_id SERIAL PRIMARY KEY,
    race_id INTEGER NOT NULL,
    driver_id INTEGER NOT NULL,
    speed INTEGER, 
    rpm INTEGER,  --
    throttle INTEGER, --0-100%
    brake INTEGER, -- 0-100%
    DRS BOOLEAN DEFAULT FALSE,
    gear INTEGER, --(-1 to Neutral to 8)
    lap INTEGER, 
    data_time TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
