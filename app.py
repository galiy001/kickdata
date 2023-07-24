import pandas as pd
import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import requests
import folium
import random
import seaborn as sns

from PIL import Image, ImageOps
from io import BytesIO
from geopy.geocoders import Nominatim
from streamlit_folium import folium_static
from utils import get_player_stats, get_players_from_api, get_club_id, LEAGUE_IDS, get_club_logo, get_team_stats


# Radar chart function -- this will allow us to visually compare players to one another. Notice that each
# radar chart draws a different amount of players. I did this because I was finding difficulties with the amount
# of arguments being passed to a single radar chart function based on the user's desired number of players to compare.
def draw_three_player_radar_chart(labels, stats1, stats2, stats3, title1, title2, title3, color1, color2, color3):
    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()

    # Applying log scaling for each player's statistics -- easier to read and less extremities in the data.
    # I tried min-max normalized scaling but ran into the same issues -- massive differences between stats with
    # large numbers and small numbers. For example, duels won vs. goals scored. Duels won could be in the hundreds,
    # goals scored in the tens. Using normalization would still cause duels won to trump every other stat visually.
    stats1 = list(np.log1p(np.float64(stats1)))
    stats1.append(stats1[0])

    # Same process as above, this is for player 2's stats!
    stats2 = list(np.log1p(np.float64(stats2)))
    stats2.append(stats2[0])

    # Same thing, but for player 3.
    stats3 = list(np.log1p(np.float64(stats3)))
    stats3.append(stats3[0])

    angles.append(angles[0])
    labels.append(labels[0])

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw={'polar': True})

    # Three players drawn.
    ax.plot(angles, stats1, 'o-', linewidth=2, label=title1, color=color1)
    ax.fill(angles, stats1, color1, alpha=0.25)
    ax.plot(angles, stats2, 'o-', linewidth=2, label=title2, color=color2)
    ax.fill(angles, stats2, color2, alpha=0.25)
    ax.plot(angles, stats3, 'o-', linewidth=2, label=title3, color=color3)
    ax.fill(angles, stats3, color3, alpha=0.25)

    ax.set_thetagrids(np.degrees(angles), labels)
    ax.set_title('Player Comparison (Logarithmic Scaling)')
    ax.grid(True)
    plt.legend(loc='upper right', bbox_to_anchor=(0.1, 0.1))

    return fig


# Draw a two player radar chart.
def draw_two_player_radar_chart(labels, stats1, stats2, title1, title2, color1, color2):
    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()

    # Applying log scaling for each player's statistics -- easier to read and less extremities in the data.
    stats1 = list(np.log1p(np.float64(stats1)))
    stats1.append(stats1[0])

    # Same process as above, this is for player 2's stats!
    stats2 = list(np.log1p(np.float64(stats2)))
    stats2.append(stats2[0])

    angles.append(angles[0])
    labels.append(labels[0])

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw={'polar': True})

    # Two players drawn.
    ax.plot(angles, stats1, 'o-', linewidth=2, label=title1, color=color1)
    ax.fill(angles, stats1, color1, alpha=0.25)
    ax.plot(angles, stats2, 'o-', linewidth=2, label=title2, color=color2)
    ax.fill(angles, stats2, color2, alpha=0.25)

    ax.set_thetagrids(np.degrees(angles), labels)
    ax.set_title('Player Comparison (Logarithmic Scaling)')
    ax.grid(True)
    plt.legend(loc='upper right', bbox_to_anchor=(0.1, 0.1))

    return fig


# Draw a single player radar chart.
def draw_single_player_radar_chart(labels, stats, title, color):
    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()

    # Applying log scaling for player's statistics -- easier to read and less extremities in the data.
    stats = list(np.log1p(np.float64(stats)))
    stats.append(stats[0])

    angles.append(angles[0])
    labels.append(labels[0])

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw={'polar': True})

    # One player drawn.
    ax.plot(angles, stats, 'o-', linewidth=2, label=title, color=color)
    ax.fill(angles, stats, color, alpha=0.25)

    ax.set_thetagrids(np.degrees(angles), labels)
    ax.set_title('Player Performance (Logarithmic Scaling)')
    ax.grid(True)
    plt.legend(loc='upper right', bbox_to_anchor=(0.1, 0.1))

    return fig


# This jitter function is used to offset each player's location in the 'Player Map' feature.
# Without this, players from the same country are ALL in the same exact place. We could take a
# more specific route by using the city in the player's API response data, but this seemed like
# an easier approach.
def add_jitter(lat, lon, amount=1):
    return lat + amount * (random.random() - 0.5), lon + amount * (random.random() - 0.5)


