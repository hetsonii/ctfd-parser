#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# File name          : ctfd_parser.py
# Author             : Podalirius (@podalirius_)
# Last Update        : 28 December 2023

import json
import time
import requests
import re
import os
import io
import sys
from concurrent.futures import ThreadPoolExecutor
from getpass import getpass
import shutil
import threading

ROOT = os.path.dirname(__file__)

FILE_MAX_SIZE_MO = 100 

def os_filename_sanitize(s:str) -> str:
    filtred = ['/', ';', ' ', ':']
    for char in filtred:
        s = s.replace(char, '_')
    s = re.sub('__*', '_', s)
    return s

class CTFdParser(object):

    def __init__(self:object, target:str, login:str=None, password:str=None, basedir:str="Challenges", initfile:str=False, token:str=None) -> None:
        super(CTFdParser, self).__init__()
        self.target = target
        self.basedir = basedir
        self.initfile = initfile
        self.challenges = {}
        self.token = token
        self.credentials = {
            'user': login,
            'password': password
        }
        self.session = requests.Session()
        
        self.psolve = os.path.join(ROOT, "template", "solve.py")
        self.pwu = os.path.join(ROOT, "template", "writeup.md")

    def login(self:object) -> bool:
        if self.token:
            self.session.headers.update({'Authorization': f'Token {self.token}'})
            r = self.session.get(self.target + '/api/v1/challenges')
            return r.status_code == 200

        r = self.session.get(self.target + '/login')
        matched = re.search(
            b"""('csrfNonce':[ \t]+"([a-f0-9A-F]+))""", r.content)
        nonce = ""
        if matched is not None:
            nonce = matched.groups()[1]
        r = self.session.post(
            self.target + '/login',
            data={
                'name': self.credentials['user'],
                'password': self.credentials['password'],
                '_submit': 'Submit',
                'nonce': nonce.decode('UTF-8')
            }
        )

        return 'Your username or password is incorrect' not in r.text

    def get_report(self:object, threads:int=8) -> None:
        self._report_timer = threading.Timer(60.0, self.get_report, args=[threads])
        self._report_timer.start()
        self.get_challenges(threads, parse=False)
        unsolved_challenges = {}

        for index in range(len(self.challenges)):
            chall = self.challenges[index]
            if(not chall['solved_by_me']):
                unsolved_challenges[index] = chall['solves']

        unsolved_challenges = {k: v for k, v in sorted(unsolved_challenges.items(), key=lambda item: item[1],reverse=True)}

        print("\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n")
        print("-"*30 + "Chall Report" + "-"*30)
        for index in unsolved_challenges:
            chall = self.challenges[index]
            name = chall['name']
            points = chall['value']
            cat = chall['category']
            solves = chall['solves']

            print(f"Challenge {name:>20} | Solves {solves:>3} | {cat:>20} | Points {points:>4} ")
        print("-"*30 + "------------" + "-"*30)


    def get_challenges(self:object, threads:int=8, parse:bool=True) -> dict:
        r = self.session.get(self.target + "/api/v1/challenges")

        if r.status_code == 200:
            if not r.content or not r.content.strip():
                print("[warn] /api/v1/challenges returned an empty response — challenges may not be available yet.")
                return None
            try:
                json_challs = json.loads(r.content)
            except json.JSONDecodeError:
                print("[warn] /api/v1/challenges returned invalid JSON — challenges may not be available yet.")
                return None
            if json_challs is not None:
                if json_challs['success']:
                    self.challenges = json_challs['data']
                    if(parse): self._parse(threads=threads)
                else:
                    print("[warn] An error occurred while requesting /api/v1/challenges")
            return json_challs
        else:
            return None

    def _parse(self:object, threads:int=8) -> None:
        # Categories
        self.categories = [chall["category"] for chall in self.challenges]
        self.categories = sorted(list(set(self.categories)))

        print(f'\x1b[1m[\x1b[93m+\x1b[0m\x1b[1m]\x1b[0m Found {len(self.categories)} categories !')

        # Parsing challenges
        for category in self.categories:
            print(f"\x1b[1m[\x1b[93m>\x1b[0m\x1b[1m]\x1b[0m Parsing challenges of category : \x1b[95m{category}\x1b[0m")

            challs_of_category = [c for c in self.challenges if c['category'] == category]

            # Waits for all the threads to be completed
            with ThreadPoolExecutor(max_workers=min(threads, len(challs_of_category))) as tp:
                for challenge in challs_of_category:
                    tp.submit(self.dump_challenge, category, challenge)

    def dump_challenge(self:object, category:str, challenge:dict)->None:
        if challenge["solved_by_me"]:
            print(f"   \x1b[1m[\x1b[93m>\x1b[0m\x1b[1m]\x1b[0m \x1b[1;92m✅\x1b[0m \x1b[96m{challenge['name']}\x1b[0m")
        else:
            print(f"   \x1b[1m[\x1b[93m>\x1b[0m\x1b[1m]\x1b[0m \x1b[1;91m❌\x1b[0m \x1b[96m{challenge['name']}\x1b[0m")

        folder = os.path.sep.join([self.basedir, os_filename_sanitize(category), os_filename_sanitize(challenge["name"])])
        if not os.path.exists(folder):
            os.makedirs(folder)
            
        #template files
        
        if self.initfile:
            shutil.copy(self.psolve, folder)
            shutil.copy(self.pwu, folder)

        # Readme.md
        f = open(folder + os.path.sep + "README.md", 'w')
        f.write(f"# {challenge['name']}\n\n")
        f.write(f"**Category** : {challenge['category']}\n")
        f.write(f"**Points** : {challenge['value']}\n\n")

        chall_json = self.get_challenge_by_id(challenge["id"])["data"]
        f.write(f"{chall_json['description']}\n\n")

        connection_info = chall_json["connection_info"]
        if connection_info is not None:
            if len(connection_info) != 0:
                f.write(f"{connection_info}\n\n")

        # Get challenge files
        if len(chall_json["files"]) != 0:
            f.write("## Files : \n")
            for file_url in chall_json["files"]:
                if "?" in file_url:
                    filename = os.path.basename(file_url.split('?')[0])
                else:
                    filename = os.path.basename(file_url)

                r = self.session.head(self.target + file_url, allow_redirects=True)
                if "Content-Length" in r.headers.keys():
                    size = int(r.headers["Content-Length"])
                    if size < (FILE_MAX_SIZE_MO * 1024 * 1024):  # 50 Mb
                        r = self.session.get(self.target + file_url, stream=True)
                        with open(folder + os.path.sep + filename, "wb") as fdl:
                            for chunk in r.iter_content(chunk_size=16 * 1024):
                                fdl.write(chunk)
                    else:
                        print(f"Not Downloading {filename}, filesize too big.")

                else:
                    r = self.session.get(self.target + file_url, stream=True)
                    with open(folder + os.path.sep + filename, "wb") as fdl:
                        for chunk in r.iter_content(chunk_size=16 * 1024):
                            fdl.write(chunk)

                f.write(f" - [{filename}](./{filename})\n")

        f.write("\n\n")
        f.close()

    def get_challenge_by_id(self:object, chall_id:int) -> dict:
        """Documentation for get_challenge_by_id"""
        r = self.session.get(self.target + f'/api/v1/challenges/{chall_id}')
        json_chall = None
        if r.status_code == 200 and r.content and r.content.strip():
            try:
                json_chall = json.loads(r.content)
            except json.JSONDecodeError:
                pass
        return json_chall

    def get_json(self:object, url:str):
        rdata = None
        r = self.session.get(self.target + url)
        if r.status_code == 200:
            rdata = json.loads(r.content)
        else:
            print(f'HTTP STATUS: {r.status_code}', file=sys.stderr)
            print(r.content.decode('UTF-8'), file=sys.stderr)
            raise RuntimeError('Something went wrong :(')
        return rdata

    def write_json(self:object, folder:str, filename:str, data):
        with io.open(folder + os.path.sep + filename, 'w', encoding='utf-8') as f:
            f.write(json.dumps(data, ensure_ascii=False))

    def dump_challenges(self:object, folder:str) -> None:
        challenges = self.get_json(f'/api/v1/challenges')['data']
        self.write_json(folder, 'challenges.json', challenges)

    def dump_teams(self:object, folder:str) -> list:
        next_page = 1
        teams = []
        while next_page != None:
            rdata = self.get_json(f'/api/v1/teams?page={next_page}')
            next_page = rdata['meta']['pagination']['next']
            teams += rdata['data']

        self.write_json(folder, 'teams.json', teams)
        return teams

    def dump_users(self:object, folder:str) -> list:
        next_page = 1
        users = []
        while next_page != None:
            rdata = self.get_json(f'/api/v1/users?page={next_page}')
            next_page = rdata['meta']['pagination']['next']
            users += rdata['data']

        self.write_json(folder, 'users.json', users)
        return users

    def dump_scoreboard(self:object, folder:str) -> None:
        scoreboard = self.get_json(f'/api/v1/scoreboard')['data']
        self.write_json(folder, 'scoreboard.json', scoreboard)
        scoreboard_detailed = self.get_json(f'/api/v1/scoreboard/top/1000000')['data']
        self.write_json(folder, 'scoreboard_detailed.json', scoreboard_detailed)
        scoreboard_split = self.get_json(f'/api/v1/split_scores/top/1000000')['data']
        self.write_json(folder, 'scoreboard_split.json', scoreboard_split)

    def dump_team_solves(self:object, folder:str, teams:list) -> None:
        team_solves = {}
        for team in teams:
            team_solves[team['id']] = self.get_json(f'/api/v1/teams/{team["id"]}/solves')['data']

        self.write_json(folder, 'team_solves.json', team_solves)

    def invoke_command(self:object, threads:int, dump:bool, report:bool) -> None:
        if report:
            self.get_report(threads)
        elif dump:
            folder = os.path.sep.join([self.basedir, 'Data'])
            if not os.path.exists(folder):
                os.makedirs(folder)

            self.dump_challenges(folder)
            teams = self.dump_teams(folder)
            users = self.dump_users(folder)
            try:
                self.dump_scoreboard(folder)
            except RuntimeError as e:
                print(e, file=sys.stderr)

            try:
                self.dump_team_solves(folder, teams)
            except RuntimeError as e:
                print(e, file=sys.stderr)
        else:
            self.get_challenges(threads)


