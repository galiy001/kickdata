import os
import requests
import streamlit as st

from unidecode import unidecode
from Levenshtein import distance
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv('API_KEY')

# Static League ID list of the top ten leagues extracted from API documents.
LEAGUE_IDS = {
    'Premier League': 39,
    'Bundesliga': 78,
    'La Liga (Spain)': 140,
    'Serie A': 135,
    'Ligue 1': 61,
    'Eredivisie': 88,
    'Serie A (Brazil)': 71,
    'Primeira Liga': 94,
    'Liga MX': 262,
    'Premier League (Russia)': 235,
}


def get_player_stats_from_api(player_name, season, league_id):
    url = "https://api-football-v1.p.rapidapi.com/v3/players"

    headers = {
        "X-RapidAPI-Key": API_KEY,
        "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
    }

    # Handle odd characters in player names by using the uni-decode package. Translate the string into
    # ASCII-code to differentiate and help find the player's exact name.
    search_name = unidecode(player_name)

    while len(search_name) > 0:
        querystring = {"season": season, "search": search_name, "league": str(league_id)}

        response = requests.get(url, headers=headers, params=querystring)
        response_data = response.json()

        if response_data.get('response'):
            # Use the 'Levenshtein' package to import distance, which will help us identify the closest match to a
            # player's name based on how close the user's input is. We had a TON of trouble finding names like 'Ronaldo',
            # 'Ben White', and another example, 'Rico Lewis'. Those problems were solved with this logic.
            players_data = response_data['response']
            best_match = min(players_data,
                             key=lambda player: distance(search_name, unidecode(player['player']['name'])))
            return best_match

        # If no matching player is found, recursively remove a character and try again.
        search_name = search_name[1:]

    return None


def get_club_stats_from_api(club_id, season, league_id):
    url = "https://api-football-v1.p.rapidapi.com/v3/teams/statistics"

    headers = {
        "X-RapidAPI-Key": API_KEY,
        "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
    }

    querystring = {"team": club_id, "season": season, "league": str(league_id)}

    response = requests.get(url, headers=headers, params=querystring)
    response_data = response.json()

    if response_data.get('response'):
        return response_data['response']

    return None


def get_players_from_api(club_id, season, league_id, page=1):
    url = "https://api-football-v1.p.rapidapi.com/v3/players"

    headers = {
        "X-RapidAPI-Key": API_KEY,
        "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
    }

    querystring = {"season": season, "team": club_id, "league": str(league_id), "page": str(page)}

    response = requests.get(url, headers=headers, params=querystring)
    response_data = response.json()

    if response_data.get('response'):
        players = response_data['response']

        if response_data.get('paging', {}).get('current') < response_data.get('paging', {}).get('total'):
            players.extend(get_players_from_api(club_id, season, league_id, page + 1))

        return players

    return None


# Retrieve a club's ID based on the club's name and country.
def get_club_id(club_name, club_country):
    url = "https://api-football-v1.p.rapidapi.com/v3/teams"

    headers = {
        "X-RapidAPI-Key": API_KEY,
        "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
    }

    querystring = {"name": club_name, "country": club_country}

    response = requests.get(url, headers=headers, params=querystring)

    if response.status_code == 200:
        response_json = response.json()

        # Narrow down the search using a country and assume that the first returned
        # club is the correct one. Not the best solution, but to my knowledge, there
        # aren't any clubs with the same exact name within a country, so this should work.
        if response_json['results'] > 0:
            return response_json['response'][0]['team']['id']
    return None


# Just a quick API call to get the club logo using the club_name and club_country.
def get_club_logo(club_name, club_country):
    url = "https://api-football-v1.p.rapidapi.com/v3/teams"
    querystring = {"name": club_name, "country": club_country}

    headers = {
        "X-RapidAPI-Key": API_KEY,
        "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
    }

    response = requests.get(url, headers=headers, params=querystring)

    if response.status_code == 200:
        response_json = response.json()

        if response_json['results'] > 0:
            return response_json['response'][0]['team']['logo']
    return None


