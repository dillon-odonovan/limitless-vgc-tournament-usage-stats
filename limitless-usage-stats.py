from bs4 import BeautifulSoup, ResultSet, Tag
from io import TextIOWrapper
from os import makedirs
from os.path import basename, dirname, exists, relpath
from pathvalidate import sanitize_filename
from requests import get
from time import sleep
from typing import NamedTuple


FILE_DOWNLOAD_SLEEP_TIME = 0.5
LIMITLESS_BASE_URL = 'https://play.limitlesstcg.com'


def main() -> None:
    tournament_id = ask_tournament_id()
    tournament = download_and_parse_tournament_standings(
        tournament_id)
    teamsheet_urls = get_teamsheet_urls(tournament.parsed_standings)
    download_teamsheets(teamsheet_urls)
    teams = get_teams(tournament.parsed_standings)
    top_cut_teams = get_top_cut_teams(teams)
    all_usage_stats = calculate_usage_statistics(teams)
    top_cut_usage_stats = calculate_usage_statistics(top_cut_teams)
    write_usage_to_file(tournament_id,
                        tournament.tournament_name,
                        len(top_cut_teams),
                        top_cut_usage_stats,
                        len(teams),
                        all_usage_stats)


def ask_tournament_id() -> str:
    """Prompt user for Limitless Tournament ID

    Returns:
        str: The tournament ID provided by the user
    """
    return input('Enter Limitless Tournament ID: ')


class Tournament(NamedTuple):
    tournament_name: str
    parsed_standings: BeautifulSoup


def download_and_parse_tournament_standings(tournament_id: str) -> Tournament:
    """Download and parse the Limitless tournament standings.

    For the provided tournament_id, download the tournament standings from the Limitless website and return as parsed BeautifulSoup.

    Args:
        tournament_id -- the Limitless Tournament ID for which to retrieve standings

    Returns:
        BeautifulSoup: The parsed standings represented as Beautiful Soup
    """
    standings = get(
        f'{LIMITLESS_BASE_URL}/tournament/{tournament_id}/standings')
    parsed_standings = BeautifulSoup(
        standings.text.encode('utf-8', 'ignore'), features='html.parser')
    tournament_name = parsed_standings.find(
        'div', class_=is_class_name).contents[0]
    sanitized_tournament_name = sanitize_filename(tournament_name)
    standings_filename = f'./tournament/{tournament_id}/standings/{sanitized_tournament_name}.html'
    makedirs(dirname(standings_filename), exist_ok=True)
    with open(standings_filename, 'w', encoding='utf-8') as standings_file:
        standings_file.write(standings.text)
    return Tournament(sanitized_tournament_name, parsed_standings)


def is_class_name(class_: str) -> bool:
    """Determines whether the HTML class is 'name'

    Args:
        class_: The HTML class

    Returns:
        bool: True if class_ is 'name'; else, False.
    """
    return class_ == 'name'


