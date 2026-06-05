
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import redis
import json
import httpx
import fastf1
import pandas as pd
from datetime import datetime
import os

app = FastAPI(title="UALSpeed - Manager", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Redis para coordenação entre nós
r = redis.Redis(
    host=os.getenv("REDIS_HOST", "redis"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    decode_responses=True
)


WORKER_1_URL = os.getenv("WORKER_1_URL", "http://worker-1:8001")
WORKER_2_URL = os.getenv("WORKER_2_URL", "http://worker-2:8002")


SERVICO_DADOS_URL = os.getenv("SERVICO_DADOS_URL", "http://servico-dados:8003")
SERVICO_RESULTADOS_URL = os.getenv("SERVICO_RESULTADOS_URL", "http://servico-resultados:8004")




@app.get("/")
def root():
    return {"servico": "UALSpeed Manager", "status": "online"}


@app.get("/health")
def health():
    nos_ativos = []
    try:
        nos_ativos = list(r.smembers("cluster:nos_ativos"))
    except:
        pass
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "nos_ativos": nos_ativos
    }


# ── REGISTO DE NÓS 

@app.post("/cluster/registar-no")
def registar_no(data: dict):
    """Worker chama este endpoint ao arrancar para se registar."""
    nome_no = data.get("nome")
    url_no = data.get("url")
    if not nome_no:
        raise HTTPException(status_code=400, detail="Campo 'nome' obrigatório")
    r.sadd("cluster:nos_ativos", nome_no)
    r.hset("cluster:nos_urls", nome_no, url_no or "")
    r.set(f"cluster:heartbeat:{nome_no}", datetime.now().isoformat())
    print(f"[CLUSTER] Nó registado: {nome_no} ({url_no})")
    return {"mensagem": f"Nó {nome_no} registado com sucesso"}


@app.post("/cluster/heartbeat")
def heartbeat(data: dict):
    """Workers enviam heartbeat periódico para confirmar que estão vivos."""
    nome_no = data.get("nome")
    if nome_no:
        r.set(f"cluster:heartbeat:{nome_no}", datetime.now().isoformat(), ex=30)
        r.sadd("cluster:nos_ativos", nome_no)
    return {"status": "ok"}


@app.get("/cluster/nos")
def listar_nos():
    """Lista todos os nós ativos no cluster."""
    try:
        nos = list(r.smembers("cluster:nos_ativos"))
        resultado = []
        for no in nos:
            ultimo_heartbeat = r.get(f"cluster:heartbeat:{no}")
            url = r.hget("cluster:nos_urls", no)
            resultado.append({
                "nome": no,
                "url": url,
                "ultimo_heartbeat": ultimo_heartbeat,
                "ativo": ultimo_heartbeat is not None
            })
        return {"nos": resultado, "total": len(resultado)}
    except Exception as e:
        return {"nos": [], "erro": str(e)}


# ── CLASSIFICAÇÕES 

@app.get("/classificacao")
def obter_classificacao():
    """Retorna a classificação atual — para o frontend e serviço de resultados."""
    dados = r.get("classificacao:atual")
    if not dados:
        return {"classificacao": [], "mensagem": "Sem dados ainda"}
    return json.loads(dados)


@app.post("/classificacao/atualizar")
def atualizar_classificacao(data: dict):
    """Recebe classificação e sincroniza em todos os nós via Redis."""
    r.set("classificacao:atual", json.dumps(data))
    r.set("classificacao:ultima_atualizacao", datetime.now().isoformat())
    r.lpush("classificacao:historico", json.dumps(data))
    r.ltrim("classificacao:historico", 0, 9)  # guarda só as últimas 10
    r.publish("canal:classificacao", json.dumps(data))
    return {"mensagem": "Classificação sincronizada", "timestamp": datetime.now().isoformat()}


@app.get("/classificacao/historico")
def historico_classificacao():
    historico = r.lrange("classificacao:historico", 0, 9)
    return {"historico": [json.loads(h) for h in historico]}


# ── DADOS F1 (FastF1) 
@app.get("/f1/sessao/{ano}/{gp}/{sessao}")
def obter_dados_sessao(ano: int, gp: str, sessao: str):
    """
    Dados de uma sessão F1.
    Exemplos:
      /f1/sessao/2024/Bahrain/R  → Corrida
      /f1/sessao/2024/Bahrain/Q  → Qualificação
    """
    cache_key = f"f1:{ano}:{gp}:{sessao}"
    dados_cache = r.get(cache_key)
    if dados_cache:
        return {"fonte": "cache", "dados": json.loads(dados_cache)}

    try:
        fastf1.Cache.enable_cache("/tmp/fastf1_cache")
        session = fastf1.get_session(ano, gp, sessao)
        session.load(telemetry=False, weather=False)

        resultados = []
        for _, piloto in session.results.iterrows():
            resultados.append({
                "posicao": int(piloto.get("Position", 0)) if pd.notna(piloto.get("Position")) else None,
                "numero": str(piloto.get("DriverNumber", "")),
                "piloto": piloto.get("FullName", ""),
                "abreviatura": piloto.get("Abbreviation", ""),
                "equipa": piloto.get("TeamName", ""),
                "tempo": str(piloto.get("Time", "")),
                "pontos": float(piloto.get("Points", 0)) if pd.notna(piloto.get("Points")) else 0,
            })

        dados = {
            "ano": ano, "gp": gp, "sessao": sessao,
            "resultados": resultados,
            "timestamp": datetime.now().isoformat()
        }
        r.set(cache_key, json.dumps(dados), ex=3600)
        return {"fonte": "fastf1", "dados": dados}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao obter dados F1: {str(e)}")


@app.get("/f1/calendario/{ano}")
def calendario(ano: int):
    cache_key = f"f1:calendario:{ano}"
    dados_cache = r.get(cache_key)
    if dados_cache:
        return {"fonte": "cache", "dados": json.loads(dados_cache)}
    try:
        fastf1.Cache.enable_cache("/tmp/fastf1_cache")
        schedule = fastf1.get_event_schedule(ano)
        corridas = []
        for _, evento in schedule.iterrows():
            corridas.append({
                "ronda": int(evento.get("RoundNumber", 0)),
                "nome": evento.get("EventName", ""),
                "pais": evento.get("Country", ""),
                "data": str(evento.get("EventDate", "")),
            })
        dados = {"ano": ano, "corridas": corridas}
        r.set(cache_key, json.dumps(dados), ex=86400)
        return {"fonte": "fastf1", "dados": dados}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── PROXY PARA OUTROS SERVIÇOS

@app.get("/dados/{path:path}")
async def proxy_servico_dados(path: str):
    """Proxy para o serviço de dados dos colegas."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{SERVICO_DADOS_URL}/{path}", timeout=10)
            return resp.json()
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Serviço de dados indisponível: {str(e)}")


@app.post("/dados/{path:path}")
async def proxy_servico_dados_post(path: str, body: dict):
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{SERVICO_DADOS_URL}/{path}", json=body, timeout=10)
            return resp.json()
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Serviço de dados indisponível: {str(e)}")


@app.get("/resultados/{path:path}")
async def proxy_servico_resultados(path: str):
    """Proxy para o serviço de resultados dos colegas."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{SERVICO_RESULTADOS_URL}/{path}", timeout=10)
            return resp.json()
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Serviço de resultados indisponível: {str(e)}")


@app.post("/resultados/{path:path}")
async def proxy_servico_resultados_post(path: str, body: dict):
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{SERVICO_RESULTADOS_URL}/{path}", json=body, timeout=10)
            return resp.json()
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Serviço de resultados indisponível: {str(e)}")
