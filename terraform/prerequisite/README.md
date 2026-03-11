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
- `us-east-1` (`US East / N. Virginia`)
- `eu-central-1` (`EU Central / Frankfurt`)
- `Custom`
Jesli nie ustawisz `AWS_PROFILE` i nie podasz `--aws-profile`, skrypt AWS wyswietli profile znalezione w `~/.aws` i poprosi o wybor strzalkami.
GitHub App jest domyslnie nazywana wedlug konwencji `gha-<pierwsze-20-znakow-org>-<hash6>`.
Ten schemat miesci sie w limicie GitHuba i jest stabilny dla danej organizacji, wiec kolejne uruchomienia moga skipnac tworzenie Appki.
Jesli lokalne credentials dla takiej nazwy juz istnieja w `gh/app/out`, skrypt pominie tworzenie Appki i je zre-uzyje.
Jesli pominiesz `--app-name`, skrypt GitHub pokaze znane lokalnie Appki z `gh/app/out`, pozwoli wybrac jedna strzalkami albo utworzyc nowa z domyslna nazwa wynikajaca z organizacji.
Przegladarka dla GitHub App manifest flow otwiera sie automatycznie. Jesli chcesz to wylaczyc, uzyj `--no-open-browser`.
Do org-level variables/secrets/team management potrzebny jest `gh` z zakresem `admin:org`.
Jesli go brakuje, skrypt sprobuje uruchomic `gh auth refresh -h github.com -s admin:org`.

Po wykonaniu prerequisite uruchamiasz `bootstrap-all`.
