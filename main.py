"""
Backend IA ELYSÉEDEN™
FastAPI + Claude Sonnet 4
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import anthropic
import os

app = FastAPI(title="ELYSÉEDEN IA Backend")

# CORS - À configurer selon domaine en production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En production: ["https://www.elyseeden.com"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Modèles Pydantic
class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: list[Message]
    pillar: str = "general"

class ChatResponse(BaseModel):
    response: str
    pillar: str

# Route santé
@app.get("/")
async def root():
    return {"status": "healthy", "service": "ELYSÉEDEN IA Backend"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

# Route chat IA
@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Endpoint principal chat avec Claude
    """
    try:
        # Récupérer clé API Anthropic
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured")
        
        # Initialiser client Anthropic
        client = anthropic.Anthropic(api_key=api_key)
        
        # Système prompt selon pilier
        system_prompts = {
            "croissance": "Tu es un expert en croissance externe, M&A et fusions-acquisitions. Tu aides les dirigeants dans leurs stratégies de croissance.",
            "crise": "Tu es un expert en gestion de crise et restructuring. Tu aides les dirigeants à sortir rapidement des situations difficiles.",
            "conflits": "Tu es un expert en résolution de conflits et management de transition. Tu aides à rétablir la gouvernance.",
            "processus": "Tu es un expert en excellence opérationnelle et optimisation des processus. Tu aides à améliorer l'efficacité.",
            "intelligence": "Tu es un expert en business intelligence et analytics. Tu aides à transformer les données en décisions.",
            "general": "Tu es l'Expert IA ELYSÉEDEN™, assistant premium pour dirigeants. Tu combines expertise en stratégie, organisation et transformation d'entreprise."
        }
        
        system_prompt = system_prompts.get(request.pillar, system_prompts["general"])
        
        # Préparer messages pour Claude
        messages = [{"role": msg.role, "content": msg.content} for msg in request.messages]
        
        # Appel API Claude
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            system=system_prompt,
            messages=messages
        )
        
        # Extraire réponse
        assistant_message = response.content[0].text
        
        return ChatResponse(
            response=assistant_message,
            pillar=request.pillar
        )
        
    except anthropic.APIError as e:
        raise HTTPException(status_code=500, detail=f"Anthropic API error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

# Route info piliers
@app.get("/pillars")
async def get_pillars():
    """
    Retourne la liste des 5 piliers
    """
    return {
        "pillars": [
            {
                "id": "croissance",
                "name": "Croissance Externe",
                "icon": "🚀",
                "description": "M&A, fusions-acquisitions, due diligence"
            },
            {
                "id": "crise",
                "name": "Crise & Restructuring",
                "icon": "🔥",
                "description": "Diagnostic, plan 90j, restructuration"
            },
            {
                "id": "conflits",
                "name": "Conflits & Transition",
                "icon": "🤝",
                "description": "Résolution conflits, médiation"
            },
            {
                "id": "processus",
                "name": "Excellence Processus",
                "icon": "⚙️",
                "description": "Optimisation, lean, automatisation"
            },
            {
                "id": "intelligence",
                "name": "Intelligence Décision",
                "icon": "📊",
                "description": "Dashboards, KPIs, analytics"
            }
        ]
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