# Quick function to add borders to player photos, wanted to beautify them a bit.
def add_border(input_image, border, color=(100, 100, 100)):
    img = Image.open(BytesIO(requests.get(input_image).content))
    if isinstance(border, int) or isinstance(border, tuple):
        bimg = ImageOps.expand(img, border=border, fill=color)
    else:
        raise RuntimeError('Border is not an integer or tuple!')
    return bimg


# Using the Nominatim package to grab latitude and longitude values for our map function,
# based on the player's country of birth. We grab this data from the API and pass it in to
# this function.
def get_coordinates(country):
    geolocator = Nominatim(user_agent="myGeocoder")
    try:
        location = geolocator.geocode(country)
        if location is not None:
            return location.latitude, location.longitude
        else:
            return None
    except Exception as e:
        print(f"An error occurred while getting coordinates for {country}: {e}")
        return None


# Calculation of team performance.
def calculate_performance(stats_dict, season):
    total_wins = stats_dict.get('Total Wins', 0)
    total_losses = stats_dict.get('Total Losses', 0)
    total_goals_scored = stats_dict.get('Total Goals Scored', 0)
    performance = (total_wins - total_losses + total_goals_scored) / stats_dict.get('Total Games', 1)
    return performance


##############################################################################################
# Starting here, this is where the actual Streamlit app will begin to render. You can read the
# logic starting from line 161 and see how each Streamlit function renders to the webpage.
##############################################################################################


# Load the KickData! logo.
logo = Image.open('./assets/logo.png')

