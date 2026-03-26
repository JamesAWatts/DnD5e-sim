from fastapi import APIRouter
from interfaces.api.models.player import PlayerCreate, PlayerResponse

router = APIRouter(prefix="/players", tags=["players"])

# Temporary in-memory storage (we’ll replace later)
players_db = {}
player_id_counter = 1


@router.post("/", response_model=PlayerResponse)
def create_player(player: PlayerCreate):
    global player_id_counter

    new_player = {
        "id": player_id_counter,
        "name": player.name,
        "hp": player.hp
    }

    players_db[player_id_counter] = new_player
    player_id_counter += 1

    return new_player


@router.get("/{player_id}", response_model=PlayerResponse)
def get_player(player_id: int):
    return players_db.get(player_id)