from bs4 import BeautifulSoup, ResultSet, Tag
from io import TextIOWrapper
from os import makedirs
from os.path import basename, dirname, exists, relpath
from pathvalidate import sanitize_filename
import requests
from time import sleep


FILE_DOWNLOAD_SLEEP_TIME = 0.5
LIMITLESS_BASE_URL = 'https://play.limitlesstcg.com'


def main() -> None:
    tournament_id = ask_tournament_id()
    parsed_standings = download_and_parse_tournament_standings(tournament_id)
    teamsheet_urls = get_teamsheet_urls(parsed_standings)
    download_teamsheets(teamsheet_urls)
    teams = get_teams(parsed_standings)
    top_cut_teams = get_top_cut_teams(teams)

    # pokemon = get_pokemon_from_teams(teams)
    # top_sixteen_pokemon = get_pokemon_from_teams(top_cut_teams)
    # pokemon_usage = get_pokemon_usage(pokemon)
    # top_sixteen_usage = get_pokemon_usage(top_sixteen_pokemon)
    # ordered_pokemon_usage = order_pokemon_by_usage(pokemon_usage)
    # ordered_top_sixteen_usage = order_pokemon_by_usage(top_sixteen_usage)
    # write_ordered_pokemon_usage_to_file(
    #     file_path, len(teams), ordered_pokemon_usage, ordered_top_sixteen_usage)


def ask_tournament_id() -> str:
    """Prompt user for Limitless Tournament ID

    Returns:
        str: The tournament ID provided by the user
    """
    return input('Enter Limitless Tournament ID: ')


def download_and_parse_tournament_standings(tournament_id: str) -> BeautifulSoup:
    """Download and parse the Limitless tournament standings.

    For the provided tournament_id, download the tournament standings from the Limitless website and return as parsed BeautifulSoup.

    Args:
        tournament_id -- the Limitless Tournament ID for which to retrieve standings

    Returns:
        BeautifulSoup: The parsed standings represented as Beautiful Soup
    """
    standings = requests.get(
        f'{LIMITLESS_BASE_URL}/tournament/{tournament_id}/standings')
    parsed_standings = BeautifulSoup(
        standings.text, features='html.parser')
    tournament_name = parsed_standings.find(
        'div', class_=class_is_name).contents[0]
    standings_filename = f'./tournament/{tournament_id}/standings/{sanitize_filename(tournament_name)}.html'
    makedirs(dirname(standings_filename), exist_ok=True)
    with open(standings_filename, 'w', encoding='utf-8') as standings_file:
        standings_file.write(standings.text)
    return parsed_standings


def class_is_name(class_: str) -> bool:
    """Determines whether the HTML class is 'name'

    Args:
        class_: The HTML class

    Returns:
        bool: True if class_ is 'name'; else, False.
    """
    return class_ == 'name'


def get_teams(parsed_standings: BeautifulSoup) -> ResultSet:
    """Gets the teams, in order, used in the tournament

    Args:
        parsed_standings: The parsed BeautifulSoup representation of the tournament standings

    Returns:
        ResultSet: The list of teams used in the tournament as a ResultSet
    """
    return parsed_standings.find_all(is_tr_and_has_data_placing_attr)


def is_tr_and_has_data_placing_attr(tag: Tag) -> bool:
    """Determines whether the tag is a 'tr' tag and has attribute 'data-placing'

    Args:
        tag: The HTML tag

    Returns:
        bool: True if tag is a 'tr' tag and has attr 'data-placing'; else, False.
    """
    return tag.name == 'tr' and tag.has_attr('data-placing')


