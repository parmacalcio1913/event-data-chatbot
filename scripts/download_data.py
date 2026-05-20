"""Download StatsBomb competitions, matches and events into a local DuckDB database.

Run once to populate data/statsbomb.duckdb. The MCP server reads from that file
and never touches the StatsBomb API at request time.
"""

from pathlib import Path

import duckdb
import pandas as pd
from statsbombpy import sb
from tqdm import tqdm

COMPETITION_NAMES = [
    "1. Bundesliga",
    "La Liga",
    "Ligue 1",
    "Premier League",
    "Serie A",
]
SEASON_NAMES = ["2015/2016"]

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "statsbomb.duckdb"

# Array/blob columns that don't belong in a flat SQL table.
EVENT_DROP_COLUMNS = [
    "related_events",
    "shot_freeze_frame",
    "freeze_frame",
    "tactics",
    "timestamp",
    "50_50",
]

# StatsBomb location arrays -> flat x/y(/z) columns. The source array column
# is dropped after the split.
LOCATION_SPLITS = {
    "location": "location",
    "pass_end_location": "pass_end",
    "carry_end_location": "carry_end",
    "shot_end_location": "shot_end",
    "goalkeeper_end_location": "goalkeeper_end",
}

EVENTS_TABLE_COMMENT = (
    "One row per match event (~3000-4000 per match). Pitch coordinates are "
    "120x80: x runs 0-120 toward the attacking goal at x=120, y runs 0-80; the "
    "goal mouth is x=120 with y 36-44 and the penalty box is x>=102 with y "
    "18-62. IMPORTANT: boolean attribute columns (under_pressure, counterpress, "
    "out, off_camera, shot_first_time, pass_cross, ...) are only ever TRUE or "
    "NULL - StatsBomb never stores FALSE - so test the false case with "
    "'IS NOT TRUE', never '= FALSE'. Type-specific columns (shot_*, pass_*, "
    "dribble_*, ...) are NULL on events of other types; e.g. shot_statsbomb_xg "
    "is set only where type = 'Shot'. Run SELECT DISTINCT on a categorical "
    "column to read its exact values. Join to the matches table on match_id. "
    "The freeze_frame and related_events arrays are intentionally excluded."
)