def header() -> None:
    print(r"""       _____ _______ ______  _   _____
      / ____|__   __|  ____|| | |  __ \
     | |       | |  | |__ __| | | |__) |_ _ _ __ ___  ___ _ __
     | |       | |  |  __/ _` | |  ___/ _` | '__/ __|/ _ \ '__|    v1.1
     | |____   | |  | | | (_| | | |  | (_| | |  \__ \  __/ |
      \_____|  |_|  |_|  \__,_| |_|   \__,_|_|  |___/\___|_|       @podalirius_
""")


def prompt_credentials() -> tuple:
    """Interactively ask for CTF URL and auth method (password or token)."""
    while True:
        url = input("CTF website URL: ").strip().rstrip('/')
        if not url:
            print("[!] URL cannot be empty.")
            continue
        if not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url
        break

    print()
    print("  Auth method:")
    print("  [1] Username + Password")
    print("  [2] Access token")
    while True:
        auth_choice = input("Choice [1/2]: ").strip()
        if auth_choice in ("1", "2"):
            break
        print("[!] Please enter 1 or 2.")

    if auth_choice == "2":
        while True:
            token = getpass("Access token: ")
            if token:
                break
            print("[!] Token cannot be empty.")
        return url, None, None, token

    while True:
        user = input("Username: ").strip()
        if not user:
            print("[!] Username cannot be empty.")
            continue
        break

    password = getpass("Password: ")
    return url, user, password, None


