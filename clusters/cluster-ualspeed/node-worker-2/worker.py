

from fastapi import FastAPI
import redis
import json
import httpx
import asyncio
import fastf1
import pandas as pd
from datetime import datetime
import os

app = FastAPI(title="UALSpeed - Worker 2 (Classificações)", version="1.0.0")

MANAGER_URL = os.getenv("MANAGER_URL", "http://manager:8000")
WORKER_NOME = os.getenv("WORKER_NOME", "worker-2")
WORKER_URL = os.getenv("WORKER_URL", "http://worker-2:8002")

r = redis.Redis(
    host=os.getenv("REDIS_HOST", "redis"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    decode_responses=True
)


@app.on_event("startup")
async def startup():
    await asyncio.sleep(4)
    asyncio.create_task(registar_no_manager())
    asyncio.create_task(enviar_heartbeat())


async def registar_no_manager():
    async with httpx.AsyncClient() as client:
        for tentativa in range(5):
            try:
                await client.post(f"{MANAGER_URL}/cluster/registar-no", json={
                    "nome": WORKER_NOME, "url": WORKER_URL
                }, timeout=5)
                print(f"[{WORKER_NOME}] Registado no manager!")
                return
            except Exception as e:
                print(f"[{WORKER_NOME}] Tentativa {tentativa+1}: {e}")
                await asyncio.sleep(3)


async def enviar_heartbeat():
    async with httpx.AsyncClient() as client:
        while True:
            try:
                await client.post(f"{MANAGER_URL}/cluster/heartbeat", json={"nome": WORKER_NOME}, timeout=5)
            except:
                pass
            await asyncio.sleep(10)


@app.get("/")
def root():
    return {"servico": WORKER_NOME, "tipo": "classificacoes", "status": "online"}


@app.get("/health")
def health():
    return {"status": "ok", "worker": WORKER_NOME, "timestamp": datetime.now().isoformat()}


@app.get("/classificacao/local")
def classificacao_local():
    dados = r.get(f"{WORKER_NOME}:classificacao_local")
    if not dados:
        return {"mensagem": "Sem dados locais ainda"}
    return json.loads(dados)


@app.get("/classificacao/{ano}/{gp}")
def classificacao_corrida(ano: int, gp: str):
    cache_key = f"classif:{ano}:{gp}"
    dados_cache = r.get(cache_key)
    if dados_cache:
        return {"fonte": "cache", "dados": json.loads(dados_cache)}

    try:
        fastf1.Cache.enable_cache("/tmp/fastf1_cache")
        session = fastf1.get_session(ano, gp, "R")
        session.load(telemetry=False, weather=False)

        classificacao = []
        for _, piloto in session.results.iterrows():
            classificacao.append({
                "posicao": int(piloto.get("Position", 0)) if pd.notna(piloto.get("Position")) else None,
                "numero": str(piloto.get("DriverNumber", "")),
                "piloto": piloto.get("FullName", ""),
                "abreviatura": piloto.get("Abbreviation", ""),
                "equipa": piloto.get("TeamName", ""),
                "tempo_total": str(piloto.get("Time", "")),
                "pontos": float(piloto.get("Points", 0)) if pd.notna(piloto.get("Points")) else 0,
                "status": piloto.get("Status", ""),
            })

        for entrada in classificacao:
            try:
                voltas = session.laps.pick_driver(entrada["abreviatura"])
                melhor_volta = voltas["LapTime"].min()
                entrada["melhor_volta"] = str(melhor_volta) if pd.notna(melhor_volta) else None
                entrada["total_voltas"] = len(voltas)
            except:
                entrada["melhor_volta"] = None
                entrada["total_voltas"] = 0

        dados = {
            "ano": ano, "gp": gp,
            "classificacao": classificacao,
            "calculado_por": WORKER_NOME,
            "timestamp": datetime.now().isoformat()
        }
        r.set(cache_key, json.dumps(dados), ex=3600)
        return {"fonte": "fastf1", "dados": dados}

    except Exception as e:
        return {"erro": str(e)}


@app.get("/voltas/{ano}/{gp}/{piloto}")
def voltas_piloto(ano: int, gp: str, piloto: str):
    cache_key = f"voltas:{ano}:{gp}:{piloto}"
    dados_cache = r.get(cache_key)
    if dados_cache:
        return {"fonte": "cache", "dados": json.loads(dados_cache)}

    try:
        fastf1.Cache.enable_cache("/tmp/fastf1_cache")
        session = fastf1.get_session(ano, gp, "R")
        session.load(telemetry=False, weather=False)

        voltas = session.laps.pick_driver(piloto.upper())
        lista_voltas = []
        for _, volta in voltas.iterrows():
            lista_voltas.append({
                "numero_volta": int(volta.get("LapNumber", 0)),
                "tempo": str(volta.get("LapTime", "")),
                "composto": volta.get("Compound", ""),
                "pit_stop": bool(volta.get("PitOutTime", None) is not None),
            })

        dados = {
            "piloto": piloto.upper(), "ano": ano, "gp": gp,
            "voltas": lista_voltas,
            "melhor_volta": str(voltas["LapTime"].min()) if not voltas.empty else None,
            "calculado_por": WORKER_NOME,
        }
        r.set(cache_key, json.dumps(dados), ex=3600)
        return {"fonte": "fastf1", "dados": dados}

    except Exception as e:
        return {"erro": str(e)}


@app.post("/sincronizar")
def sincronizar(data: dict):
    """Recebe dados do serviço de resultados e sincroniza no cluster."""
    data["sincronizado_por"] = WORKER_NOME
    data["timestamp"] = datetime.now().isoformat()
    r.set("classificacao:atual", json.dumps(data))
    r.publish("canal:classificacao", json.dumps(data))
    return {"mensagem": "Dados sincronizados no cluster", "worker": WORKER_NOME}