# Probably the most important function in this app, retrieve the player's stats based on the player's
# full name, the season, and the league which they play in.
def get_player_stats(player_full_name, season, league_name):
    league_id = LEAGUE_IDS.get(league_name)
    if not league_id:
        return f"Invalid league name: {league_name}. Please choose from: {', '.join(LEAGUE_IDS.keys())}"

    # Split the player name to make it easier to find if the user enters multiple names separated by a space.
    # Obviously this won't work if a user enters a name without any spaces.
    names = player_full_name.split(" ")

    # If the user enters one name, don't split anything. Otherwise, split the names.
    if len(names) == 1:
        first_name = ''
        last_name = names[0]
    elif len(names) >= 2:
        first_name = " ".join(names[:-1])
        last_name = names[-1]

    # Join the first_name and last_name together, along with season year and league_id, and grab player data.
    player_data = get_player_stats_from_api(first_name + " " + last_name, season, league_id)

    # If we can't find any data, try again with just the last_name.
    if player_data is None:
        player_data = get_player_stats_from_api(last_name, season, league_id)

    # If we STILL can't find any data, return a message that says we can't find stats for that player.
    if player_data is None:
        return f"No stats found for {player_full_name} in the {season} season."

    # Store the player data and the statistic data in separate variables.
    player = player_data['player']
    stats = player_data['statistics'][0]

    # Use the 'stats' variable to return every data value we want to compare and assign to an individual variable.
    # We could've just passed in these values to 'Stats:' but I think this is a cleaner solution. We did do that for
    # the player's name, photo, nationality, club, and club logo, however.
    total_goals = stats['goals']['total']
    total_assists = stats['goals']['assists'] if stats['goals']['assists'] is not None else 0
    total_shots = stats['shots']['total']
    shots_on_target = stats['shots']['on']
    dribbles_attempts = stats['dribbles']['attempts']
    dribbles_success = stats['dribbles']['success']
    key_passes = stats['passes']['key']
    pass_accuracy = stats['passes'].get('accuracy', None)
    duels_won = stats['duels'].get('won', None)
    tackles_total = stats['tackles'].get('total', None)
    tackles_interceptions = stats['tackles']['interceptions']
    tackles_blocks = stats['tackles']['blocks']
    fouls_drawn = stats['fouls']['drawn']
    fouls_committed = stats['fouls']['committed']

    return {
        "Player": {
            "Name": player['name'],
            "Photo": player['photo'],
            "Team Logo": stats['team']['logo'],
            "Nationality": player['nationality'],
            "Team": stats['team']['id']
        },
        "Stats": {
            "Goals": total_goals,
            "Assists": total_assists,
            "Total Shots": total_shots,
            "Shots on Target": shots_on_target,
            "Dribble Attempts": dribbles_attempts,
            "Dribble Successes": dribbles_success,
            "Key Passes": key_passes,
            "Pass Success Rate": pass_accuracy if pass_accuracy is not None else 0,
            "Duels Won": duels_won if duels_won is not None else 0,
            "Total Tackles": tackles_total if tackles_total is not None else 0,
            "Interceptions": tackles_interceptions if tackles_interceptions is not None else 0,
            "Blocks": tackles_blocks if tackles_blocks is not None else 0,
            "Fouls Drawn": fouls_drawn if fouls_drawn is not None else 0,
            "Fouls Committed": fouls_committed if fouls_committed is not None else 0,
        }
    }


