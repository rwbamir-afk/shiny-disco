"""Idempotent post-game result processing (Section 34/35).

Runs under the per-game lock, so only one finalization can be in flight per game.
The status transition ('playing' -> 'finished') is the additional idempotency
guard: a second call sees status != 'playing' and returns without awarding twice.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import select

from ..models import Game as GameModel
from ..models import GamePlayer, Tournament, TournamentMatch, TournamentParticipant
from .economy_service import credit, ensure_wallet
from .premium_service import add_battle_pass_xp
from .progression_service import ensure_catalog
from .user_service import (
    level_for_xp,
    opponent_avg_rating,
    profile_public,
    team_rating_change,
    xp_award_for_result,
)


class ResultProcessor:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    async def _advance_tournament(self, db, game, gp_rows, winner_team: str) -> dict | None:
        if not game.tournament_match_id:
            return None
        match = await db.get(TournamentMatch, game.tournament_match_id)
        if match is None or match.status == "finished":
            return None
        tournament = await db.get(Tournament, match.tournament_id)
        if tournament is None or tournament.status != "running":
            return None
        winning_ids = [gp.user_id for gp in gp_rows if gp.team == winner_team and gp.user_id]
        losing_ids = [gp.user_id for gp in gp_rows if gp.team != winner_team and gp.user_id]
        match.winner_id = winning_ids[0] if winning_ids else None
        match.game_id = game.id
        match.status = "finished"
        for uid in losing_ids:
            row = (await db.execute(select(TournamentParticipant).where(TournamentParticipant.tournament_id == tournament.id, TournamentParticipant.user_id == uid))).scalar_one_or_none()
            if row:
                row.eliminated = True
        # Wait until every match in the round is finished, then form the next round
        # from winning teams (two seats per winning team).
        current = (await db.execute(select(TournamentMatch).where(TournamentMatch.tournament_id == tournament.id, TournamentMatch.round_no == match.round_no).order_by(TournamentMatch.slot))).scalars().all()
        if not all(x.status == "finished" for x in current):
            return {"status": "round_in_progress", "round": match.round_no}
        teams: list[list[str]] = []
        for m in current:
            ids = [m.player_a_id, m.player_b_id, m.player_c_id, m.player_d_id]
            # The winning team is the two seats belonging to the game winner.
            game_players = (await db.execute(select(GamePlayer).where(GamePlayer.game_id == m.game_id).order_by(GamePlayer.seat))).scalars().all()
            team_ids = [gp.user_id for gp in game_players if gp.team == (winner_team if m.id == match.id else "")]
            if not team_ids:
                # Derive the winning team from the persisted game result for other matches.
                other_game = await db.get(type(game), m.game_id) if m.game_id else None
                if other_game:
                    result_team = other_game.winner_team
                    team_ids = [gp.user_id for gp in game_players if gp.team == result_team]
            if len(team_ids) == 2:
                teams.append(team_ids)
        advancing = [uid for team in teams for uid in team]
        if len(advancing) == 2:
            tournament.status = "finished"
            tournament.winner_id = advancing[0]
            # Split the configured prize across the winning pair, idempotently.
            if tournament.prize_coins:
                half = tournament.prize_coins // 2
                remainder = tournament.prize_coins - half
                for i, uid in enumerate(advancing):
                    await credit(db, uid, half if i == 0 else remainder, "tournament_prize", f"tournament:{tournament.id}:prize:{uid}", {"tournament_id": tournament.id})
            return {"status": "tournament_finished", "winner_ids": advancing}
        next_round = match.round_no + 1
        tournament.current_round = next_round
        for slot in range(0, len(advancing), 4):
            group = advancing[slot:slot + 4]
            if len(group) < 4:
                break
            db.add(TournamentMatch(tournament_id=tournament.id, round_no=next_round, slot=slot // 4,
                                   player_a_id=group[0], player_b_id=group[1], player_c_id=group[2], player_d_id=group[3], status="ready"))
        return {"status": "next_round", "round": next_round, "advancing": len(advancing)}

    async def finalize(self, game_id: str, runtime) -> dict:
        async with self._session_factory() as db:
            game = await db.get(GameModel, game_id)
            if game is None or game.status != "playing":
                # Already finalized or aborted -> idempotent no-op.
                return {"finalized": False}

            result = runtime.engine.result()
            config = json.loads(game.config or "{}")
            variant = config.get("variant", "classic_4p")
            if variant == "classic_4p":
                winner_team = result["winner_team"]
                scores = result["scores"]
            else:
                winner_seat = int(result["winner_seat"])
                winner_team = chr(65 + winner_seat)
                scores = result["scores"]

            gp_rows = (
                (await db.execute(select(GamePlayer).where(GamePlayer.game_id == game_id)))
                .scalars()
                .all()
            )

            # Gather seat -> (user_id, team, rating, profile).
            seat_meta = {}
            profiles = {}
            for gp in gp_rows:
                from ..models import UserProfile

                prof = (
                    (await db.execute(select(UserProfile).where(UserProfile.user_id == gp.user_id)))
                    .scalar_one_or_none()
                )
                if prof is None:
                    continue
                profiles[gp.user_id] = prof
                seat_meta[gp.seat] = {"user_id": gp.user_id, "team": gp.team, "rating": prof.rating}

            # Compute ratings.
            team_ratings = {}
            for m in seat_meta.values():
                team_ratings.setdefault(m["team"], []).append(m["rating"])

            rating_changes: dict[str, int] = {}
            xp_changes: dict[str, int] = {}
            coin_changes: dict[str, int] = {}
            for gp in gp_rows:
                user_id = gp.user_id
                prof = profiles.get(user_id)
                if prof is None:
                    continue
                won = gp.team == winner_team
                if variant == "classic_4p":
                    opp_team = "B" if gp.team == "A" else "A"
                    opp_avg = opponent_avg_rating(team_ratings.get(opp_team, []))
                else:
                    opponents = [r for team, values in team_ratings.items() if team != gp.team for r in values]
                    opp_avg = opponent_avg_rating(opponents)
                delta = team_rating_change(prof.rating, opp_avg, won)
                prof.rating = max(100, prof.rating + delta)
                prof.peak_rating = max(prof.peak_rating, prof.rating)

                # XP / level / streak.
                streak = prof.streak + 1 if won else 0
                prof.streak = streak
                prof.max_streak = max(prof.max_streak, streak)
                xp_gain = xp_award_for_result(won, prof.streak)
                prof.xp += xp_gain
                prof.level = level_for_xp(prof.xp)

                prof.games_played += 1
                if won:
                    prof.wins += 1
                else:
                    prof.losses += 1

                rating_changes[user_id] = delta
                xp_changes[user_id] = xp_gain
                gp.rating_change = delta
                gp.xp_gained = xp_gain

                # Competitive games also feed the durable economy. The idempotency key
                # is tied to this game/player so retries can never double-pay.
                coin_gain = 100 if won else 25
                await credit(db, user_id, coin_gain, "game_result", f"game:{game_id}:coins:{user_id}", {"game_id": game_id, "won": won})
                coin_changes[user_id] = coin_gain
                gp.coins_gained = coin_gain
                # Seasonal Battle Pass progression mirrors completed-game XP.
                await add_battle_pass_xp(db, user_id, xp_gain, f"game:{game_id}:bp:{user_id}")

            # Mark the game finished (idempotency guard set BEFORE commit).
            game.status = "finished"
            game.winner_team = winner_team
            game.final_scores = json.dumps(scores)
            game.finished_at = datetime.now(timezone.utc)
            # Refresh progression records after profile counters changed.
            await ensure_catalog(db)
            from ..models import Mission, UserMission, Achievement, UserAchievement
            for mission in (await db.execute(select(Mission).where(Mission.active.is_(True)))).scalars().all():
                um = (await db.execute(select(UserMission).where(UserMission.user_id.in_(list(profiles.keys())), UserMission.mission_id == mission.id))).scalars().all()
                for row in um:
                    prof = profiles.get(row.user_id)
                    if prof:
                        row.progress = min(mission.target, int(getattr(prof, mission.metric, 0)))
            for achievement in (await db.execute(select(Achievement).where(Achievement.active.is_(True)))).scalars().all():
                for uid, prof in profiles.items():
                    current = int(getattr(prof, achievement.metric, 0))
                    if current >= achievement.target:
                        exists = (await db.execute(select(UserAchievement).where(UserAchievement.user_id == uid, UserAchievement.achievement_id == achievement.id))).scalar_one_or_none()
                        if exists is None:
                            db.add(UserAchievement(user_id=uid, achievement_id=achievement.id, unlocked_at=datetime.now(timezone.utc)))
                            await credit(db, uid, achievement.reward_coins, "achievement_reward", f"achievement:{uid}:{achievement.id}")
                            prof.xp += achievement.reward_xp
                            prof.level = level_for_xp(prof.xp)
            # Tournament progression is finalized from the authoritative game result.
            tournament_result = await self._advance_tournament(db, game, gp_rows, winner_team) if variant == "classic_4p" else None
            await db.commit()

            return {
                "finalized": True,
                "winner_team": winner_team,
                "scores": scores,
                "rating_changes": rating_changes,
                "xp_changes": xp_changes,
                "coin_changes": coin_changes,
                "tournament": tournament_result,
            }
