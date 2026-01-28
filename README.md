# ELYSÉEDEN™ IA Backend

Backend FastAPI pour l'application IA ELYSÉEDEN™

## Technologies

- **FastAPI** - Framework web Python moderne
- **Claude Sonnet 4** - IA Anthropic
- **Uvicorn** - Serveur ASGI

## Endpoints

### GET /
Status du service

### GET /health
Health check

### POST /chat
Chat avec l'IA
```json
{
  "messages": [
    {"role": "user", "content": "Bonjour"}
  ],
  "pillar": "general"
}
```

### GET /pillars
Liste des 5 piliers d'expertise

## Variables d'environnement

- `ANTHROPIC_API_KEY` - Clé API Claude (requis)
- `PORT` - Port serveur (défaut: 8000)

## Déploiement Railway

1. Push sur GitHub
2. Connecter Railway au repo
3. Configurer ANTHROPIC_API_KEY
4. Deploy automatique

## Local

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY="your-key"
uvicorn main:app --reload
```

---

🎩💎 ELYSÉEDEN™
"Votre performance, c'est notre métier"
