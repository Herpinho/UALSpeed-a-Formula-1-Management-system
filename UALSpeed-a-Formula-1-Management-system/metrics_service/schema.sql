CREATE TABLE IF NOT EXISTS public.services (
    service_id   SERIAL PRIMARY KEY,
    name         VARCHAR(100) NOT NULL UNIQUE,
    url          VARCHAR(255) NOT NULL,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.service_checks (
    check_id     SERIAL PRIMARY KEY,
    service_id   INTEGER REFERENCES public.services(service_id) ON DELETE CASCADE,
    status       VARCHAR(20) NOT NULL CHECK (status IN ('online', 'offline', 'degraded')),
    latency_ms   FLOAT,
    status_code  INTEGER,
    error_msg    VARCHAR(500),
    checked_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_checks_service_id  ON public.service_checks(service_id);
CREATE INDEX IF NOT EXISTS idx_checks_checked_at  ON public.service_checks(checked_at);

-- Serviços registados por defeito
INSERT INTO public.services (name, url) VALUES
    ('Results Service', 'http://results-service:5002/results/'),
    ('Data Service',    'http://data-service:5003/data/')
ON CONFLICT (name) DO NOTHING;

-- Eventos para contagem de throughput (cada linha é 1 evento recebido)
CREATE TABLE IF NOT EXISTS public.events (
    event_id    SERIAL PRIMARY KEY,
    service_id  INTEGER REFERENCES public.services(service_id) ON DELETE SET NULL,
    event_type  VARCHAR(100) DEFAULT 'generic',
    occurred_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_events_occurred_at ON public.events(occurred_at);
CREATE INDEX IF NOT EXISTS idx_events_service_id ON public.events(service_id);