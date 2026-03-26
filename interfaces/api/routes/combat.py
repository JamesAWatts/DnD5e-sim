from fastapi import APIRouter
from interfaces.api.services.combat_service import simulate_combat

router = APIRouter(prefix="/combat", tags=["combat"])

@router.post("/")
def run_combat():
    result = simulate_combat()
    return {"result": result}