def prompt_menu(cp: CTFdParser) -> None:
    """Main interactive menu loop."""
    default_output = os.path.join(os.getcwd(), "challs")

    while True:
        print()
        print("=" * 40)
        print("  What would you like to do?")
        print("  [1] Dump all challenges")
        print("  [2] Timely report (refreshes every 60s)")
        print("  [3] Exit")
        print("=" * 40)
        choice = input("Choice: ").strip()

        if choice == "1":
            path_input = input(f"Output path [{default_output}]: ").strip()
            output = path_input if path_input else default_output
            cp.basedir = output
            print(f"[>] Dumping challenges to: {output}")
            cp.get_challenges(threads=8)
            print("[+] Done! Returning to menu.\n")

        elif choice == "2":
            print("[>] Starting timely report. Press Ctrl-C to stop and return to menu.")
            try:
                cp.get_report(threads=8)
                # Block until interrupted; the timer fires every 60 s on its own
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                timer = getattr(cp, '_report_timer', None)
                if timer is not None:
                    timer.cancel()
                print("\n[+] Report stopped. Returning to menu.")

        elif choice == "3":
            print("Bye!")
            break

        else:
            print("[!] Invalid choice, please enter 1, 2, or 3.")


def main() -> int:
    header()
    url, user, password, token = prompt_credentials()

    cp = CTFdParser(url, user, password, token=token)
    print("[>] Logging in...")
    if not cp.login():
        print("[-] Login failed. Check your credentials.")
        return -1
    print("[+] Logged in successfully!")

    prompt_menu(cp)
    return 0


if __name__ == '__main__':
    main()

