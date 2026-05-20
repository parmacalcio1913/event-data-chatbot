from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.prompts import base
from pydantic import Field

from core.statsbomb import StatsBomb

sb = StatsBomb()
mcp = FastMCP("FootballEventsMCP", log_level="ERROR")


# The events table is wide (~80 columns). Its schema is read from the database
# once, here at import time, and baked into the query tool's description below.
# That keeps it in the (cacheable) tool definition instead of forcing the model
# to dump a catalog query into the conversation on every events question.
QUERY_DESCRIPTION = (
    "Run a read-only SQL query against the local StatsBomb DuckDB database and "
    "return the resulting rows. For data queries, prefer aggregates (COUNT, "
    "SUM, AVG, GROUP BY) over selecting raw rows whenever the question allows "
    "it. Always list the specific columns you need in the SELECT clause; never "
    "write SELECT * — it pulls every column of every matched row into context "
    "and is the biggest avoidable source of wasted tokens.\n"
    "\n"
    "Tables:\n"
    "  competitions(competition_id INTEGER, season_id INTEGER, "
    "competition_name VARCHAR, season_name VARCHAR, competition_gender VARCHAR)\n"
    "  matches(match_id INTEGER, competition_id INTEGER, season_id INTEGER, "
    "match_date DATE, home_team_id INTEGER, home_team_name VARCHAR, "
    "away_team_id INTEGER, away_team_name VARCHAR, home_score INTEGER, "
    "away_score INTEGER)\n"
    "  lineups(match_id INTEGER, team_id INTEGER, team_name VARCHAR, "
    "player_id INTEGER, player_name VARCHAR, player_nickname VARCHAR, "
    "jersey_number INTEGER, country_name VARCHAR, position_name VARCHAR, "
    "on_the_pitch_from_timestamp VARCHAR, on_the_pitch_to_timestamp VARCHAR, "
    "on_the_pitch_from_period INTEGER, on_the_pitch_to_period INTEGER, "
    "first_yellow_card_timestamp VARCHAR, first_yellow_card_period INTEGER, "
    "first_yellow_card_reason VARCHAR, second_yellow_card_timestamp VARCHAR, "
    "second_yellow_card_period INTEGER, second_yellow_card_reason VARCHAR, "
    "red_card_timestamp VARCHAR, red_card_period INTEGER, "
    "red_card_reason VARCHAR) — one row per player per match (starters, "
    "used and unused substitutes); use it for starting XIs, substitutions "
    "and cards. Clock columns are 'MM:SS' strings within the period. A "
    "starter has on_the_pitch_from_timestamp = '00:00' and "
    "on_the_pitch_from_period = 1; a used substitute came on later; an "
    "unused substitute has every on_the_pitch_* column NULL. "
    "on_the_pitch_to_* is NULL for a player still on at the final whistle. "
    "  events — one row per match event; a wide table. Its full schema is "
    "given below, so you never need to inspect the table at runtime. Column "
    "names are bare (player, team, type — NOT player_name); use exactly the "
    "names listed and select only the ones the question needs.\n"
    "\n"
    "events table schema:\n"
    f"{sb.events_schema()}\n"
    "\n"
    "When using team names and/or player names in WHERE conditions, don't use the Equal To operator but use the LIKE operator."
    "There is no teams table — derive teams from matches.home_team_name / "
    "matches.away_team_name. Only SELECT statements are allowed. Results are "
    "capped; the response includes a 'truncated' flag when the cap is hit."
    "When you are asked to return a game or a list of games (e.g., 'What's the last game this team played at home',"
    "or 'What games did this team played during Winter?'), always include the match IDs."
)


@mcp.tool(name="query", description=QUERY_DESCRIPTION)
def query(sql: str = Field(description="A single read-only SQL SELECT statement.")):
    return sb.query(sql)


@mcp.prompt(
    name="summary",
    description="Write a match summary for a given match ID.",
)
def write_match_summary(
    match_id: str = Field(description="ID of the match to sumarize."),
) -> list[base.Message]:
    prompt = f"""
    You need to summarize match ID = {match_id}. You will have to query both the events table and the lineups table.

    The report should follow the following rules:

    <rules>
    1. Begin with a strong introduction that includes the match's score, scorers, winner, date, and any sending-offs (double yellow cards or red cards only).
    For example, “Joel Veltman scored two goals Saturday to lead Brighton to a 2-0 win over Toronto FC.”
    2. Present the lineups, including team names, starters and substitutions.
        1a. Write the team name in caps lock, and the team formation between brackets.
        1b. Present the lineups line by line, moving up the pitch and from right to left.
        1c. The lines are always at least 5: GK; DEF; MID; FWD;
            For formations like 4312/4231/3412/3421/4321 etc, add a CAM line between MID and FWD.
        1d. Substitutions should be presented in the lineusp as follows: Pjanic (77' Torosidis).
        1e. Players who did not come on can be omitted.
    3. Move on to the key events of the match: goals, substitutions and red cards.
        3a. Outline chronologically while keeping descriptions concise.
        3b. Be specific and avoid rambling.
        3c. Write in short paragraphs.
        3d. Describe goals, but also missed chances (xG >= 0.2).
        3e. Do not mention explicitely xG.
        3f. Mention substitutions, and specify if they are because of an "Injury". Otherwise it's assumed it's a Tactical change, no need to specify it.
        3g. Describe cards and the reason.
    </rules>

    You are only allowed to run the following queries. You cannot run any other queries. Everything you need is in these queries.
    <queries>
    <matches-query>
    SELECT match_id, match_date, home_team_name, away_team_name, home_score, away_score
    FROM matches WHERE match_id={match_id}
    <matches-query>

    The lineups table should be queried as follows:
    <lineups-query>
    SELECT team_name,COALESCE(player_nickname,player_name) player,position_name,
    on_the_pitch_from_timestamp,on_the_pitch_to_timestamp,
    on_the_pitch_from_period,on_the_pitch_to_period,
    first_yellow_card_timestamp,first_yellow_card_period,first_yellow_card_reason,
    second_yellow_card_timestamp,second_yellow_card_period,second_yellow_card_reason,
    red_card_timestamp,red_card_period,red_card_reason
    FROM lineups
    WHERE match_id={match_id} AND on_the_pitch_from_timestamp IS NOT NULL;
    </lineups-query>
    This table will give you all the information you need to write the lineups.
    For the match report, you need to get the substitution reason and the goals from the events table.

    The events table should be queried as follows:
    <events-query>
    SELECT period,minute,team,player,substitution_outcome,substitution_replacement,
    play_pattern,shot_body_part,shot_outcome,shot_statsbomb_xg,shot_type
    FROM events
    WHERE match_id={match_id}
    AND (type='Substitution' OR type='Shot' AND (shot_outcome='Goal' OR shot_statsbomb_xg>=0.2));
    </events-query>
    </queries>
    """

    return [base.UserMessage(prompt)]


if __name__ == "__main__":
    mcp.run(transport="stdio")