EVENT_COLUMN_COMMENTS = {
    "type": (
        "Event type - Pass, Ball Receipt*, Carry, Pressure, Ball Recovery, "
        "Duel, Shot, Dribble, Interception, Clearance, Block, Foul Committed, "
        "Foul Won, Goal Keeper, Substitution, etc. SELECT DISTINCT type for "
        "the full list (~33 values)."
    ),
    "index": "Sequential order of the event within the match (1 = first event).",
    "period": "Match period: 1 = first half, 2 = second half, 3-4 = extra time, 5 = shootout.",
    "possession": "Possession-sequence number within the match - one team's unbroken spell of control.",
    "possession_team": "Team in control during this possession (shown even on the opponent's events).",
    "play_pattern": (
        "How the possession started: Regular Play, From Corner, From Free "
        "Kick, From Throw In, From Counter, From Goal Kick, From Keeper, "
        "From Kick Off, Other."
    ),
    "team": "Name of the team the event belongs to.",
    "player": "Name of the player the event belongs to (NULL for team-level events).",
    "position": "Player's tactical position at the time (Goalkeeper, Center Back, Left Wing, ...).",
    "location_x": "Event x coordinate on a 120x80 pitch, 0-120, attacking toward x=120.",
    "location_y": "Event y coordinate on a 120x80 pitch, 0-80.",
    "duration": "Length of the event in seconds, where relevant.",
    "under_pressure": "TRUE if performed under defensive pressure; otherwise NULL - never FALSE.",
    "counterpress": "TRUE if a pressing action within 5s of an open-play turnover; otherwise NULL.",
    "out": "TRUE if the event put the ball out of bounds; otherwise NULL.",
    "off_camera": "TRUE if the event occurred while the broadcast camera was off; otherwise NULL.",
    "shot_statsbomb_xg": "StatsBomb expected-goals (xG) value of the shot, 0-1. Set only where type = 'Shot'.",
    "shot_outcome": (
        "Shot result - Goal, Saved, Blocked, Off T, Post, Wayward, Saved Off "
        "T, Saved To Post. Goals are shot_outcome = 'Goal'."
    ),
    "shot_type": "How the shot originated - Open Play, Free Kick, Corner, Penalty, Kick Off.",
    "shot_body_part": "Body part used for the shot - Head, Left Foot, Right Foot, Other.",
    "shot_technique": "Shot technique - Normal, Volley, Half Volley, Lob, Backheel, Diving Header, Overhead Kick.",
    "shot_end_x": "x coordinate where the shot ended.",
    "shot_end_y": "y coordinate where the shot ended.",
    "shot_end_z": "Height (z) where the shot crossed the goal line; the goal frame is z 0-2.67.",
    "shot_first_time": "TRUE if a first-touch shot; otherwise NULL.",
    "shot_one_on_one": "TRUE if the shot was one-on-one with the keeper; otherwise NULL.",
    "shot_open_goal": "TRUE if taken with an open goal; otherwise NULL.",
    "shot_aerial_won": "TRUE if the shooter won an aerial duel for the shot; otherwise NULL.",
    "shot_key_pass_id": "id of the Pass event that created this shot (the key pass).",
    "pass_outcome": (
        "Pass result - Incomplete, Out, Pass Offside, Injury Clearance, "
        "Unknown. NULL means the pass was completed successfully."
    ),
    "pass_height": "Pass height - Ground Pass, Low Pass, High Pass.",
    "pass_length": "Pass length in yards.",
    "pass_angle": "Pass direction in radians: 0 = straight ahead, positive = clockwise, range -pi..pi.",
    "pass_type": (
        "Set-piece origin - Corner, Free Kick, Goal Kick, Throw-in, Kick Off, "
        "Recovery, Interception. NULL = open-play pass."
    ),
    "pass_body_part": "Body part used - Right Foot, Left Foot, Head, Keeper Arm, Drop Kick, No Touch, Other.",
    "pass_technique": "Pass technique - Inswinging, Outswinging, Straight, Through Ball.",
    "pass_recipient": "Name of the intended receiver of the pass.",
    "pass_end_x": "x coordinate where the pass ended.",
    "pass_end_y": "y coordinate where the pass ended.",
    "pass_cross": "TRUE if the pass was a cross; otherwise NULL.",
    "pass_switch": "TRUE if the pass switched play across the pitch; otherwise NULL.",
    "pass_cut_back": "TRUE if the pass was a cut-back; otherwise NULL.",
    "pass_goal_assist": "TRUE if the pass directly assisted a goal; otherwise NULL.",
    "pass_shot_assist": "TRUE if the pass assisted a shot that did not score; otherwise NULL.",
    "pass_assisted_shot_id": "id of the Shot event this pass set up.",
    "carry_end_x": "x coordinate where the carry ended.",
    "carry_end_y": "y coordinate where the carry ended.",
    "dribble_outcome": "Dribble result - Complete or Incomplete.",
    "dribble_nutmeg": "TRUE if the dribble nutmegged the opponent; otherwise NULL.",
    "duel_type": "Duel type - Aerial Lost, Tackle.",
    "duel_outcome": "Duel result - Won, Lost In Play, Lost Out, Success In Play, Success Out, etc.",
    "goalkeeper_type": (
        "Goalkeeper action - Shot Faced, Shot Saved, Save, Smother, Collected, "
        "Punch, Keeper Sweeper, Goal Conceded, Penalty Saved, etc."
    ),
    "goalkeeper_outcome": "Outcome of the goalkeeper action.",
    "interception_outcome": "Interception result - Won, Success In Play, Lost In Play, etc.",
    "foul_committed_card": "Card shown for the foul - Yellow Card, Second Yellow, Red Card.",
    "foul_committed_type": "Foul type - Handball, Dangerous Play, Dive, Foul Out, 6 Seconds, Backpass Pick.",
    "foul_committed_penalty": "TRUE if the foul conceded a penalty; otherwise NULL.",
    "foul_won_penalty": "TRUE if winning the foul earned a penalty; otherwise NULL.",
    "bad_behaviour_card": "Card for off-ball misconduct - Yellow Card, Second Yellow, Red Card.",
    "substitution_replacement": "Player coming on; the row's player is the one going off.",
    "substitution_outcome": "Reason for the substitution - Injury or Tactical.",
    "tactics": "Team formation (e.g. 433, 4231) - set on Starting XI and Tactical Shift events.",
}


LINEUPS_TABLE_COMMENT = (
    "One row per player per match - starters, used substitutes, and unused "
    "substitutes. Use it to build a mini match summary: who started, who came "
    "on, and who was booked or sent off. A starter has "
    "on_the_pitch_from_timestamp = '00:00' and on_the_pitch_from_period = 1; a "
    "used substitute came on later; an unused substitute has every "
    "on_the_pitch_* column NULL. on_the_pitch_to_* is NULL for a player still "
    "on the pitch at the final whistle. Clock columns are 'MM:SS' strings "
    "counting within the period. Join to the matches table on match_id, and to "
    "the events table on match_id plus player_name = events.player."
)

