from bs4 import BeautifulSoup, ResultSet, Tag
from io import TextIOWrapper
import jsonpickle
from math import sqrt
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
import numpy as np
from os import makedirs
from os.path import dirname, exists
from pathvalidate import sanitize_filename
from requests import get
from time import sleep
from typing import Any, NamedTuple


FILE_DOWNLOAD_SLEEP_TIME = 0.33
LIMITLESS_BASE_URL = 'https://play.limitlesstcg.com'
DEFAULT_LABEL_PADDING = .0015
LABEL_PADDING_INCREMENT = .0025
LABEL_FONT_SIZE = 6
POINT_DISTANCE_LABEL_ADJUSTMENT_THRESHOLD = .01
AXIS_MIN = 0
AXIS_ZOOMED_IN_MAX = 0.2
AXIS_MAX_BUFFER = 0.1
AXIS_TICK_MAX = 1.0


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
    tournament_usage = TournamentUsage(tournament_id,
                                       tournament.tournament_name,
                                       len(top_cut_teams),
                                       top_cut_usage_stats,
                                       len(teams),
                                       all_usage_stats)
    write_usage_to_file(tournament_usage)
    create_graph(tournament_usage)


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
    print("Downloading standings...")
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
    print("Done downloading standings.")
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
    print("Downloading teamsheets...")
    for teamsheet_url in teamsheet_urls:
        teamsheet_file_path = f'.{teamsheet_url}.html'
        if not exists(teamsheet_file_path):
            teamsheet = get(f'{LIMITLESS_BASE_URL}{teamsheet_url}')
            makedirs(dirname(teamsheet_file_path), exist_ok=True)
            with open(teamsheet_file_path, 'w', encoding='utf-8') as teamsheet_file:
                teamsheet_file.write(teamsheet.text)
            sleep(FILE_DOWNLOAD_SLEEP_TIME)
    print("Done downloading teamsheets.")


