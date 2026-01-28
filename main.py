"""
Backend IA ELYSÉEDEN™ V2 - ULTRA-PERFORMANT
FastAPI + Claude Sonnet 4 + Optimisations
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, List
import anthropic
import os
import time
import logging
from functools import lru_cache
from datetime import datetime
import hashlib
import json

# Configuration Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="ELYSÉEDEN IA Backend V2",
    description="Backend ultra-performant pour l'IA ELYSÉEDEN™",
    version="2.0.0"
)

# ============================================
# MIDDLEWARE - PERFORMANCE
# ============================================

# Compression GZIP (réponses 60% plus petites)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# CORS optimisé
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://www.elyseeden.com",
        "https://www.elyseeden.com",
        "http://elyseeden.com",
        "https://elyseeden.com"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    max_age=3600  # Cache preflight 1h
)

# Middleware temps de réponse
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(round(process_time, 3))
    logger.info(f"{request.method} {request.url.path} - {process_time:.3f}s")
    return response

# ============================================
# CACHE SIMPLE (IN-MEMORY)
# ============================================

class SimpleCache:
    def __init__(self, max_size=100, ttl=3600):
        self.cache = {}
        self.max_size = max_size
        self.ttl = ttl
    
    def get(self, key: str):
        if key in self.cache:
            data, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                logger.info(f"Cache HIT: {key[:20]}...")
                return data
            else:
                del self.cache[key]
        return None
    
    def set(self, key: str, value):
        if len(self.cache) >= self.max_size:
            # Supprimer plus ancien
            oldest = min(self.cache.items(), key=lambda x: x[1][1])
            del self.cache[oldest[0]]
        self.cache[key] = (value, time.time())
        logger.info(f"Cache SET: {key[:20]}...")

# Cache global
response_cache = SimpleCache(max_size=100, ttl=1800)  # 30 min TTL

# ============================================
# RATE LIMITING SIMPLE
# ============================================

class RateLimiter:
    def __init__(self, max_requests=30, window=60):
        self.requests = {}
        self.max_requests = max_requests
        self.window = window
    
    def is_allowed(self, client_id: str) -> bool:
        now = time.time()
        if client_id not in self.requests:
            self.requests[client_id] = []
        
        # Nettoyer anciennes requêtes
        self.requests[client_id] = [
            req_time for req_time in self.requests[client_id]
            if now - req_time < self.window
        ]
        
        if len(self.requests[client_id]) >= self.max_requests:
            logger.warning(f"Rate limit exceeded for {client_id}")
            return False
        
        self.requests[client_id].append(now)
        return True

rate_limiter = RateLimiter(max_requests=30, window=60)  # 30 req/min

# ============================================
# MODÈLES PYDANTIC
# ============================================

class Message(BaseModel):
    role: str = Field(..., description="user ou assistant")
    content: str = Field(..., min_length=1, max_length=10000)

class ChatRequest(BaseModel):
    messages: List[Message] = Field(..., min_items=1, max_items=50)
    pillar: str = Field(default="general", description="Pilier d'expertise")
    stream: bool = Field(default=False, description="Streaming activé")
    temperature: float = Field(default=0.7, ge=0, le=1)
    max_tokens: int = Field(default=2000, ge=100, le=4000)

class ChatResponse(BaseModel):
    response: str
    pillar: str
    cached: bool = False
    process_time: float
    tokens_used: Optional[int] = None

class ErrorResponse(BaseModel):
    error: str
    detail: str
    timestamp: str

# ============================================
# GESTION ERREURS GLOBALE
# ============================================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global error: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc),
            "timestamp": datetime.utcnow().isoformat()
        }
    )

# ============================================
# ROUTES SANTÉ
# ============================================

@app.get("/")
async def root():
    return {
        "status": "healthy",
        "service": "ELYSÉEDEN IA Backend V2",
        "version": "2.0.0",
        "features": [
            "Compression GZIP",
            "Cache intelligent",
            "Rate limiting",
            "Logging avancé",
            "Gestion erreurs robuste"
        ]
    }

@app.get("/health")
async def health():
    """Health check détaillé"""
    try:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "api_configured": bool(api_key),
            "cache_size": len(response_cache.cache),
            "uptime": "OK"
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(status_code=503, detail="Service unhealthy")

# ============================================
# PROMPTS SYSTÈME OPTIMISÉS
# ============================================

SYSTEM_PROMPTS = {
    "general": """Tu es ELYSÉEDEN™, Expert IA premium pour dirigeants et décideurs.

EXPERTISE :
- Stratégie d'entreprise et vision long terme
- Organisation et transformation
- Leadership et management
- Performance opérationnelle

STYLE :
- Professionnel mais accessible
- Concis et actionnable
- Structuré (listes, étapes)
- Exemples concrets

