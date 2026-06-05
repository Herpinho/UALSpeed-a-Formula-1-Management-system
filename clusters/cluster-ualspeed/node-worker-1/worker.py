

from fastapi import FastAPI
import redis
import json
import httpx
import asyncio
import fastf1
import pandas as pd
from datetime import datetime
import os

app = FastAPI(title="UALSpeed - Worker 1 (Dados)", version="1.0.0")

MANAGER_URL = os.getenv("MANAGER_URL", "http://manager:8000")
WORKER_NOME = os.getenv("WORKER_NOME", "worker-1")
WORKER_URL = os.getenv("WORKER_URL", "http://worker-1:8001")

r = redis.Redis(
    host=os.getenv("REDIS_HOST", "redis"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    decode_responses=True
)




@app.on_event("startup")
async def startup():
    """Regista este worker no manager ao arrancar."""
    await asyncio.sleep(3)  # esperar o manager estar pronto
    asyncio.create_task(registar_no_manager())
    asyncio.create_task(enviar_heartbeat())


async def registar_no_manager():
    async with httpx.AsyncClient() as client:
        for tentativa in range(5):
            try:
                await client.post(f"{MANAGER_URL}/cluster/registar-no", json={
                    "nome": WORKER_NOME,
                    "url": WORKER_URL
                }, timeout=5)
                print(f"[{WORKER_NOME}] Registado no manager!")
                return
            except Exception as e:
                print(f"[{WORKER_NOME}] Tentativa {tentativa+1} falhou: {e}")
                await asyncio.sleep(3)


async def enviar_heartbeat():
    """Envia heartbeat ao manager a cada 10 segundos."""
    async with httpx.AsyncClient() as client:
        while True:
            try:
                await client.post(f"{MANAGER_URL}/cluster/heartbeat", json={
                    "nome": WORKER_NOME
                }, timeout=5)
            except:
                pass
            await asyncio.sleep(10)


# ── HEALTH CHECK 

@app.get("/")
def root():
    return {"servico": WORKER_NOME, "tipo": "dados-telemetria", "status": "online"}


@app.get("/health")
def health():
    return {"status": "ok", "worker": WORKER_NOME, "timestamp": datetime.now().isoformat()}


#  TELEMETRIA 

@app.get("/telemetria/{ano}/{gp}/{piloto}")
def obter_telemetria(ano: int, gp: str, piloto: str, volta: int = 1):
    """
    Obtém dados de telemetria de um piloto (velocidade, RPM, posição em pista).
    Exemplo: /telemetria/2024/Bahrain/VER?volta=10
    """
    cache_key = f"telemetria:{ano}:{gp}:{piloto}:{volta}"
    dados_cache = r.get(cache_key)
    if dados_cache:
        return {"fonte": "cache", "dados": json.loads(dados_cache)}

    try:
        fastf1.Cache.enable_cache("/tmp/fastf1_cache")
        session = fastf1.get_session(ano, gp, "R")
        session.load(telemetry=True, weather=False)

        lap = session.laps.pick_driver(piloto.upper()).pick_lap(volta)
        tel = lap.get_telemetry()

        amostras = []
        for _, linha in tel.iterrows():
            amostras.append({
                "tempo": str(linha.get("Time", "")),
                "velocidade": float(linha.get("Speed", 0)),
                "rpm": int(linha.get("RPM", 0)),
                "marcha": int(linha.get("nGear", 0)),
                "acelerador": float(linha.get("Throttle", 0)),
                "travao": bool(linha.get("Brake", False)),
                "x": float(linha.get("X", 0)),
                "y": float(linha.get("Y", 0)),
            })

        dados = {
            "ano": ano, "gp": gp, "piloto": piloto.upper(),
            "volta": volta, "amostras": amostras,
            "total_amostras": len(amostras),
            "processado_por": WORKER_NOME,
            "timestamp": datetime.now().isoformat()
        }

        r.set(cache_key, json.dumps(dados), ex=3600)
        return {"fonte": "fastf1", "dados": dados}

    except Exception as e:
        return {"erro": str(e), "piloto": piloto, "volta": volta}


@app.get("/velocidade-maxima/{ano}/{gp}")
def velocidade_maxima(ano: int, gp: str):
    """Retorna a velocidade máxima de cada piloto numa corrida."""
    cache_key = f"vel_max:{ano}:{gp}"
    dados_cache = r.get(cache_key)
    if dados_cache:
        return {"fonte": "cache", "dados": json.loads(dados_cache)}

    try:
        fastf1.Cache.enable_cache("/tmp/fastf1_cache")
        session = fastf1.get_session(ano, gp, "R")
        session.load(telemetry=False, weather=False)

        resultados = []
        for abrev in session.laps["Driver"].unique():
            voltas_piloto = session.laps.pick_driver(abrev)
            vel_max = voltas_piloto["SpeedST"].max() if "SpeedST" in voltas_piloto.columns else 0
            resultados.append({
                "piloto": abrev,
                "velocidade_maxima_kmh": round(float(vel_max), 1) if pd.notna(vel_max) else 0
            })

        resultados.sort(key=lambda x: x["velocidade_maxima_kmh"], reverse=True)
        dados = {"ano": ano, "gp": gp, "velocidades": resultados}
        r.set(cache_key, json.dumps(dados), ex=3600)
        return {"fonte": "fastf1", "dados": dados}

    except Exception as e:
        return {"erro": str(e)}


@app.post("/processar-evento")
def processar_evento(evento: dict):
    """
    Recebe um evento de dados em tempo real e guarda na fila Redis.
    Para ligação com o serviço de dados dos colegas.
    """
    evento["processado_por"] = WORKER_NOME
    evento["timestamp"] = datetime.now().isoformat()

    r.lpush("fila:eventos", json.dumps(evento))
    r.ltrim("fila:eventos", 0, 999)  # manter só os últimos 1000 eventos

    return {"mensagem": "Evento processado", "worker": WORKER_NOME}


@app.get("/fila/tamanho")
def tamanho_fila():
    tamanho = r.llen("fila:eventos")
    return {"tamanho_fila": tamanho, "worker": WORKER_NOME}