def get_top_cut_teams(teams: ResultSet) -> ResultSet:
    """Gets all of the teams that top cut the event

    For tournaments with 2 days of Swiss all teams with 2 or fewer losses after the first day of swiss are considered top cut teams.
    If only a single day of swiss then the user will input what the size of the top cut was for that tournament.

    Args:
        teams: The list of all teams that participated in the tournament

    Returns:
        ResultSet: The subset of teams that made top cut
    """
    num_days_swiss = 0
    while True:
        try:
            num_days_swiss = int(input('Were there 1 or 2 days of swiss? '))
            if num_days_swiss <= 0 or num_days_swiss > 2:
                raise Exception()
            break
        except Exception:
            print("Please enter '1' or '2' for number of days of swiss.")

    if num_days_swiss == 2:
        num_day_one_swiss_rounds = 0
        while True:
            try:
                num_day_one_swiss_rounds = int(
                    input('How many rounds of swiss were there on day 1? '))
                if num_day_one_swiss_rounds <= 0:
                    raise Exception()
                break
            except:
                print(
                    'Please enter a valid integer greater than 0 for number of swiss rounds on day 1.')

        return [team
                for team in teams
                if int(team.find_all('td')[3].contents[0]) >= num_day_one_swiss_rounds - 2]
    else:
        top_cut_size = 0
        num_teams = len(teams)
        while True:
            try:
                top_cut_size = int(input('What was the size of top cut? '))
                if top_cut_size <= 0 or top_cut_size > num_teams:
                    raise Exception()
                break
            except:
                print(
                    f'Top cut size must be at least 1 and no more than the number of teams ({num_teams})')
        return teams[:top_cut_size]


def get_teamsheet_urls(parsed_html: BeautifulSoup) -> list[str]:
    """

    """
    return [a['href']
            for a in parsed_html.find_all('a')
            if a.has_attr('href')
            and a['href'].endswith('teamlist')]


def download_teamsheets(teamsheet_urls: list[str]) -> None:
    """Download all teamsheets from the list of URLs

    Downloads each teamsheet from the Limitless website, provided it does not already exist on disk.

    Args:
        teamsheet_urls: The list of relative URLs of tournament teamsheets to download
    """
    for teamsheet_url in teamsheet_urls:
        teamsheet_file_path = f'.{teamsheet_url}.html'
        if not exists(teamsheet_file_path):
            teamsheet = requests.get(f'{LIMITLESS_BASE_URL}{teamsheet_url}')
            makedirs(dirname(teamsheet_file_path), exist_ok=True)
            with open(teamsheet_file_path, 'w', encoding='utf-8') as teamsheet_file:
                teamsheet_file.write(teamsheet.text)
            sleep(FILE_DOWNLOAD_SLEEP_TIME)


def get_pokemon_from_teams(teams: ResultSet) -> list[str]:
    return [span['title']
            for team in teams
            for span in team.find_all('span')
            if span.has_attr('title')]


def get_pokemon_usage(pokemon: list[str]) -> dict[str, int]:
    pokemon_usage = {}
    for poke in pokemon:
        if poke in pokemon_usage:
            pokemon_usage[poke] += 1
        else:
            pokemon_usage[poke] = 1
    return pokemon_usage


def order_pokemon_by_usage(pokemon_usage: dict[str, int]) -> dict[str, int]:
    return {key: val
            for key, val in sorted(pokemon_usage.items(),
                                   key=lambda item: item[1],
                                   reverse=True)}


def write_ordered_pokemon_usage_to_file(file_path: str, num_teams: int, ordered_pokemon_usage: dict[str, int], ordered_top_sixteen_usage: dict[str, int]) -> None:
    with open(f'./{dirname(relpath(file_path))}/{basename(file_path)}-Usage.txt', 'w', encoding='utf-8') as usage_stats_file:
        usage_stats_file.write(f'Entrants: {num_teams}\n\n')
        usage_stats_file.write('Top 16 Usage:\n')
        write_usage_stats(usage_stats_file, ordered_top_sixteen_usage, 16)
        usage_stats_file.write('\n')
        usage_stats_file.write('All Usage:\n')
        write_usage_stats(usage_stats_file, ordered_pokemon_usage, num_teams)


def write_usage_stats(file: TextIOWrapper, usage_stats: dict[str, int], num_teams: int):
    for index, (pokemon, num_used) in enumerate(usage_stats.items()):
        file.write(
            f'{index + 1}. {pokemon}: {round(100 * num_used / num_teams, 2)}% ({num_used})\n')


if __name__ == '__main__':
    main()