# Similar to the get_player_stats, however this function is to retrieve club stats!
def get_team_stats(club_name, club_country, season, league_name):
    league_id = LEAGUE_IDS.get(league_name)
    if not league_id:
        return f"Invalid league name: {league_name}. Please choose from: {', '.join(LEAGUE_IDS.keys())}"

    club_id = get_club_id(club_name, club_country)

    if club_id is None:
        return f"No club found for {club_name} in {club_country}."

    # Grab club data from the get_club_stats_from_api function above.
    club_data = get_club_stats_from_api(club_id, season, league_id)

    if 'team' not in club_data:
        return "Unexpected API response format."

    if club_data is None:
        return f"No stats found for {club_name} in the {season} season."

    # Store the player data and the statistic data in separate variables.
    club = club_data['team']
    stats = club_data

    # Use the 'club_stats' variable to return every data value we want to grab and assign to an individual variable.
    total_played = stats['fixtures']['played']['total']
    total_wins_home = stats['fixtures']['wins']['home']
    total_wins_away = stats['fixtures']['wins']['away']
    total_wins = stats['fixtures']['wins']['total']
    total_draws_home = stats['fixtures']['draws']['home']
    total_draws_away = stats['fixtures']['draws']['away']
    total_draws = stats['fixtures']['draws']['total']
    total_loses_home = stats['fixtures']['loses']['home']
    total_loses_away = stats['fixtures']['loses']['away']
    total_loses = stats['fixtures']['loses']['total']
    club_form = stats['form']

    total_goals_scored_home = stats['goals']['for']['total']['home']
    total_goals_scored_away = stats['goals']['for']['total']['away']
    total_goals_scored = stats['goals']['for']['total']['total']
    goals_scored_average_home = stats['goals']['for']['average']['home']
    goals_scored_average_away = stats['goals']['for']['average']['away']
    goals_scored_average_total = stats['goals']['for']['average']['total']

    total_goals_conceded_home = stats['goals']['against']['total']['home']
    total_goals_conceded_away = stats['goals']['against']['total']['away']
    total_goals_conceded = stats['goals']['against']['total']['total']
    goals_conceded_average_home = stats['goals']['against']['average']['home']
    goals_conceded_average_away = stats['goals']['against']['average']['away']
    goals_conceded_average_total = stats['goals']['against']['average']['total']

    longest_win_streak = stats['biggest']['streak']['wins']
    longest_draw_streak = stats['biggest']['streak']['draws']
    longest_lose_streak = stats['biggest']['streak']['loses']

    biggest_win_home = stats['biggest']['wins']['home']
    biggest_win_away = stats['biggest']['wins']['away']
    biggest_lose_home = stats['biggest']['loses']['home']
    biggest_lose_away = stats['biggest']['loses']['away']

    total_clean_sheets_home = stats['clean_sheet']['home']
    total_clean_sheets_away = stats['clean_sheet']['away']
    total_clean_sheets = stats['clean_sheet']['total']

    failed_to_score_home = stats['failed_to_score']['home']
    failed_to_score_away = stats['failed_to_score']['away']
    failed_to_score_total = stats['failed_to_score']['total']

    lineup_info = {}

    for i in range(len(stats['lineups'])):
        formation_deployed = stats['lineups'][i]['formation']
        times_deployed = stats['lineups'][i]['played']
        lineup_info[formation_deployed] = times_deployed

    return {
        "Club": {
            "Name": club['name'],
            "Logo": club['logo']
        },
        "Stats": {
            "Total Games": total_played,
            "Total Wins Home": total_wins_home,
            "Total Wins Away": total_wins_away,
            "Total Wins": total_wins,
            "Total Draws Home": total_draws_home,
            "Total Draws Away": total_draws_away,
            "Total Draws": total_draws,
            "Total Losses Home": total_loses_home,
            "Total Losses Away": total_loses_away,
            "Total Losses": total_loses,
            "Club Form": club_form,
            "Total Home Goals Scored": total_goals_scored_home,
            "Total Away Goals Scored": total_goals_scored_away,
            "Total Goals Scored": total_goals_scored,
            "Average Home Goals Scored": goals_scored_average_home,
            "Average Away Goals Scored": goals_scored_average_away,
            "Average Goals Scored": goals_scored_average_total,
            "Total Home Goals Conceded": total_goals_conceded_home,
            "Total Away Goals Conceded": total_goals_conceded_away,
            "Total Goals Conceded": total_goals_conceded,
            "Average Home Goals Conceded": goals_conceded_average_home,
            "Average Away Goals Conceded": goals_conceded_average_away,
            "Average Goals Conceded": goals_conceded_average_total,
            "Longest Win Streak": longest_win_streak,
            "Longest Draw Streak": longest_draw_streak,
            "Longest Lose Streak": longest_lose_streak,
            "Biggest Home Win": biggest_win_home,
            "Biggest Away Win": biggest_win_away,
            "Biggest Home Loss": biggest_lose_home,
            "Biggest Away Loss": biggest_lose_away,
            "Total Home Clean Sheets": total_clean_sheets_home,
            "Total Away Clean Sheets": total_clean_sheets_away,
            "Total Clean Sheets": total_clean_sheets,
            "Times Failed to Score at Home": failed_to_score_home,
            "Times Failed to Score Away": failed_to_score_away,
            "Total Times Failed to Score": failed_to_score_total,
            "Lineups": lineup_info,
        }
    }


def get_league_performance(league_name, season):
    league_id = LEAGUE_IDS.get(league_name)
    if not league_id:
        return f"Invalid league name: {league_name}. Please choose from: {', '.join(LEAGUE_IDS.keys())}"

    url = "https://api-football-v1.p.rapidapi.com/v3/teams"
    headers = {
        "X-RapidAPI-Key": API_KEY,
        "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
    }
    querystring = {"league": str(league_id), "season": season}
    response = requests.get(url, headers=headers, params=querystring)
    response_data = response.json()
    if response_data.get('response'):
        team_stats = []
        for team in response_data['response']:
            team_id = team['team']['id']
            team_name = team['team']['name']
            team_country = team['team']['country']
            team_stat = get_team_stats(team_name, team_country, season, league_name)
            if isinstance(team_stat, dict):
                team_stat['team_id'] = team_id
                team_stat['team_name'] = team_name
                team_stats.append(team_stat)

        return team_stats
    else:
        return f"No teams found for {league_name} in the {season} season."