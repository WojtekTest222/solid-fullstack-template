# Prerequisite

Ten katalog zawiera kroki wykonywane raz, zanim zaczniesz bootstrapowac kolejne repo z template.

Zalecany entrypoint:
- `bootstrap.py` - lokalny orchestrator spinajacy AWS prerequisite i GitHub prerequisite w jednej komendzie.

- `aws/` - prerequisite po stronie AWS (rola OIDC dla workflow, S3 backend, DynamoDB lock table, bootstrap variables)
- `gh/` - prerequisite po stronie GitHub:
  - `gh/app/` - tworzenie GitHub App,
  - `gh/team/` - zapewnienie teamu administratorow,
  - `gh/bootstrap-gh.py` - lokalny orchestrator spinajacy app + team + GitHub App secrets.

Szybki start:

```ps1
Set-Location terraform/prerequisite

python bootstrap.py `
  --aws-region eu-central-1
```

Jesli pominiesz `--org` albo `--repo`, skrypt sprobuje wziac je z `git remote origin`.
Jesli nie da sie ich ustalic z `.git`, wtedy dopyta interaktywnie.
Jesli pominiesz `--aws-region`, skrypt pokaze menu obslugiwane strzalkami:
- `eu-central-1` (`EU Central / Frankfurt`)
- `us-east-1` (`US East / N. Virginia`)
- `Custom`
Jesli nie ustawisz `AWS_PROFILE` i nie podasz `--aws-profile`, skrypt AWS wyswietli profile znalezione w `~/.aws` i poprosi o wybor strzalkami.
GitHub App jest domyslnie nazywana wedlug konwencji `gha-<pierwsze-20-znakow-org>-<hash6>`.
Ten schemat miesci sie w limicie GitHuba i jest stabilny dla danej organizacji.
Jesli pominiesz `--app-name`, skrypt GitHub najpierw pokaze Appki znalezione w lokalnym `gh/app/out` oraz we wspoldzielonym cache credentials na tym samym komputerze.
Pozwoli wybrac jedna strzalkami albo utworzyc nowa z domyslna nazwa wynikajaca z organizacji.
Przy starcie skrypt probuje tez zsynchronizowac zapisane credentials Appki z AWS SSM Parameter Store (`SecureString`) do lokalnego cache.
Jesli takie zapisane credentials wskazuja Appke, ktora zostala juz usunieta z GitHuba, skrypt pominie je i jasno to zakomunikuje.
Takie stale credentials sa tez automatycznie sprzatane z lokalnego `gh/app/out`, ze wspoldzielonego cache oraz z AWS SSM.
Po wybraniu albo utworzeniu Appki wykonuje upsert jej `app_id` i `private_key_pem` do AWS SSM jako backup/fallback.
W trybie nieinteraktywnym skrypt moze automatycznie zre-uzyc konwencyjna Appke albo jednoznacznie jedyny znaleziony bundle credentials z tych lokalizacji.
Przegladarka dla GitHub App manifest flow otwiera sie automatycznie. Jesli chcesz to wylaczyc, uzyj `--no-open-browser`.
Do org-level variables/secrets/team management potrzebny jest `gh` z zakresem `admin:org`.
Jesli go brakuje, skrypt sprobuje uruchomic `gh auth refresh -h github.com -s admin:org`.

Po wykonaniu prerequisite uruchamiasz `bootstrap-all`.
