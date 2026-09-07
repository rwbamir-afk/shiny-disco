"""Tournament lifecycle with real four-seat Hokm matches, deadlines and forfeits."""
from __future__ import annotations
import json
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..config import get_settings
from ..db import get_db
from ..deps import get_current_user
from ..models import Tournament, TournamentMatch, TournamentParticipant, User, UserProfile, Game, GamePlayer
from ..services.economy_service import debit, credit

router = APIRouter(prefix="/tournaments", tags=["tournaments"])
settings = get_settings()

class TournamentCreateIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    bracket_size: int = Field(default=8, ge=4, le=16)
    entry_fee: int = Field(default=0, ge=0, le=1_000_000)
    prize_coins: int = Field(default=0, ge=0, le=10_000_000)

class MatchResultIn(BaseModel):
    winner_team: str | None = Field(default=None, pattern=r"^[AB]$")
    winner_id: str | None = None
    game_id: str | None = None


def _valid_size(n: int) -> bool: return n in (4, 8, 16)

async def _matches(db, tid: str):
    return (await db.execute(select(TournamentMatch).where(TournamentMatch.tournament_id == tid).order_by(TournamentMatch.round_no, TournamentMatch.slot))).scalars().all()

def _serialize_match(m):
    return {"id": m.id, "round": m.round_no, "slot": m.slot, "player_a_id": m.player_a_id, "player_b_id": m.player_b_id,
            "player_c_id": m.player_c_id, "player_d_id": m.player_d_id, "winner_id": m.winner_id, "game_id": m.game_id,
            "status": m.status, "deadline_at": m.deadline_at.isoformat() if m.deadline_at else None,
            "started_at": m.started_at.isoformat() if m.started_at else None, "finished_at": m.finished_at.isoformat() if m.finished_at else None}

async def _create_match(db, t, round_no, slot, ids):
    deadline = datetime.now(timezone.utc) + timedelta(seconds=settings.reconnect_grace_seconds + 120)
    db.add(TournamentMatch(tournament_id=t.id, round_no=round_no, slot=slot,
        player_a_id=ids[0], player_b_id=ids[1], player_c_id=ids[2], player_d_id=ids[3], status="ready", deadline_at=deadline))

@router.post("")
async def create(body: TournamentCreateIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if not _valid_size(body.bracket_size): raise HTTPException(400, "bracket_size must be 4, 8, or 16")
    t = Tournament(creator_id=user.id, name=body.name.strip(), bracket_size=body.bracket_size, entry_fee=body.entry_fee, prize_coins=body.prize_coins)
    db.add(t); await db.flush(); await db.commit()
    return {"tournament": {"id": t.id, "name": t.name, "bracket_size": t.bracket_size, "status": t.status}}

@router.get("")
async def list_tournaments(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Tournament).where(Tournament.status.in_(["registration", "running"])).order_by(Tournament.created_at.desc()).limit(50))).scalars().all()
    return {"tournaments": [{"id": t.id, "name": t.name, "bracket_size": t.bracket_size, "status": t.status, "entry_fee": t.entry_fee, "prize_coins": t.prize_coins} for t in rows]}