def get_teamsheet_urls(parsed_standings: BeautifulSoup) -> list[str]:
    """Get all teamsheet URLs from the parsed HTML

    Args:
        parsed_standings: The BeautifulSoup representation of the tournament standings

    Returns:
        list[str]: A list of all teamsheet relative URLs
    """
    return [a['href']
            for a in parsed_standings.find_all('a')
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
            teamsheet = get(f'{LIMITLESS_BASE_URL}{teamsheet_url}')
            makedirs(dirname(teamsheet_file_path), exist_ok=True)
            with open(teamsheet_file_path, 'w', encoding='utf-8') as teamsheet_file:
                teamsheet_file.write(teamsheet.text)
            sleep(FILE_DOWNLOAD_SLEEP_TIME)


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


class PokemonStats:
    def __init__(self):
        self.count = 0
        self.item = {}
        self.ability = {}
        self.tera = {}
        self.attacks = {}


def calculate_usage_statistics(teams: ResultSet) -> dict[str, PokemonStats]:
    all_pokemon_statistics: dict[str, PokemonStats] = {}

    for team in teams:
        tds = team.find_all('td')
        teamlist_href = tds[8].a['href']
        with open(f'.{teamlist_href}.html', 'r') as teamlist:
            teamlist_parsed = BeautifulSoup(
                teamlist, features='html.parser', from_encoding='utf-8')
            pokemon_used = teamlist_parsed.find_all(
                'div', class_=is_class_pkmn)
            for pokemon in pokemon_used:
                pokemon_name_div = pokemon.find(
                    'div', class_=is_class_name)
                pokemon_name = pokemon_name_div.span.text

                pokemon_stats: PokemonStats
                if pokemon_name in all_pokemon_statistics:
                    pokemon_stats = all_pokemon_statistics[pokemon_name]
                else:
                    pokemon_stats = PokemonStats()
                    all_pokemon_statistics[pokemon_name] = pokemon_stats

                pokemon_stats.count += 1

                pokemon_details = pokemon.find('div', class_=is_class_details)

                pokemon_item = pokemon_details.find(
                    'div', class_=is_class_item).text
                add_or_update_dict(pokemon_stats.item, pokemon_item)

                pokemon_ability = pokemon_details.find(
                    'div', class_=is_class_ability).text.split('Ability: ')[1]
                add_or_update_dict(pokemon_stats.ability, pokemon_ability)

                pokemon_tera_div = pokemon_details.find(
                    'div', class_=is_class_tera)
                pokemon_tera = pokemon_tera_div.text.split(
                    'Tera Type: ')[1] if pokemon_tera_div is not None else 'default'
                add_or_update_dict(pokemon_stats.tera, pokemon_tera)

                pokemon_attacks = pokemon.find('ul', class_=is_class_attacks)
                for attack_li in pokemon_attacks.find_all('li'):
                    attack = attack_li.text
                    add_or_update_dict(pokemon_stats.attacks, attack)

    return all_pokemon_statistics


def add_or_update_dict(dict: dict[str, int], key: str) -> None:
    """Adds the key to dict or updates its count in the dict if present.

    Args:
        dict: The dict to modify
        key: The key in the dict to add or update
    """
    if key in dict:
        dict[key] += 1
    else:
        dict[key] = 1


def is_class_pkmn(class_: str) -> bool:
    """Determines whether the HTML class is 'pkmn'

    Args:
        class_: The HTML class

    Returns:
        bool: True if class_ is 'pkmn'; else, False.
    """
    return class_ == 'pkmn'


def is_class_details(class_: str) -> bool:
    """Determines whether the HTML class is 'details'

    Args:
        class_: The HTML class

    Returns:
        bool: True if class_ is 'details'; else, False.
    """
    return class_ == 'details'


def is_class_item(class_: str) -> bool:
    """Determines whether the HTML class is 'item'

    Args:
        class_: The HTML class

    Returns:
        bool: True if class_ is 'item'; else, False.
    """
    return class_ == 'item'


def is_class_ability(class_: str) -> bool:
    """Determines whether the HTML class is 'ability'

    Args:
        class_: The HTML class

    Returns:
        bool: True if class_ is 'ability'; else, False.
    """
    return class_ == 'ability'


def is_class_tera(class_: str) -> bool:
    """Determines whether the HTML class is 'tera'

    Args:
        class_: The HTML class

    Returns:
        bool: True if class_ is 'tera'; else, False.
    """
    return class_ == 'tera'


def is_class_attacks(class_: str) -> bool:
    """Determines whether the HTML class is 'attacks'

    Args:
        class_: The HTML class

    Returns:
        bool: True if class_ is 'attacks'; else, False.
    """
    return class_ == 'attacks'


def write_usage_to_file(tournament_id: str,
                        tournament_name: str,
                        num_top_cut_teams: int,
                        top_cut_usage_stats: dict[str, PokemonStats],
                        num_teams: int,
                        all_usage_stats: dict[str, PokemonStats]):
    ordered_top_cut_usage_stats = {key: val for key, val in sorted(
        top_cut_usage_stats.items(), key=lambda item: item[1].count, reverse=True)}
    ordered_usage_stats = {key: val for key, val in sorted(
        all_usage_stats.items(), key=lambda item: item[1].count, reverse=True)}
    filepath = f'./tournament/{tournament_id}/usage/{tournament_name} Usage.txt'
    makedirs(dirname(filepath), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as usage_stats_file:
        usage_stats_file.write(f'{tournament_name} ({tournament_id})\n')
        usage_stats_file.write('\n')
        usage_stats_file.write(f'Top cut: {num_top_cut_teams}\n')
        usage_stats_file.write('Top cut usage:\n')
        write_usage_stats(usage_stats_file,
                          ordered_top_cut_usage_stats, num_top_cut_teams)
        usage_stats_file.write('\n')
        usage_stats_file.write(f'Entrants: {num_teams}\n')
        usage_stats_file.write('All usage:\n')
        write_usage_stats(usage_stats_file, ordered_usage_stats, num_teams)


def write_usage_stats(file: TextIOWrapper, usage_stats: dict[str, PokemonStats], num_teams: int):
    for index, (pokemon, pokemon_stats) in enumerate(usage_stats.items()):
        file.write(
            f'\t{get_stat(index, pokemon, pokemon_stats.count, num_teams)}\n')
        file.write('\t\tAbility:\n')
        write_stat(file, pokemon_stats.ability, pokemon_stats.count)
        file.write('\t\tTera:\n')
        write_stat(file, pokemon_stats.tera, pokemon_stats.count)
        file.write('\t\tItem:\n')
        write_stat(file, pokemon_stats.item, pokemon_stats.count)
        file.write('\t\tAttacks:\n')
        write_stat(file, pokemon_stats.attacks, pokemon_stats.count)


def write_stat(file: TextIOWrapper, dict: dict[str, int], total: int):
    for i, (item, count) in enumerate(order_dict_by_count(dict).items()):
        file.write(
            f'\t\t\t{get_stat(i, item, count, total)}\n')


def order_dict_by_count(d: dict[str, int]) -> dict[str, int]:
    return {key: val
            for key, val in sorted(d.items(),
                                   key=lambda item: item[1],
                                   reverse=True)}


def get_stat(index: int, name: str, count: int, total: int):
    return f'{index + 1}. {name}: {get_percentage(count, total)}% ({count})'


def get_percentage(a, b):
    return round(100 * a / b, 2)


if __name__ == '__main__':
    main()