LINEUP_COLUMNS = [
    "match_id",
    "team_id",
    "team_name",
    "player_id",
    "player_name",
    "player_nickname",
    "jersey_number",
    "country_name",
    "position_name",
    "on_the_pitch_from_timestamp",
    "on_the_pitch_to_timestamp",
    "on_the_pitch_from_period",
    "on_the_pitch_to_period",
    "first_yellow_card_timestamp",
    "first_yellow_card_period",
    "first_yellow_card_reason",
    "second_yellow_card_timestamp",
    "second_yellow_card_period",
    "second_yellow_card_reason",
    "red_card_timestamp",
    "red_card_period",
    "red_card_reason",
]

# Nullable-integer columns: unused substitutes leave the period columns empty,
# so pandas would otherwise widen them to float.
LINEUP_INT_COLUMNS = [
    "jersey_number",
    "on_the_pitch_from_period",
    "on_the_pitch_to_period",
    "first_yellow_card_period",
    "second_yellow_card_period",
    "red_card_period",
]

LINEUP_COLUMN_COMMENTS = {
    "match_id": "Match this row belongs to. Join to the matches table.",
    "team_id": "id of the team the player was listed for.",
    "team_name": "Name of the team the player was listed for.",
    "player_id": "StatsBomb id of the player.",
    "player_name": "Full name of the player; equals events.player for this match.",
    "player_nickname": "Common short name; NULL when the player has none.",
    "jersey_number": "Shirt number worn in this match.",
    "country_name": "Country the player represents.",
    "position_name": (
        "Tactical position the player started in, or came on at for a "
        "substitute. NULL for an unused substitute. Later in-match position "
        "changes are not recorded here."
    ),
    "on_the_pitch_from_timestamp": (
        "Clock 'MM:SS' when the player came onto the pitch - '00:00' for a "
        "starter, NULL for an unused substitute."
    ),
    "on_the_pitch_to_timestamp": (
        "Clock 'MM:SS' when the player left the pitch - NULL if still on at the "
        "final whistle or an unused substitute."
    ),
    "on_the_pitch_from_period": (
        "Period the player came on in (1 = first half). NULL for an unused substitute."
    ),
    "on_the_pitch_to_period": (
        "Period the player left in. NULL if still on at the final whistle or an "
        "unused substitute."
    ),
    "first_yellow_card_timestamp": "Clock 'MM:SS' of the player's first yellow card; NULL if none.",
    "first_yellow_card_period": "Period of the first yellow card; NULL if none.",
    "first_yellow_card_reason": "Reason for the first yellow card (e.g. Foul Committed); NULL if none.",
    "second_yellow_card_timestamp": (
        "Clock 'MM:SS' of the second yellow card - a sending-off offence; NULL if none."
    ),
    "second_yellow_card_period": "Period of the second yellow card; NULL if none.",
    "second_yellow_card_reason": "Reason for the second yellow card; NULL if none.",
    "red_card_timestamp": "Clock 'MM:SS' of a straight red card; NULL if none.",
    "red_card_period": "Period of the straight red card; NULL if none.",
    "red_card_reason": "Reason for the straight red card; NULL if none.",
}


def fetch_competitions() -> pd.DataFrame:
    all_comps = sb.competitions(fmt="json")
    rows = [
        {
            "competition_id": c["competition_id"],
            "season_id": c["season_id"],
            "competition_name": c["competition_name"],
            "season_name": c["season_name"],
            "competition_gender": c["competition_gender"],
        }
        for c in all_comps.values()
        if c["competition_name"] in COMPETITION_NAMES
        and c["season_name"] in SEASON_NAMES
    ]
    return pd.DataFrame(
        rows,
        columns=[
            "competition_id",
            "season_id",
            "competition_name",
            "season_name",
            "competition_gender",
        ],
    )