@router.post("/{tid}/join")
async def join(tid: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    t = await db.get(Tournament, tid)
    if not t or t.status != "registration": raise HTTPException(404, "tournament not open")
    existing = (await db.execute(select(TournamentParticipant).where(TournamentParticipant.tournament_id == tid, TournamentParticipant.user_id == user.id))).scalar_one_or_none()
    if existing: return {"ok": True, "status": "joined", "seed": existing.seed}
    participants = (await db.execute(select(TournamentParticipant).where(TournamentParticipant.tournament_id == tid).order_by(TournamentParticipant.seed))).scalars().all()
    if len(participants) >= t.bracket_size: raise HTTPException(409, "tournament is full")
    try:
        if t.entry_fee: await debit(db, user.id, t.entry_fee, "tournament_entry", f"tournament:{tid}:entry:{user.id}", {"tournament_id": tid})
    except ValueError as exc: raise HTTPException(409, str(exc))
    seed = len(participants) + 1
    db.add(TournamentParticipant(tournament_id=tid, user_id=user.id, seed=seed)); await db.commit()
    return {"ok": True, "status": "joined", "seed": seed}

@router.post("/{tid}/start")
async def start(tid: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    t = await db.get(Tournament, tid)
    if not t or t.creator_id != user.id: raise HTTPException(404, "tournament not found")
    if t.status != "registration": raise HTTPException(400, "tournament already started")
    ps = (await db.execute(select(TournamentParticipant).where(TournamentParticipant.tournament_id == tid).order_by(TournamentParticipant.seed))).scalars().all()
    if len(ps) != t.bracket_size: raise HTTPException(400, f"need exactly {t.bracket_size} players")
    for slot in range(t.bracket_size // 4): await _create_match(db, t, 1, slot, [p.user_id for p in ps[slot*4:slot*4+4]])
    t.status = "running"; t.current_round = 1; await db.commit()
    return {"ok": True, "round": 1}

@router.post("/{tid}/matches/{match_id}/start")
async def start_match(tid: str, match_id: str, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    t = await db.get(Tournament, tid); m = await db.get(TournamentMatch, match_id)
    if not t or not m or m.tournament_id != tid or t.status != "running": raise HTTPException(404, "match not found")
    ids = [m.player_a_id, m.player_b_id, m.player_c_id, m.player_d_id]
    if user.id not in ids: raise HTTPException(403, "not a match participant")
    if m.status == "playing" and m.game_id: return {"ok": True, "game_id": m.game_id, "status": "playing"}
    if m.status != "ready" or any(x is None for x in ids): raise HTTPException(409, "match is not ready")
    if m.deadline_at and datetime.now(timezone.utc) > m.deadline_at: raise HTTPException(409, "match deadline expired; forfeit required")
    profiles = (await db.execute(select(UserProfile).where(UserProfile.user_id.in_(ids)))).scalars().all(); by_id={p.user_id:p for p in profiles}
    users=(await db.execute(select(User).where(User.id.in_(ids)))).scalars().all(); by_user={u.id:u for u in users}
    seats=[{"user_id":uid,"is_bot":False,"rating":by_id.get(uid).rating if by_id.get(uid) else 1000,"display_name":by_user.get(uid).first_name if by_user.get(uid) else "بازیکن","username":by_user.get(uid).username if by_user.get(uid) else None} for uid in ids]
    runtime=await request.app.state.game_service.create_game(seats, db=db, config={"source":"tournament","tournament_id":tid,"tournament_match_id":match_id})
    m.game_id=runtime.game_id; m.status="playing"; m.started_at=datetime.now(timezone.utc); await db.commit()
    return {"ok": True, "game_id": runtime.game_id, "status": "playing"}

@router.post("/{tid}/matches/{match_id}/result")
async def result(tid: str, match_id: str, body: MatchResultIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    t=await db.get(Tournament,tid); m=await db.get(TournamentMatch,match_id)
    if not t or not m or m.tournament_id!=tid or t.status!="running": raise HTTPException(404,"match not found")
    if user.id not in {t.creator_id,m.player_a_id,m.player_b_id,m.player_c_id,m.player_d_id}: raise HTTPException(403,"not allowed")
    if m.status=="finished": return {"ok":True,"status":"finished","winner_id":m.winner_id}
    winner_team=body.winner_team
    game_id=body.game_id or m.game_id
    if game_id:
        game=await db.get(Game,game_id)
        if not game or game.tournament_match_id!=m.id: raise HTTPException(400,"invalid tournament game")
        if game.status!="finished": raise HTTPException(409,"game is not finished")
        winner_team=game.winner_team
        m.game_id=game.id
    if winner_team not in {"A","B"}: raise HTTPException(400,"winner_team A or B required")
    winners=[m.player_a_id,m.player_c_id] if winner_team=="A" else [m.player_b_id,m.player_d_id]
    losers=[x for x in [m.player_a_id,m.player_b_id,m.player_c_id,m.player_d_id] if x not in winners]
    m.winner_id=winners[0]; m.status="finished"; m.finished_at=datetime.now(timezone.utc); m.reported_by=user.id
    for loser in losers:
        p=(await db.execute(select(TournamentParticipant).where(TournamentParticipant.tournament_id==tid,TournamentParticipant.user_id==loser))).scalar_one_or_none()
        if p: p.eliminated=True
    round_matches=(await db.execute(select(TournamentMatch).where(TournamentMatch.tournament_id==tid,TournamentMatch.round_no==m.round_no))).scalars().all()
    if not all(x.status in {"finished","bye"} for x in round_matches): await db.commit(); return {"ok":True,"status":"round_in_progress","winner_team":winner_team}
    pair_winners=[]
    for rm in sorted(round_matches,key=lambda x:x.slot):
        team="A" if rm.player_a_id==rm.winner_id else "B"
        pair_winners.append([rm.player_a_id,rm.player_c_id] if team=="A" else [rm.player_b_id,rm.player_d_id])
    if len(pair_winners)==1:
        t.status="finished"; t.winner_id=pair_winners[0][0]
        if t.prize_coins:
            for uid in pair_winners[0]: await credit(db,uid,t.prize_coins//2,"tournament_prize",f"tournament:{tid}:prize:{uid}",{"tournament_id":tid})
        await db.commit(); return {"ok":True,"status":"tournament_finished","winner_ids":pair_winners[0]}
    next_round=m.round_no+1
    for i in range(0,len(pair_winners),2):
        ids=pair_winners[i]+pair_winners[i+1]
        await _create_match(db,t,next_round,i//2,ids)
    t.current_round=next_round; await db.commit(); return {"ok":True,"status":"next_round","round":next_round}

@router.post("/{tid}/matches/{match_id}/forfeit")
async def forfeit(tid:str,match_id:str,body:MatchResultIn,user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    t=await db.get(Tournament,tid); m=await db.get(TournamentMatch,match_id)
    if not t or not m or m.tournament_id!=tid or t.status!="running": raise HTTPException(404,"match not found")
    ids=[m.player_a_id,m.player_b_id,m.player_c_id,m.player_d_id]
    if user.id!=t.creator_id and user.id not in ids: raise HTTPException(403,"not allowed")
    if m.status not in {"ready","playing"}: raise HTTPException(409,"match already resolved")
    team=body.winner_team
    if team not in {"A","B"}:
        if not m.deadline_at or datetime.now(timezone.utc)<=m.deadline_at: raise HTTPException(400,"winner_team required before deadline")
        team="B" if user.id in {m.player_a_id,m.player_c_id} else "A"
    m.status="forfeit"; m.winner_id=m.player_a_id if team=="A" else m.player_b_id; m.finished_at=datetime.now(timezone.utc); m.reported_by=user.id
    losers=[m.player_b_id,m.player_d_id] if team=="A" else [m.player_a_id,m.player_c_id]
    for uid in losers:
        p=(await db.execute(select(TournamentParticipant).where(TournamentParticipant.tournament_id==tid,TournamentParticipant.user_id==uid))).scalar_one_or_none()
        if p:p.eliminated=True
    # Treat forfeit as a completed round; use the same progression logic by marking the match finished after recording.
    m.status="finished"
    round_matches=(await db.execute(select(TournamentMatch).where(TournamentMatch.tournament_id==tid,TournamentMatch.round_no==m.round_no))).scalars().all()
    if not all(x.status in {"finished","bye"} for x in round_matches): await db.commit(); return {"ok":True,"status":"round_in_progress"}
    pair_winners=[]
    for rm in sorted(round_matches,key=lambda x:x.slot):
        team_rm="A" if rm.player_a_id==rm.winner_id else "B"; pair_winners.append([rm.player_a_id,rm.player_c_id] if team_rm=="A" else [rm.player_b_id,rm.player_d_id])
    if len(pair_winners)==1:
        t.status="finished"; t.winner_id=pair_winners[0][0]; await db.commit(); return {"ok":True,"status":"tournament_finished","winner_ids":pair_winners[0]}
    nr=m.round_no+1
    for i in range(0,len(pair_winners),2): await _create_match(db,t,nr,i//2,pair_winners[i]+pair_winners[i+1])
    t.current_round=nr; await db.commit(); return {"ok":True,"status":"next_round","round":nr}

@router.get("/{tid}")
async def get(tid:str,db:AsyncSession=Depends(get_db)):
    t=await db.get(Tournament,tid)
    if not t: raise HTTPException(404,"tournament not found")
    ps=(await db.execute(select(TournamentParticipant).where(TournamentParticipant.tournament_id==tid).order_by(TournamentParticipant.seed))).scalars().all(); ms=await _matches(db,tid)
    return {"tournament":{"id":t.id,"name":t.name,"bracket_size":t.bracket_size,"status":t.status,"current_round":t.current_round,"winner_id":t.winner_id,"entry_fee":t.entry_fee,"prize_coins":t.prize_coins},"participants":[{"user_id":p.user_id,"seed":p.seed,"eliminated":p.eliminated} for p in ps],"matches":[_serialize_match(m) for m in ms]}