def get_teams(parsed_standings: BeautifulSoup) -> ResultSet:
    """Gets the teams, in order, used in the tournament

    Args:
        parsed_standings: The parsed BeautifulSoup representation of the tournament standings

    Returns:
        ResultSet: The list of teams used in the tournament as a ResultSet
    """
    field_size = -1
    while True:
        try:
            field_size_inp = input(
                'How many teams you do want to consider? (Enter for all) ')
            if field_size_inp == '':
                break
            field_size = int(field_size_inp)
            if field_size <= 0:
                raise Exception()
            break
        except:
            print(f'Size of field must be at least 1')
    return parsed_standings.find_all(is_tr_and_has_data_placing_attr)[:field_size]


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

    The user will input what the size of the top cut was for the tournament.

    Args:
        teams: The list of all teams that participated in the tournament

    Returns:
        ResultSet: The subset of teams that made top cut
    """
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
        self.teammates = {}
        self.placings = []


def calculate_usage_statistics(teams: ResultSet) -> dict[str, PokemonStats]:
    all_pokemon_statistics: dict[str, PokemonStats] = {}

    for placing, team in enumerate(teams):
        teamlist_href = team.find('a', href=href_ends_with_teamlist)['href']
        with open(f'.{teamlist_href}.html', 'r') as teamlist:
            teamlist_parsed = BeautifulSoup(
                teamlist, features='html.parser', from_encoding='utf-8')
            pokemon_used = teamlist_parsed.find_all(
                'div', class_=is_class_pkmn)
            for pokemon in pokemon_used:
                pokemon_name = get_pokemon_name(pokemon)

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

                teammates = [get_pokemon_name(p)
                             for p in pokemon_used
                             if not get_pokemon_name(p) == pokemon_name]
                for teammate in teammates:
                    add_or_update_dict(pokemon_stats.teammates, teammate)

                pokemon_stats.placings.append(placing + 1)

    return all_pokemon_statistics


def href_ends_with_teamlist(href: str) -> bool:
    """Determines whether the href attribute ends with 'teamlist'

    Args:
        href: The HTML href attribute

    Returns:
        bool: True if href ends with 'teamlist'; else, False.
    """
    return href.endswith('teamlist')


def get_pokemon_name(pokemon: Any) -> str:
    """Gets the name of the Pokemon from the HTML

    Args:
        pokemon: The HTML representation of the Pokemon

    Returns:
        str: The name of the Pokemon
    """
    pokemon_name_div = pokemon.find('div', class_=is_class_name)
    return pokemon_name_div.span.text


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


def sort_by_usage_then_alphabetical(item: tuple[str, PokemonStats]):
    return (-item[1].count, item[0])


class TournamentUsage:
    def __init__(self,
                 tournament_id: str,
                 tournament_name: str,
                 top_cut_size: int,
                 top_cut_usage: PokemonStats,
                 size: int,
                 all_usage: PokemonStats) -> None:
        self.tournament_id = tournament_id
        self.tournament_name = tournament_name
        self.top_cut_size = top_cut_size
        self.top_cut_usage: dict[str, PokemonStats] = {
            key: val
            for key, val in sorted(top_cut_usage.items(),
                                   key=lambda item: sort_by_usage_then_alphabetical(item))
        }
        self.size = size
        self.all_usage: dict[str, PokemonStats] = {
            key: val
            for key, val in sorted(all_usage.items(),
                                   key=lambda item: sort_by_usage_then_alphabetical(item))
        }


def write_usage_to_file(tournament_usage: TournamentUsage):
    tournament_id = tournament_usage.tournament_id
    tournament_name = tournament_usage.tournament_name
    output_dir = get_output_dir(tournament_id)
    file_name = f'{tournament_name} Usage'

    usage_filepath = f'{output_dir}/{file_name}.txt'
    makedirs(dirname(usage_filepath), exist_ok=True)
    with open(usage_filepath, 'w', encoding='utf-8') as usage_stats_file:
        usage_stats_file.write(f'{tournament_name} ({tournament_id})\n')
        usage_stats_file.write('\n')

        usage_stats_file.write(f'Top cut: {tournament_usage.top_cut_size}\n')
        usage_stats_file.write('Top cut usage:\n')
        write_usage_stats(
            usage_stats_file, tournament_usage.top_cut_usage, tournament_usage.top_cut_size)
        usage_stats_file.write('\n')

        usage_stats_file.write(f'Entrants: {tournament_usage.size}\n')
        usage_stats_file.write('All usage:\n')
        write_usage_stats(usage_stats_file,
                          tournament_usage.all_usage, tournament_usage.size)

    with open(f'{output_dir}/{tournament_usage.tournament_id}-all.json', 'w', encoding='utf-8') as all_json:
        all_json.write(jsonpickle.encode(tournament_usage.all_usage))

    with open(f'{output_dir}/{tournament_usage.tournament_id}-top-cut.json', 'w', encoding='utf-8') as top_cut_json:
        top_cut_json.write(jsonpickle.encode(tournament_usage.top_cut_usage))


def get_output_dir(tournament_id: str) -> str:
    return f'./tournament/{tournament_id}/usage'


def write_usage_stats(file: TextIOWrapper, usage_stats: dict[str, PokemonStats], num_teams: int):
    for index, (pokemon, pokemon_stats) in enumerate(usage_stats.items()):
        file.write(
            f'\t{get_stat(index, pokemon, pokemon_stats.count, num_teams)}\n')
        file.write('\t\tAbility:\n')
        write_dict_stat(file, pokemon_stats.ability, pokemon_stats.count)
        file.write('\t\tTera:\n')
        write_dict_stat(file, pokemon_stats.tera, pokemon_stats.count)
        file.write('\t\tItem:\n')
        write_dict_stat(file, pokemon_stats.item, pokemon_stats.count)
        file.write('\t\tAttacks:\n')
        write_dict_stat(file, pokemon_stats.attacks, pokemon_stats.count)
        file.write('\t\tTeammates:\n')
        write_dict_stat(file, pokemon_stats.teammates, pokemon_stats.count)
        file.write('\t\tPlacings:\n')
        write_arr_stat(file, pokemon_stats.placings)


def write_arr_stat(file: TextIOWrapper, arr:  list[int]):
    for value in arr:
        file.write(f'\t\t\t{value}\n')


def write_dict_stat(file: TextIOWrapper, dict: dict[str, int], total: int):
    for i, (item, count) in enumerate(order_dict_by_count(dict).items()):
        file.write(
            f'\t\t\t{get_stat(i, item, count, total)}\n')


def order_dict_by_count(d: dict[str, int]) -> dict[str, int]:
    return {key: val
            for key, val in sorted(d.items(),
                                   # count then alphabetical
                                   key=lambda item: (item[1], item[0]),
                                   reverse=True)}


def get_stat(index: int, name: str, count: int, total: int):
    return f'{index + 1}. {name}: {get_percentage(count, total)}% ({count})'


def get_percentage(a, b):
    return round(100 * a / b, 2)


class UsagePoint:
    def __init__(self, total_usage_rate, top_cut_usage_rate, label) -> None:
        self.total_usage_rate = total_usage_rate
        self.top_cut_usage_rate = top_cut_usage_rate
        self.label = label


def create_graph(tournament_usage: TournamentUsage) -> None:
    pokemon_to_show = {
        pokemon for pokemon in tournament_usage.top_cut_usage.keys()}
    for pokemon, pokemon_stats in tournament_usage.all_usage.items():
        if pokemon_stats.count / tournament_usage.size >= 0.03:
            pokemon_to_show.add(pokemon)

    usage_points: list[UsagePoint] = []
    for pokemon in pokemon_to_show:
        usage_point = UsagePoint(tournament_usage.all_usage[pokemon].count / tournament_usage.size,
                                 tournament_usage.top_cut_usage[pokemon].count /
                                 tournament_usage.top_cut_size
                                 if pokemon in tournament_usage.top_cut_usage
                                 else 0,
                                 pokemon)
        usage_points.append(usage_point)

    usage_points = sorted(usage_points,
                          key=lambda point: (
                              point.top_cut_usage_rate, point.total_usage_rate),
                          reverse=True)

    fig, ax = plt.subplots()
    line = np.linspace(0, 1)
    ax.scatter([usage.total_usage_rate for usage in usage_points], [
               usage.top_cut_usage_rate for usage in usage_points])
    ax.plot(line, line, linewidth=0.25)

    label_padding = DEFAULT_LABEL_PADDING
    for index, usage_point in enumerate(usage_points):
        if index > 0 and index < len(usage_points):
            prev_usage_point = usage_points[index - 1]

            # sqrt[ (x2-x1)^2 + (y2-y1)^2 ]
            distance_between_points = sqrt(
                (usage_point.total_usage_rate - prev_usage_point.total_usage_rate) ** 2 +
                (usage_point.top_cut_usage_rate -
                 prev_usage_point.top_cut_usage_rate) ** 2
            )

            if distance_between_points <= POINT_DISTANCE_LABEL_ADJUSTMENT_THRESHOLD:
                label_padding += LABEL_PADDING_INCREMENT
            else:
                label_padding = DEFAULT_LABEL_PADDING

        ax.text(usage_point.total_usage_rate,
                usage_point.top_cut_usage_rate + label_padding,
                usage_point.label,
                size=LABEL_FONT_SIZE)

    ax.grid(visible=True, which='both')
    ax.set_title(
        f'{tournament_usage.tournament_name} ({tournament_usage.tournament_id}) Usage Stats')

    ax.set_xlabel('Total Usage Rate (Percent)')
    ax.xaxis.set_major_formatter(PercentFormatter(AXIS_TICK_MAX))

    ax.set_ylabel('Top Cut Usage Rate (Percent)')
    ax.yaxis.set_major_formatter(PercentFormatter(AXIS_TICK_MAX))

    most_used = first_key_in_dict(tournament_usage.all_usage)
    most_used_in_top_cut = first_key_in_dict(tournament_usage.top_cut_usage)
    output_dir = get_output_dir(tournament_usage.tournament_id)

    ax.set_xlim(AXIS_MIN, AXIS_ZOOMED_IN_MAX)
    ax.set_ylim(AXIS_MIN, AXIS_ZOOMED_IN_MAX)

    plt.get_current_fig_manager().full_screen_toggle()

    plt.savefig(
        f'{output_dir}/{tournament_usage.tournament_name} Zoomed-In.png')

    ax.set_xlim(AXIS_MIN,
                tournament_usage.all_usage[most_used].count / tournament_usage.size + AXIS_MAX_BUFFER)
    ax.set_ylim(AXIS_MIN,
                tournament_usage.top_cut_usage[most_used_in_top_cut].count / tournament_usage.top_cut_size + AXIS_MAX_BUFFER)
    plt.savefig(
        f'{output_dir}/{tournament_usage.tournament_name} Zoomed-Out.png')


def first_key_in_dict(d: dict[str, Any]) -> str:
    return next(iter(d.keys()))


if __name__ == '__main__':
    main()
