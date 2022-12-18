from bs4 import BeautifulSoup, ResultSet
from io import TextIOWrapper
from os import makedirs
from os.path import basename, dirname, exists, relpath
import requests
from time import sleep


FILE_DOWNLOAD_SLEEP_TIME = 0.5
LIMITLESS_BASE_URL = 'https://play.limitlesstcg.com'


def main() -> None:
    file_path = ask_file_path()
    parsed_html = parse_html(file_path)
    teamsheet_urls = get_teamsheet_urls(parsed_html)
    download_teamsheets(teamsheet_urls)
    teams = get_teams(parsed_html)
    top_sixteen_teams = teams[0:16]
    pokemon = get_pokemon_from_teams(teams)
    top_sixteen_pokemon = get_pokemon_from_teams(top_sixteen_teams)
    pokemon_usage = get_pokemon_usage(pokemon)
    top_sixteen_usage = get_pokemon_usage(top_sixteen_pokemon)
    ordered_pokemon_usage = order_pokemon_by_usage(pokemon_usage)
    ordered_top_sixteen_usage = order_pokemon_by_usage(top_sixteen_usage)
    write_ordered_pokemon_usage_to_file(
        file_path, len(teams), ordered_pokemon_usage, ordered_top_sixteen_usage)


def ask_file_path() -> str:
    return input('Enter Limitless Tournament HTM(L) file to parse:')


def parse_html(file_path: str) -> BeautifulSoup:
    with open(file_path, 'r', encoding='utf-8') as html:
        return BeautifulSoup(html, 'html.parser')


def get_teams(parsed_html: BeautifulSoup) -> ResultSet:
    return [td
            for td in parsed_html.find_all('td')
            if td.has_attr('class')
            and td['class'][0] == 'vgc-team']


def get_teamsheet_urls(parsed_html: BeautifulSoup) -> list[str]:
    return [a['href']
            for a in parsed_html.find_all('a')
            if a.has_attr('href')
            and a['href'].endswith('teamlist')]


def download_teamsheets(teamsheet_urls: list[str]) -> None:
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
