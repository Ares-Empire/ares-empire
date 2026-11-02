<p align="center">
  <img src="docs/images/banner.png" alt="The Ares Empire hub on the web and in its iPhone app" width="100%">
</p>

# Ares Empire

The hub of the Ares apps: one account for all of them, the push service behind their notifications, and the overview
at **[ares-empire.de](https://www.ares-empire.de)**: every app on a ring, with the chronicle of what was built.

[The apps](https://patrikbreeck.com/en/apps/) · [Their iPhone code](https://github.com/Ares-Empire/empire-ios) ·
[The project map](EMPIRE.md)

## What lives here

| Part | What it is |
|---|---|
| **The hub website** (`web/`) | The apps on a ring that turns, a board for each, the chronicle as a timeline, and the plans. A phone version too. No build step: React and Babel are served from the repository itself. |
| **Accounts** (`accounts/`) | One account for every app, on PocketBase: sign-up, email confirmation, approval, password reset, and access per app. [docs/ACCOUNTS.md](docs/ACCOUNTS.md) |
| **The web server** (`webauth/`) | The login gate, the hub's API, and the legal and contact pages in English and German. Python's standard library only. |
| **Push** (`push/`) | One service that sends every iPhone app's notifications through Apple's push service. [docs/PUSH.md](docs/PUSH.md) |
| **Backups** (`backup/`) | The nightly encrypted backup of the data that cannot be rebuilt. [docs/BACKUP.md](docs/BACKUP.md) |
| **The map** ([`EMPIRE.md`](EMPIRE.md)) | The projects, the shared design language, how the apps are built, and the chronicle. |

## The apps

| App | What it is | Code |
|---|---|---|
| **Aresium** | Personal finance from bank exports | [aresium](https://github.com/Ares-Empire/aresium) |
| **Arestemis** | Searches that run for you: flats, things for sale, prices, pages | iPhone app in [empire-ios](https://github.com/Ares-Empire/empire-ios) |
| **Arestoteles** | A personal knowledge map, searched by meaning | [Arestoteles](https://github.com/Ares-Empire/Arestoteles) |
| **Aresus** | The watchtower over the server, the services and the machines' sync | iPhone app in [empire-ios](https://github.com/Ares-Empire/empire-ios) |
| **Ares Empire** | This hub, and its iPhone app | here, and [empire-ios](https://github.com/Ares-Empire/empire-ios) |

## Screenshots

<table>
  <tr>
    <td><img src="docs/images/app-ring-dark.png" alt="The apps on a ring, the chronicle below"></td>
    <td><img src="docs/images/app-ring-light.png" alt="The same in light mode"></td>
    <td><img src="docs/images/app-province-light.png" alt="One app's page"></td>
    <td><img src="docs/images/app-approvals-dark.png" alt="Approvals of new accounts"></td>
    <td><img src="docs/images/app-more-dark.png" alt="Asking for another app"></td>
  </tr>
</table>

## Design language

Near-black walls, glass cards and faint red and blue light; polished gold only as an accent; Space Grotesk and
JetBrains Mono. Each app has a marble bust of its own and one accent colour. The details are in
[EMPIRE.md](EMPIRE.md) → The crown language.

## Run it locally

```sh
python3 -m http.server 8099 --directory web               # the hub on its bundled data: http://127.0.0.1:8099
python3 -m unittest discover -s webauth -p 'test_*.py'     # the web server's tests
python3 -m unittest tools/test_empire_samples.py           # the sample answers stay current
```

The full server (login, legal pages) and deploying: [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).