# Set the page config, the tab will read 'KickData!', the icon will be a soccer ball, and the sidebar begins
# in an expanded state. This needs to be the FIRST Streamlit function rendered, otherwise it won't work.
st.set_page_config(
    page_title="KickData!",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Sidebar for website navigation -- looked way better and easier to navigate this way!
st.sidebar.header("KickData! Menu")
option = st.sidebar.selectbox("Choose an option:",
                              ["Welcome to KickData!", "Radar Chart", "Player Search", "Player Map",
                               "Team Statistics"])

# Here's a default landing page with an introduction/guide to the web app!
if option == 'Welcome to KickData!':
    col1, col2, col3 = st.columns(3)
    with col1:
        st.write(' ')
    with col2:
        st.image(logo)
    with col3:
        st.write(' ')
    st.write("""
    KickData! is a comprehensive web application that allows you to retrieve and compare player statistics for the top 
    10 football leagues around the world. Currently, these leagues are:
    - The English 'Premier League'
    - The German 'Bundesliga'
    - The Spanish 'La Liga'
    - The Italian 'Serie A'
    - The French 'Ligue 1'
    - The Dutch 'Eredivisie'
    - The Brazilian 'Serie A'
    - The Portuguese 'Primeira Liga'
    - The Mexican 'Liga MX'
    - The Russian 'Премьер-Лига' (Premier League)
    
    *Each league has complete data available starting from 2016, with partial data available for many clubs as early as 
    2010.*
    """)

    st.markdown("""
        <div style="text-align: center"> 
            <h1> Getting Started </h1>
        </div>
    """, unsafe_allow_html=True)

    st.write("""
    KickData! has been made with simplicity in mind. Located on the left-hand side of the page, a sidebar
    contains all of the features of the website. Simply choose an option to get started! Currently, KickData!
    features:
    - A radar chart feature that can compare up to three players from the top ten leagues across various statistics, 
    season-by-season.
    - A player search feature that will display an individual player's stats in a particular season, with the option
    of a bar chart to make data visualization even easier.
    - A map that pinpoints the nationality of each player for a specific club in a particular year, in addition to the
    entire team roster.
    - A team statistics feature that will display the overall team stats for a specific club in a particular year.
    """)

# The first option -- radar chart comparison. This website feature makes use of the radar chart function above.
elif option == "Radar Chart":

    st.sidebar.divider()

    # Title and info box so the user understands how to use the radar chart feature.
    st.sidebar.header("Radar Chart")
    st.sidebar.info(
        'This feature will display the stats of up to three players across the ten leagues and visualize '
        'them in a radar chart. The second and third player fields are optional -- KickData! will render a radar chart '
        'as long as a single player has been entered.', icon="ℹ️")

    # This variable makes it so that the league selection will default to a blank box.
    league_options = [''] + list(LEAGUE_IDS.keys())

    # Take input from the user in order to call the API retrieval function from utils.py.
    # Furthermore, the only input boxes initially available are the player name boxes --
    # once the user enters a name, the 'Season' and 'Color Selection' options will appear.
    # I think this makes it way easier on the eyes, less confusing for the end user.
    player1 = st.sidebar.text_input("Provide the first player's name:")
    if player1:
        league1 = st.sidebar.selectbox("Select the league for the first player:", options=league_options)

    player2 = st.sidebar.text_input("Optionally, provide the second player's name:")
    if player2:
        league2 = st.sidebar.selectbox("Select the league for the second player:", options=league_options)

    player3 = st.sidebar.text_input("Optionally, provide the third player's name:")
    if player3:
        league3 = st.sidebar.selectbox("Select the league for the third player:", options=league_options)

    st.sidebar.divider()

    season = st.sidebar.text_input("Enter the season year:")

    # List of all possible stats for the 'multi-select' box.
    all_possible_stats = [
        "Goals",
        "Assists",
        "Total Shots",
        "Shots on Target",
        "Dribble Attempts",
        "Dribble Successes",
        "Key Passes",
        "Pass Success Rate",
        "Duels Won",
        "Total Tackles",
        "Interceptions",
        "Blocks",
        "Fouls Drawn",
        "Fouls Committed",
    ]

    # An 'All' option so the user doesn't have to click through each stat to get all of them on the radar chart.
    stats_options = ["All"] + all_possible_stats

    # Here's the actual 'multi-select' box for the user to pick and choose their preferred stats. It defaults to 'All'.
    selected_stats = st.sidebar.multiselect(
        "Select the stats you want to compare:",
        options=stats_options,
        default="All",
    )

    # Here's a color picker so the user can choose the colors they want on the radar chart.
    if player1:
        color1 = st.sidebar.color_picker("Pick a color for the first player:", '#0000FF')
    if player2:
        color2 = st.sidebar.color_picker("Pick a color for the second player:", '#FF0000')
    if player3:
        color3 = st.sidebar.color_picker("Pick a color for the third player:", '#00FF00')

    # If the user selects "All", use all the stats.
    if "All" in selected_stats:
        selected_stats = all_possible_stats

    # Logic once the user clicks the 'Chart!' button.
    if st.sidebar.button('Chart!'):
        # Create 'player_stats' with data we retrieved from the API.
        if player1 and season and league1 or league2 or league3:
            with st.spinner(f'Fetching data on {player1}...'):
                player1_stats = get_player_stats(player1, season, league1)
            if player2:
                with st.spinner(f'Fetching data on {player2}...'):
                    player2_stats = get_player_stats(player2, season, league2)
            else:
                player2_stats = None
            if player3:
                with st.spinner(f'Fetching data on {player3}...'):
                    player3_stats = get_player_stats(player3, season, league3)
            else:
                player3_stats = None

            # Error handling with st.error if we can't find the player.
            if not isinstance(player1_stats, dict) or (player2 and not isinstance(player2_stats, dict)) or (
                    player3 and not isinstance(player3_stats, dict)):
                st.error("One or more players not found. Please check the names and try again.")
            else:
                # Processing the data for the radar chart.
                with st.spinner('Processing data...'):
                    # Pop the player's name from the stats -- we don't need it, it'll cause errors because it isn't an int.
                    player1_name = player1_stats["Player"].pop("Name")
                    player2_name = player2_stats["Player"].pop("Name") if player2_stats else None
                    player3_name = player3_stats["Player"].pop("Name") if player3_stats else None

                    player1_stats = {stat: player1_stats['Stats'].get(stat, 0) for stat in selected_stats}
                    player2_stats = {stat: player2_stats['Stats'].get(stat, 0) for stat in
                                     selected_stats} if player2_stats else None
                    player3_stats = {stat: player3_stats['Stats'].get(stat, 0) for stat in
                                     selected_stats} if player3_stats else None

                    # Create lists for each player's stats -- if player2 and 3 are not chosen, set to none.
                    player1_values = list(player1_stats.values())
                    player2_values = list(player2_stats.values()) if player2_stats else None
                    player3_values = list(player3_stats.values()) if player3_stats else None

                with st.spinner('Generating radar chart...'):
                    # The easiest way to get this working was to create three different methods based on the fields
                    # the user populated. If 1 player, we use draw_single_player_radar_chart, if two we use draw_two_player,
                    # if three, draw_three_player_radar_chart.
                    if player2_values and player3_values:
                        st.markdown("""
                            <div style="text-align: center"> 
                                <h1> Radar Chart </h1>
                                <h3> {} vs. {} vs. {} </h3>
                            </div>
                        """.format(player1_name, player2_name, player3_name), unsafe_allow_html=True)
                        fig = draw_three_player_radar_chart(selected_stats, player1_values, player2_values,
                                                            player3_values,
                                                            player1_name,
                                                            player2_name, player3_name, color1, color2, color3)
                    elif player2_values:
                        st.markdown("""
                            <div style="text-align: center"> 
                                <h1> Radar Chart </h1>
                                <h3> {} vs. {} </h3>
                            </div>
                        """.format(player1_name, player2_name), unsafe_allow_html=True)
                        fig = draw_two_player_radar_chart(selected_stats, player1_values, player2_values, player1_name,
                                                          player2_name,
                                                          color1, color2)

                    else:
                        st.markdown("""
                            <div style="text-align: center"> 
                                <h1> Radar Chart </h1>
                                <h3> {} </h3>
                            </div>
                        """.format(player1_name), unsafe_allow_html=True)
                        fig = draw_single_player_radar_chart(selected_stats, player1_values, player1_name, color1)

                    # Render the radar chart using the st.pyplot method and passing in 'fig' -- the chart we created.
                    st.pyplot(fig)

elif option == "Player Search":

    st.sidebar.divider()

    # Title and info box so the user understands how to use the player search feature.
    st.sidebar.header("Player Search")
    st.sidebar.info(
        'This feature will grab the statistics for a particular player and display them in a table. Optionally, '
        'should a user want to visualize the data, they can use the checkbox to render a bar chart with the '
        'aforementioned data.', icon="ℹ️")

    # Using league_options from above -- I wanted to have a blank space as the first entry.
    league_options = [''] + list(LEAGUE_IDS.keys())

    # Take input from the user in order to call the API retrieval function from utils.py.
    player_name = st.sidebar.text_input("Enter the full name of the player:")
    league = st.sidebar.selectbox("Select the league:", options=league_options)
    show_chart = st.sidebar.checkbox("Render Stats Chart?")

    st.sidebar.divider()

    season = st.sidebar.text_input("Enter the season year:")

    # Once the user clicks 'Search!' begin to execute this logic.
    if st.sidebar.button('Search!'):
        if player_name and season and league:

            with st.spinner('Fetching player stats...'):
                player_stats = get_player_stats(player_name, season, league)

            # Check if player_stats is a dictionary and contains the key "Player"
            if isinstance(player_stats, dict) and "Player" in player_stats:
                player_name = player_stats["Player"].pop("Name")
                player_photo = player_stats["Player"].pop("Photo")
                club_logo = player_stats["Player"].pop("Team Logo")

                # Make a dictionary with the player stats we just grabbed from the API.
                player_stats_dict = player_stats.get("Stats", {})

                # Create the table labels for the player.
                all_labels = list(player_stats_dict.keys())

                # Now, create a list of values for the player.
                player_values = [player_stats_dict.get(label, 0) for label in all_labels]

                # Check if player's stats have same length, fill with zero if not.
                while len(player_values) < len(all_labels):
                    player_values.append(0)

                # This was the best way to handle displaying the player's photo, name, and club.
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.image(add_border(player_photo, border=10), width=100)
                with col3:
                    st.markdown(f'## {player_name} - {int(season)} - {int(season) + int(1)}')
                    style = "<style>h2 {text-align: center;}</style>"
                    st.markdown(style, unsafe_allow_html=True)
                with col2:
                    st.image(club_logo, width=100)
                    style2 = "<style>h2 {align-content: end;}</style>"
                    st.markdown(style2, unsafe_allow_html=True)

                # Display player's stats in a table using Pandas Dataframe.
                st.markdown('### Player Statistics')

                with st.spinner('Generating player statistics table...'):
                    stats_df = pd.DataFrame(data={'Statistic': all_labels, 'Value': player_values})
                    stats_df.index = np.arange(1, len(stats_df) + 1)
                    st.table(stats_df)

                # Visualize player's stats using a bar chart if the checkbox is checked!
                if show_chart:  # Check the value of the checkbox here
                    st.markdown('### Player Statistics Chart')

                    with st.spinner('Generating player statistics chart...'):
                        stats_df = stats_df.set_index('Statistic')
                        st.bar_chart(stats_df)
            else:
                # Error handling with st.error.
                st.error("Player not found or invalid data. Please check the name and try again.")

elif option == "Player Map":

    st.sidebar.divider()

    # Title and info box so the user understands how to use the player map feature.
    st.sidebar.header("Player Map")
    st.sidebar.info(
        'This feature will grab the data for a chosen team based on season year and club country, and map each '
        'player for the year to a world map. In addition, below the map, you will have a full team roster based '
        'on the roster submitted to each league football organization.', icon="ℹ️")

    # Using league_options from above -- I wanted to have a blank space as the first entry.
    league_options = [''] + list(LEAGUE_IDS.keys())

    # Take input from the user in order to call the API retrieval function from utils.py.
    club_name = st.sidebar.text_input("Enter the club name:")
    club_country = st.sidebar.text_input("Enter the country of the club:")
    league = st.sidebar.selectbox("Select the league:", list(LEAGUE_IDS.keys()))

    st.sidebar.divider()

    season = st.sidebar.text_input("Enter the season year:")

    if st.sidebar.button('Map!'):
        if club_name and club_country and season and league:

            club_id = get_club_id(club_name, club_country)

            if club_id is not None:

                with st.spinner('Fetching players...'):
                    players = get_players_from_api(club_id, season, LEAGUE_IDS[league])

                geolocator = Nominatim(user_agent="myGeocoder")
                m = folium.Map(location=[52.5200, 13.4050], zoom_start=3)

                # For each player we pull from the API using the club_id, season, and league, do:
                for player in players:
                    player_data = player['player']
                    location = geolocator.geocode(player_data['nationality'])
                    if location is not None:
                        # 'Jitter' the latitude/longitude so each player isn't on top of each other.
                        jittered_lat, jittered_lon = add_jitter(location.latitude, location.longitude)
                        # User folium's 'Marker' function to add the player's name and location to the map!
                        folium.Marker(
                            [jittered_lat, jittered_lon],
                            popup=player_data['name']
                        ).add_to(m)

                club_logo = get_club_logo(club_name, club_country)

                col1, col2 = st.columns([4, 1])
                with col1:
                    st.header(f"{club_name}'s {int(season)} - {int(season) + int(1)} Player Map")
                with col2:
                    st.image(club_logo, width=80)

                # Display the folium map with player locations and names.
                with st.spinner('Rendering map...'):
                    folium_static(m)

                # Render the roster table below the map.
                st.header(f"{club_name}'s {int(season)} - {int(season) + int(1)} Roster")

                with st.spinner('Generating player roster...'):
                    players_data = [
                        {'Player Name': player['player']['name'], 'Nationality': player['player']['nationality']} for
                        player in players]
                    players_df = pd.DataFrame(players_data)
                    players_df.index = np.arange(1, len(players_df) + 1)
                    st.table(players_df)
            else:
                # Error handling if we can't find the club within a country.
                st.error("No club found with this name and country.")


# Else if the option is Team Statistics, divert to this logic.
elif option == "Team Statistics":

    st.sidebar.divider()

    # Title and info box so the user understands how to use the team statistics feature.
    st.sidebar.header("Team Statistics")
    st.sidebar.info(
        'This feature will grab the statistics for a particular team and give the user an option on what they want to see -- '
        'using the "Season at a Glance" option, they can view a condensed version of stats, an overview of a team\'s season. '
        'Selecting "An In-Depth Look" provides tabular data in addition to visualized data using various charts to illustrate'
        'a team\'s performance during that season.', icon="ℹ️")

    # Using league_options from above -- I wanted to have a blank space as the first entry.
    league_options = [''] + list(LEAGUE_IDS.keys())

    # Take input from the user in order to call the API retrieval function from utils.py.
    club_name = st.sidebar.text_input("Enter the name of the team:")
    club_country = st.sidebar.text_input("Enter the country of the club:")
    league = st.sidebar.selectbox("Select the league:", options=league_options)
    chart_option = st.sidebar.radio("Choose the type of statistical information:",
                                    ('Season at a Glance', 'An In-Depth Look'))

    st.sidebar.divider()

    season = st.sidebar.text_input("Enter the season year:")

    # Once the user clicks 'Search!' begin to execute this logic.
    if st.sidebar.button('Search!'):
        if club_name and season and league:
            team_stats = get_team_stats(club_name, club_country, season, league)

            if isinstance(team_stats, dict) and "Club" in team_stats:
                team_name = team_stats["Club"].pop("Name")
                team_logo = team_stats["Club"].pop("Logo")

                # Load the stats into the dict.
                stats_dict = team_stats["Stats"]

                # Create the table labels for the team.
                all_labels = list(stats_dict.keys())

                # Now, create a list of values for the team.
                team_values = [stats_dict.get(label, 0) for label in all_labels]

                # Check if team's stats have same length, fill with zero if not!
                while len(team_values) < len(all_labels):
                    team_values.append(0)

                if chart_option == 'An In-Depth Look':
                    st.image(team_logo)
                    st.markdown(f"### {team_name}")

                    # Simplify the stats -- a lot of these stats aren't needed and are translated visually below.
                    simplified_stats = {
                        'Total Games': team_stats["Stats"]['Total Games'],
                        'Total Wins': team_stats["Stats"]['Total Wins'],
                        'Total Draws': team_stats["Stats"]['Total Draws'],
                        'Total Losses': team_stats["Stats"]['Total Losses'],
                        'Total Goals Scored': team_stats["Stats"]['Total Goals Scored'],
                        'Average Goals Scored': team_stats["Stats"]['Average Goals Scored'],
                        'Total Goals Conceded': team_stats["Stats"]['Total Goals Conceded'],
                        'Average Goals Conceded': team_stats["Stats"]['Average Goals Conceded'],
                        'Longest Win Streak': team_stats["Stats"]['Longest Win Streak'],
                        'Longest Draw Streak': team_stats["Stats"]['Longest Draw Streak'],
                        'Longest Lose Streak': team_stats["Stats"]['Longest Lose Streak'],
                        'Biggest Win': max(
                            [team_stats["Stats"]['Biggest Home Win'], team_stats["Stats"]['Biggest Away Win']]),
                        'Biggest Loss': max(
                            [team_stats["Stats"]['Biggest Home Loss'], team_stats["Stats"]['Biggest Away Loss']]),
                        'Total Clean Sheets': team_stats["Stats"]['Total Clean Sheets'],
                        'Total Times Failed to Score': team_stats["Stats"]['Total Times Failed to Score'],
                    }

                    with st.spinner("Generating stat table..."):
                        simplified_stats_df = pd.DataFrame(
                            data={'Statistic': list(simplified_stats.keys()), 'Value': list(simplified_stats.values())})
                        simplified_stats_df.index = np.arange(1, len(simplified_stats_df) + 1)
                        st.markdown(f"### {int(season)} - {int(season) + int(1)} Season Stats")
                        st.table(simplified_stats_df)

                    # Display win data within a heatmap using seaborn. Generate to small size so we don't overwhelm user!
                    win_data = {
                        "Wins": [stats_dict['Total Wins Home'], stats_dict['Total Wins Away'],
                                 stats_dict['Total Wins']],
                        "Draws": [stats_dict['Total Draws Home'], stats_dict['Total Draws Away'],
                                  stats_dict['Total Draws']],
                        "Losses": [stats_dict['Total Losses Home'], stats_dict['Total Losses Away'],
                                   stats_dict['Total Losses']]
                    }

                    with st.spinner("Generating charts..."):
                        # A heatmap of games won/lost/drawn.
                        df = pd.DataFrame(win_data, index=["Home", "Away", "Total"])

                        fig, ax = plt.subplots(figsize=(10, 5))
                        sns.heatmap(df, annot=True, fmt='d', cmap='YlGnBu', ax=ax, cbar_kws={'label': 'Number of Games'})
                        ax.set_title('Game Results Breakdown')
                        ax.set_xlabel('Result Type')
                        ax.set_ylabel('Location')
                        heatmap_fig = fig

                        # Formations used + percentage of time used!
                        formation_names = team_stats["Stats"]["Lineups"].keys()
                        formation_counts = team_stats["Stats"]["Lineups"].values()
                        formations = list(formation_names)
                        counts = list(formation_counts)
                        colors = cm.rainbow(np.linspace(0, 1, len(formations)))
                        explode = [0.1 if count == max(counts) else 0 for count in
                                   counts]

                        fig, ax = plt.subplots(figsize=(5, 5))
                        ax.pie(counts, labels=formations, autopct='%1.1f%%', colors=colors, explode=explode)
                        ax.set_title('Formations Used')
                        ax.legend(formations, title="Formations", loc="upper right", bbox_to_anchor=(1, 0, 0.5, 1))
                        formations_pie_chart_fig = fig

                        # A bar chart for longest streaks.
                        streak_types = ["Win", "Draw", "Lose"]
                        streak_lengths = [team_stats["Stats"]["Longest " + t + " Streak"] for t in streak_types]

                        fig, ax = plt.subplots(figsize=(10, 5))
                        bars = ax.barh(streak_types, streak_lengths, color=['green', 'blue', 'red'])

                        for bar in bars:
                            width = bar.get_width()
                            ax.text(width, bar.get_y() + bar.get_height() / 2, f' {width}', ha='left', va='center',
                                    color='black')

                        ax.set_xlabel('Streak Length')
                        ax.set_ylabel('Streak Type')
                        ax.set_title('Longest Streaks')
                        streak_bar_chart_fig = fig

                        season_form = team_stats["Stats"]["Club Form"]

                        # Mapping each result to its corresponding points.
                        points_mapping = {'W': 3, 'D': 1, 'L': 0}
                        points = [points_mapping[game_result] for game_result in season_form]

                        # Creating a running total of points.
                        cumulative_points = [sum(points[:i + 1]) for i in range(len(points))]

                        # A line chart for points accumulated over the course of a season.
                        fig, ax = plt.subplots(figsize=(10, 5))
                        ax.plot(cumulative_points, marker='o', color='black')

                        # Add a red dot for the maximum point accumulation for user visibility.
                        max_points = max(cumulative_points)
                        max_points_index = cumulative_points.index(max_points)
                        ax.plot(max_points_index, max_points, marker='o', color='red')

                        # Add a text label for the maximum point accumulation at the end of the season.
                        ax.text(max_points_index, max_points, f'  Max ({max_points})', ha='left', va='bottom', color='red')

                        ax.set_title(f'{team_name}\'s Season Points Accumulation')
                        ax.set_xlabel('Matchday')
                        ax.set_ylabel('Cumulative Points')
                        ax.grid(True)

                        # Shading for the line chart so we can see where teams had poor results.
                        start_shade = None
                        for i, game_result in enumerate(season_form):
                            if game_result in {'D', 'L'} and start_shade is None:
                                start_shade = i
                            elif game_result == 'W' and start_shade is not None:
                                ax.fill_between([start_shade - 1, i - 1], 0, max(cumulative_points), color='red', alpha=0.1)
                                start_shade = None
                        if start_shade is not None:
                            ax.fill_between([start_shade - 1, len(season_form)], 0, max(cumulative_points), color='red',
                                            alpha=0.1)

                        points_accumulated_fig = fig

                    st.markdown("### Data Visualization")
                    st.write("You can find visualized data in this section. In order to expand the charts, hover over "
                             "the chart and click the full-screen button on the top-right corner of the chart.")
                    st.markdown("<hr/>", unsafe_allow_html=True)

                    col1, col2 = st.columns(2)
                    with col1:
                        st.pyplot(heatmap_fig)
                        st.markdown("<h4 style='text-align: center; color: white;'>Game Results Heatmap</h4>",
                                    unsafe_allow_html=True)
                    with col2:
                        st.pyplot(formations_pie_chart_fig)
                        st.markdown("<h4 style='text-align: center; color: white;'>Formation Frequencies</h4>",
                                    unsafe_allow_html=True)

                    col1, col2 = st.columns(2)
                    with col1:
                        st.pyplot(streak_bar_chart_fig)
                        st.markdown("<h4 style='text-align: center; color: white;'>Longest Streaks</h4>",
                                    unsafe_allow_html=True)
                    with col2:
                        st.pyplot(points_accumulated_fig)
                        st.markdown("<h4 style='text-align: center; color: white;'>Points Accumulated</h4>",
                                    unsafe_allow_html=True)

                    st.markdown("<hr/>", unsafe_allow_html=True)

                elif chart_option == 'Season at a Glance':

                    with st.spinner('Loading team data...'):
                        st.image(team_logo)

                        performance = calculate_performance(stats_dict, season)

                        # Color the number based on performance.
                        if performance <= 1:
                            color = "red"

                        elif 1 < performance <= 2.5:
                            color = "yellow"

                        else:
                            color = "green"

                        st.markdown(f"### {team_name}'s {int(season)} - {int(season) + int(1)} Overall Season Performance:")
                        st.markdown(f"<h3 style='text-align: start; color: {color};'>{performance:.2f}</h3>",
                                    unsafe_allow_html=True)

                        st.markdown(
                            f"Team performance is calculated based on total wins, total losses, and total goals scored. The higher the value, the better the team performance. "
                            f"These values typically lie between **0** and **3.5.** ")

                        # Read in the other stats and use them to create a dynamic summary.
                        # Initially, these were supposed to be tiles (hence "tile_stats"), but Streamlit
                        # was very difficult when attempting this so I settled for a season summary.
                        simplified_tile_stats = {
                            'Total Games': team_stats["Stats"]['Total Games'],
                            'Total Wins': team_stats["Stats"]['Total Wins'],
                            'Total Draws': team_stats["Stats"]['Total Draws'],
                            'Total Losses': team_stats["Stats"]['Total Losses'],
                            'Total Goals Scored': team_stats["Stats"]['Total Goals Scored'],
                            'Total Goals Conceded': team_stats["Stats"]['Total Goals Conceded'],
                            'Longest Win Streak': team_stats["Stats"]['Longest Win Streak'],
                            'Longest Draw Streak': team_stats["Stats"]['Longest Draw Streak'],
                            'Longest Lose Streak': team_stats["Stats"]['Longest Lose Streak'],
                            'Biggest Win': max(
                                [team_stats["Stats"]['Biggest Home Win'], team_stats["Stats"]['Biggest Away Win']]),
                            'Biggest Loss': max(
                                [team_stats["Stats"]['Biggest Home Loss'], team_stats["Stats"]['Biggest Away Loss']]),
                            'Total Clean Sheets': team_stats["Stats"]['Total Clean Sheets'],
                            'Total Times Failed to Score': team_stats["Stats"]['Total Times Failed to Score'],
                        }

                        # Extract the stats from the dictionary.
                        total_games = simplified_tile_stats['Total Games']
                        total_wins = simplified_tile_stats['Total Wins']
                        total_draws = simplified_tile_stats['Total Draws']
                        total_losses = simplified_tile_stats['Total Losses']
                        total_goals_scored = simplified_tile_stats['Total Goals Scored']
                        total_goals_conceded = simplified_tile_stats['Total Goals Conceded']
                        biggest_win = simplified_tile_stats['Biggest Win']
                        biggest_loss = simplified_tile_stats['Biggest Loss']
                        total_clean_sheets = simplified_tile_stats['Total Clean Sheets']
                        total_times_failed_to_score = simplified_tile_stats['Total Times Failed to Score']

                        # Calculate various statistic variables for the summary.
                        win_rate = total_wins / total_games * 100
                        loss_rate = total_losses / total_games * 100
                        clean_sheet_rate = total_clean_sheets / total_games * 100
                        goal_difference = total_goals_scored - total_goals_conceded

                    # Begin the dynamic summary.
                    with st.spinner('Creating summary...'):
                        summary = f"During the {int(season)} - {int(season) + int(1)} season, {team_name} played a total of {total_games} games."

                        if win_rate >= 65:
                            summary += f" They had an incredible season, with a strong performance score of {performance:.2f} and winning at least two-thirds of their games, a total of {total_wins} victories and a win percentage of {win_rate:.2f}%."
                        elif win_rate >= 51:
                            summary += f" They had a decent season, with a performance score of {performance:.2f} and victories in just over half of their games with a total of {total_wins} victories and a win percentage of {win_rate:.2f}%."
                        elif win_rate <= 33:
                            summary += f" Unfortunately, they struggled throughout the season, with a poor performance score of {performance:.2f} winning just {total_wins} games out of {total_games} played with a loss percentage of {loss_rate:.2f}%."
                        else:
                            summary += f" They had a fairly balanced season -- {total_wins} wins from their {total_games} games with {win_rate:.2f}% of games won and {loss_rate:.2f}% of games lost, leaving them with a performance score of {performance:.2f}."

                        if goal_difference > 0:
                            summary += f" With {total_goals_scored} goals scored and {total_goals_conceded} goals conceded, they had a positive goal difference of {goal_difference}."
                        else:
                            summary += f" With {total_goals_scored} goals scored and {total_goals_conceded} goals conceded, they had a negative goal difference of {goal_difference}."

                        if total_clean_sheets > total_games / 3:
                            summary += f" They had quite a stalwart defense, leading them to a clean sheet over {clean_sheet_rate:.2f}% of games, with a total of {total_clean_sheets} clean sheets."
                        else:
                            summary += f" They could do with a stronger defense -- they only managed a clean sheet in about {clean_sheet_rate:.2f}% of games, with a total of {total_clean_sheets} clean sheets."

                        if total_times_failed_to_score < total_games / 2:
                            summary += f" Their attack was quite potent -- they only failed to score a total of {total_times_failed_to_score} games over {total_games} games played. Dangerous."
                        else:
                            summary += f" Their attackers were off the mark this season, as they failed to score {total_times_failed_to_score} times over {total_games} games played. Quite poor."

                        summary += f" Their biggest win was {biggest_win}, and the biggest loss was {biggest_loss}."

                        st.markdown(summary)

                        st.divider()

                        st.markdown(
                            "##### ⬅️ To see detailed statistics and charts, choose 'An In-Depth Look' from the side bar. ")

                else:
                    # Error handling with st.error.
                    st.error(f"Error: {team_stats}")
