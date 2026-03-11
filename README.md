<p align="center">
  <img src=".github/banner.png" alt="CTFdParser" width="860"/>
</p>

<p align="center">
  A python tool to dump and manage challenges from any CTFd-based Capture the Flag.
  <br><br>
  <img alt="Python" src="https://img.shields.io/badge/python-3.10%2B-blue?style=flat-square&logo=python&logoColor=white">
  <img alt="License" src="https://img.shields.io/badge/license-MIT-green?style=flat-square">
  <img alt="Version" src="https://img.shields.io/badge/version-2.0-brightgreen?style=flat-square">
  <a href="https://twitter.com/intent/follow?screen_name=hetsonii">
    <img alt="Twitter Follow" src="https://img.shields.io/twitter/follow/hetsonii?style=social">
  </a>
</p>

---

## Features

- [x] Three auth methods — API token, session cookie, username + password
- [x] Lists all unsolved challenges sorted by solve count
- [x] Downloads challenge files into a `Category / Challenge / files` tree
- [x] Auto-generates a `README.md` per challenge (description, points, connection info)
- [x] Auto-refresh live report during an active CTF
- [x] Dumps scoreboard, teams, users, and per-team solves to JSON
- [x] Retry with exponential backoff on flaky connections

## Usage

```
$ python ctfd.py -h

       _____ _______ ______  _   _____
      / ____|__   __|  ____|| | |  __ \
     | |       | |  | |__ __| | | |__) |_ _ _ __ ___  ___ _ __
     | |       | |  |  __/ _` | |  ___/ _` | '__/ __|/ _ \ '__|
     | |____   | |  | | | (_| | | |  | (_| | |  \__ \  __/ |
      \_____|  |_|  |_|  \__,_| |_|   \__,_|_|  |___/\___|_|

usage: ctfd.py [-h] [-U URL] [-k TOKEN] [-c COOKIE] [-u USER] [-p PASS]
               [-o DIR] [-T N]
               {list,report,download,dump} ...

commands:
  list        Print unsolved challenges sorted by solve count
  report      Auto-refreshing unsolved challenge table
  download    Download challenge files to disk
  dump        Dump challenges, teams, users, scoreboard to JSON

authentication:
  -U, --url     CTFd base URL
  -k, --token   API token
  -c, --cookie  Session cookie value
  -u, --user    Username
  -p, --pass    Password

optional:
  -o, --output  Output directory  (default: ./ctfd_output)
  -T, --threads Worker threads    (default: 8)
```

Run without arguments for interactive mode:

```
$ python ctfd.py
```

## Installation

```bash
git clone https://github.com/hetsonii/ctfd-parser
cd ctfd-parser
pip install -r requirements.txt
```

## Examples

```bash
# List unsolved challenges
python ctfd.py --url https://ctf.example.com --token TOKEN list

# Download only unsolved challenges, skip files > 50 MB
python ctfd.py --url https://ctf.example.com --token TOKEN download --only-unsolved --max-mb 50

# Live report, refreshes every 30 seconds
python ctfd.py --url https://ctf.example.com -u user -p pass report --interval 30

# Dump everything to JSON
python ctfd.py --url https://ctf.example.com --cookie SESSION dump
```

## Contributors

Pull requests are welcome. Feel free to open an issue if you want to add other features.