def fetch_matches(competitions: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for comp in competitions.itertuples():
        matches = sb.matches(
            competition_id=comp.competition_id,
            season_id=comp.season_id,
            fmt="json",
        )
        for match_id, m in matches.items():
            rows.append(
                {
                    "match_id": int(match_id),
                    "competition_id": comp.competition_id,
                    "season_id": comp.season_id,
                    "match_date": m["match_date"],
                    "home_team_id": m["home_team"]["home_team_id"],
                    "home_team_name": m["home_team"]["home_team_name"],
                    "away_team_id": m["away_team"]["away_team_id"],
                    "away_team_name": m["away_team"]["away_team_name"],
                    "home_score": m["home_score"],
                    "away_score": m["away_score"],
                }
            )
        print(f"  {comp.competition_name} {comp.season_name}: {len(matches)} matches")
    return pd.DataFrame(
        rows,
        columns=[
            "match_id",
            "competition_id",
            "season_id",
            "match_date",
            "home_team_id",
            "home_team_name",
            "away_team_id",
            "away_team_name",
            "home_score",
            "away_score",
        ],
    )


def fetch_lineups(matches: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _match in tqdm(
        matches.itertuples(), total=len(matches), desc="Lineups", unit="match"
    ):
        try:
            lineups = sb.lineups(match_id=_match.match_id, fmt="json")
        except Exception as exc:  # skip a bad match, keep going
            tqdm.write(f"  ! skipped lineup for match {_match.match_id}: {exc}")
            continue
        for team in lineups.values():
            for player in team["lineup"]:
                positions = player.get("positions") or []
                first_pos = positions[0] if positions else None
                last_pos = positions[-1] if positions else None

                cards = player.get("cards") or []
                first_yellow = next(
                    (c for c in cards if c.get("card_type") == "Yellow Card"), None
                )
                second_yellow = next(
                    (c for c in cards if c.get("card_type") == "Second Yellow"), None
                )
                red = next((c for c in cards if c.get("card_type") == "Red Card"), None)

                country = player.get("country") or {}
                rows.append(
                    {
                        "match_id": int(_match.match_id),
                        "team_id": team["team_id"],
                        "team_name": team["team_name"],
                        "player_id": player["player_id"],
                        "player_name": player["player_name"],
                        "player_nickname": player.get("player_nickname"),
                        "jersey_number": player.get("jersey_number"),
                        "country_name": country.get("name"),
                        "position_name": first_pos["position"] if first_pos else None,
                        "on_the_pitch_from_timestamp": (
                            first_pos["from"] if first_pos else None
                        ),
                        "on_the_pitch_to_timestamp": (
                            last_pos["to"] if last_pos else None
                        ),
                        "on_the_pitch_from_period": (
                            first_pos["from_period"] if first_pos else None
                        ),
                        "on_the_pitch_to_period": (
                            last_pos["to_period"] if last_pos else None
                        ),
                        "first_yellow_card_timestamp": (
                            first_yellow["time"] if first_yellow else None
                        ),
                        "first_yellow_card_period": (
                            first_yellow["period"] if first_yellow else None
                        ),
                        "first_yellow_card_reason": (
                            first_yellow.get("reason") if first_yellow else None
                        ),
                        "second_yellow_card_timestamp": (
                            second_yellow["time"] if second_yellow else None
                        ),
                        "second_yellow_card_period": (
                            second_yellow["period"] if second_yellow else None
                        ),
                        "second_yellow_card_reason": (
                            second_yellow.get("reason") if second_yellow else None
                        ),
                        "red_card_timestamp": red["time"] if red else None,
                        "red_card_period": red["period"] if red else None,
                        "red_card_reason": red.get("reason") if red else None,
                    }
                )

    df = pd.DataFrame(rows, columns=LINEUP_COLUMNS)
    for column in LINEUP_INT_COLUMNS:
        df[column] = df[column].astype("Int64")
    return df


def _shape_events(df: pd.DataFrame) -> pd.DataFrame:
    for source, prefix in LOCATION_SPLITS.items():
        if source not in df.columns:
            continue
        df[f"{prefix}_x"] = df[source].str[0]
        df[f"{prefix}_y"] = df[source].str[1]
        if prefix == "shot_end":
            df[f"{prefix}_z"] = df[source].str[2]

    df = df.drop(columns=EVENT_DROP_COLUMNS + list(LOCATION_SPLITS), errors="ignore")

    # StatsBomb emits booleans as TRUE-or-absent, so pandas reads them as
    # object columns of {True, NaN}. Coerce to a real nullable boolean.
    for column in df.columns:
        values = df[column].dropna().unique()
        if len(values) and all(isinstance(v, bool) for v in values):
            df[column] = df[column].astype("boolean")

    return df


def fetch_events(matches: pd.DataFrame) -> pd.DataFrame:
    frames = []
    for _i, _match in enumerate(
        tqdm(matches.itertuples(), total=len(matches), desc="Events", unit="match")
    ):
        try:
            events = sb.events(match_id=_match.match_id)
        except Exception as exc:  # skip a bad match, keep going
            tqdm.write(f"  ! skipped match {_match.match_id}: {exc}")
            continue
        events["match_id"] = _match.match_id
        frames.append(events)
    return _shape_events(pd.concat(frames, ignore_index=True))


def _sql_literal(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


def _apply_event_comments(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(f"COMMENT ON TABLE events IS {_sql_literal(EVENTS_TABLE_COMMENT)}")
    existing = {
        row[0]
        for row in con.execute(
            "SELECT column_name FROM duckdb_columns() WHERE table_name = 'events'"
        ).fetchall()
    }
    for column, text in EVENT_COLUMN_COMMENTS.items():
        if column in existing:
            con.execute(f'COMMENT ON COLUMN events."{column}" IS {_sql_literal(text)}')


def _apply_lineup_comments(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(f"COMMENT ON TABLE lineups IS {_sql_literal(LINEUPS_TABLE_COMMENT)}")
    for column, text in LINEUP_COLUMN_COMMENTS.items():
        con.execute(f'COMMENT ON COLUMN lineups."{column}" IS {_sql_literal(text)}')


def main() -> None:
    print("Fetching competitions...")
    competitions_df = fetch_competitions()
    print(f"  {len(competitions_df)} competition-seasons matched the filter")

    print("Fetching matches...")
    matches_df = fetch_matches(competitions_df)
    print(f"  {len(matches_df)} matches total")

    print("Fetching lineups...")
    lineups_df = fetch_lineups(matches_df)
    print(f"  {len(lineups_df)} lineup rows total")

    print("Fetching events (slow - one API call per match)...")
    events_df = fetch_events(matches_df)
    print(f"  {len(events_df)} events total")

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB_PATH))
    try:
        con.register("competitions_df", competitions_df)
        con.register("matches_df", matches_df)

        con.execute("DROP TABLE IF EXISTS lineups")
        con.execute("DROP TABLE IF EXISTS matches")
        con.execute("DROP TABLE IF EXISTS competitions")

        con.execute(
            """
            CREATE TABLE competitions (
                competition_id     INTEGER,
                season_id          INTEGER,
                competition_name   VARCHAR,
                season_name        VARCHAR,
                competition_gender VARCHAR,
                PRIMARY KEY (competition_id, season_id)
            )
            """
        )
        con.execute("INSERT INTO competitions SELECT * FROM competitions_df")

        con.execute(
            """
            CREATE TABLE matches (
                match_id        INTEGER PRIMARY KEY,
                competition_id  INTEGER,
                season_id       INTEGER,
                match_date      DATE,
                home_team_id    INTEGER,
                home_team_name  VARCHAR,
                away_team_id    INTEGER,
                away_team_name  VARCHAR,
                home_score      INTEGER,
                away_score      INTEGER
            )
            """
        )
        con.execute("INSERT INTO matches SELECT * FROM matches_df")

        con.register("lineups_df", lineups_df)
        con.execute(
            """
            CREATE TABLE lineups (
                match_id                     INTEGER,
                team_id                      INTEGER,
                team_name                    VARCHAR,
                player_id                    INTEGER,
                player_name                  VARCHAR,
                player_nickname              VARCHAR,
                jersey_number                INTEGER,
                country_name                 VARCHAR,
                position_name                VARCHAR,
                on_the_pitch_from_timestamp  VARCHAR,
                on_the_pitch_to_timestamp    VARCHAR,
                on_the_pitch_from_period     INTEGER,
                on_the_pitch_to_period       INTEGER,
                first_yellow_card_timestamp  VARCHAR,
                first_yellow_card_period     INTEGER,
                first_yellow_card_reason     VARCHAR,
                second_yellow_card_timestamp VARCHAR,
                second_yellow_card_period    INTEGER,
                second_yellow_card_reason    VARCHAR,
                red_card_timestamp           VARCHAR,
                red_card_period              INTEGER,
                red_card_reason              VARCHAR,
                PRIMARY KEY (match_id, player_id)
            )
            """
        )
        con.execute("INSERT INTO lineups SELECT * FROM lineups_df")
        _apply_lineup_comments(con)

        con.register("events_df", events_df)
        con.execute("DROP TABLE IF EXISTS events")
        con.execute("CREATE TABLE events AS SELECT * FROM events_df")
        _apply_event_comments(con)
    finally:
        con.close()

    print(f"Done. Wrote {DB_PATH}")


if __name__ == "__main__":
    main()