FORMATAGE :
- Utilise Markdown (**, ##, -, etc.)
- Structure avec headers
- Listes pour clarté
- Gras pour points clés

PRINCIPES :
- Pas de langue de bois
- Solutions pragmatiques
- Vision business
- ROI et résultats""",

    "croissance": """Expert M&A et croissance externe.

Focus : Fusions-acquisitions, due diligence, intégration post-acquisition, synergies, valorisation.

Approche : Chiffres précis, risques identifiés, plan d'action 100 jours.""",

    "crise": """Expert gestion de crise et restructuring.

Focus : Diagnostic rapide, plan urgence, cash management, restructuration, retournement.

Approche : Pragmatisme, décisions rapides, priorisation, résultats mesurables.""",

    "conflits": """Expert résolution conflits et médiation.

Focus : Analyse parties prenantes, médiation, gouvernance, management transition.

Approche : Écoute, neutralité, solutions gagnant-gagnant, apaisement.""",

    "processus": """Expert excellence opérationnelle.

Focus : Lean, Six Sigma, optimisation processus, automatisation, KPIs.

Approche : Données, amélioration continue, quick wins, ROI.""",

    "intelligence": """Expert business intelligence et analytics.

Focus : Dashboards, KPIs, data analytics, aide décision, prédictif.

Approche : Visualisation, insights actionnables, tendances, recommandations."""
}

# ============================================
# FONCTION CACHE KEY
# ============================================

def generate_cache_key(messages: List[Message], pillar: str) -> str:
    """Générer clé cache unique"""
    content = json.dumps([{"role": m.role, "content": m.content} for m in messages])
    content += pillar
    return hashlib.md5(content.encode()).hexdigest()

# ============================================
# ROUTE CHAT OPTIMISÉE
# ============================================

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, req: Request):
    """
    Endpoint chat ultra-optimisé avec cache et rate limiting
    """
    start_time = time.time()
    
    # Rate limiting
    client_ip = req.client.host
    if not rate_limiter.is_allowed(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Trop de requêtes. Limite : 30/minute. Réessayez dans 60s."
        )
    
    # Vérifier clé API
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        logger.error("ANTHROPIC_API_KEY not configured")
        raise HTTPException(
            status_code=500,
            detail="API non configurée. Contactez l'administrateur."
        )
    
    # Générer cache key
    cache_key = generate_cache_key(request.messages, request.pillar)
    
    # Vérifier cache
    cached_response = response_cache.get(cache_key)
    if cached_response:
        process_time = time.time() - start_time
        return ChatResponse(
            response=cached_response,
            pillar=request.pillar,
            cached=True,
            process_time=round(process_time, 3)
        )
    
    try:
        # Initialiser client Anthropic
        client = anthropic.Anthropic(api_key=api_key, timeout=30.0)
        
        # Prompt système
        system_prompt = SYSTEM_PROMPTS.get(request.pillar, SYSTEM_PROMPTS["general"])
        
        # Préparer messages
        messages = [{"role": msg.role, "content": msg.content} for msg in request.messages]
        
        # Appel API Claude avec timeout
        logger.info(f"Calling Claude API - Pillar: {request.pillar}")
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            system=system_prompt,
            messages=messages
        )
        
        # Extraire réponse
        assistant_message = response.content[0].text
        tokens_used = response.usage.input_tokens + response.usage.output_tokens
        
        # Mettre en cache
        response_cache.set(cache_key, assistant_message)
        
        process_time = time.time() - start_time
        
        logger.info(f"Response generated - {tokens_used} tokens - {process_time:.3f}s")
        
        return ChatResponse(
            response=assistant_message,
            pillar=request.pillar,
            cached=False,
            process_time=round(process_time, 3),
            tokens_used=tokens_used
        )
        
    except anthropic.APITimeoutError:
        logger.error("Claude API timeout")
        raise HTTPException(
            status_code=504,
            detail="L'IA met trop de temps à répondre. Réessayez avec une question plus courte."
        )
    
    except anthropic.RateLimitError:
        logger.error("Claude API rate limit")
        raise HTTPException(
            status_code=429,
            detail="Limite API atteinte. Réessayez dans quelques secondes."
        )
    
    except anthropic.APIError as e:
        logger.error(f"Anthropic API error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erreur API Claude : {str(e)}"
        )
    
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erreur serveur : {str(e)}"
        )

# ============================================
# ROUTE STATS
# ============================================

@app.get("/stats")
async def get_stats():
    """Statistiques backend"""
    return {
        "cache": {
            "size": len(response_cache.cache),
            "max_size": response_cache.max_size,
            "ttl": response_cache.ttl
        },
        "rate_limiter": {
            "active_clients": len(rate_limiter.requests),
            "max_requests": rate_limiter.max_requests,
            "window": rate_limiter.window
        },
        "timestamp": datetime.utcnow().isoformat()
    }

# ============================================
# ROUTE PILLARS
# ============================================

@app.get("/pillars")
async def get_pillars():
    """Liste des piliers d'expertise"""
    return {
        "pillars": [
            {
                "id": "general",
                "name": "Général",
                "icon": "🎯",
                "description": "Expert tous domaines"
            },
            {
                "id": "croissance",
                "name": "Croissance Externe",
                "icon": "🚀",
                "description": "M&A, fusions-acquisitions"
            },
            {
                "id": "crise",
                "name": "Crise & Restructuring",
                "icon": "🔥",
                "description": "Retournement, restructuration"
            },
            {
                "id": "conflits",
                "name": "Conflits & Transition",
                "icon": "🤝",
                "description": "Médiation, gouvernance"
            },
            {
                "id": "processus",
                "name": "Excellence Processus",
                "icon": "⚙️",
                "description": "Lean, optimisation"
            },
            {
                "id": "intelligence",
                "name": "Intelligence Décision",
                "icon": "📊",
                "description": "Analytics, dashboards"
            }
        ]
    }

# ============================================
# DÉMARRAGE
# ============================================

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    logger.info(f"Starting ELYSÉEDEN IA Backend V2 on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
