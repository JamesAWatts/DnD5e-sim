from fastapi import FastAPI
from interfaces.api.routes import players, combat

app = FastAPI(title="5esim API")

app.include_router(players.router)
app.include_router(combat.router)

@app.get("/health")
def health():
    return {"status": "ok"}