# GitHub prerequisite (one-time per org)

Ten krok wykonujesz raz na organizacje GitHub.

Etap 0 sklada sie z trzech czesci:
- `app/` - tworzenie GitHub App przez manifest flow,
- `team/` - idempotentne zapewnienie teamu `administrators`,
- `bootstrap-gh.py` - lokalny orchestrator, ktory spina oba kroki i od razu ustawia sekrety GitHub App.

## 1. Wymagania

1. Zalogowany `gh` CLI z uprawnieniami administracyjnymi do org/repo:
   ```ps1
   gh auth login
   gh auth status
   ```
1. Uprawnienia do tworzenia GitHub App i zarzadzania teamami/repo variables/secrets.
1. Token `gh` powinien miec zakres `admin:org`:
   ```ps1
   gh auth refresh -h github.com -s admin:org
   ```
   Skrypt sprobuje odpalic ten refresh automatycznie, jesli scope bedzie brakowal.

## 2. Szybki start (zalecane)

```ps1
Set-Location terraform/prerequisite/gh

python bootstrap-gh.py `
  --org KnightRadiants `
  --bootstrap-repo solid-fullstack-template-manual `
  --scope org `
  --app-description "Bootstrap app for template governance"
```

Co zrobi orchestrator:
1. Utworzy GitHub App (albo uzyje istniejacych credentials z `app/out`, jesli juz sa).
1. Zapewni team `administrators` i maintainera.
1. Ustawi:
   - `GH_APP_ID` (secret)
   - `GH_APP_PRIVATE_KEY` (secret)

Przy `--scope org` wartosci sa zapisywane jako org-level i ograniczone do `--bootstrap-repo` (`visibility=selected`).
Nazwa Appki jest domyslnie skladana wedlug konwencji `gha-<pierwsze-20-znakow-org>-<hash6>`.
Ten schemat miesci sie w limicie GitHuba i jest stabilny dla danej organizacji, wiec kolejne uruchomienia moga skipnac tworzenie Appki.
Jesli lokalne credentials dla takiej nazwy juz istnieja w `app/out`, skrypt pominie tworzenie Appki i je zre-uzyje.
Jesli pominiesz `--app-name`, skrypt pokaze Appki znalezione lokalnie w `app/out` dla danej organizacji i pozwoli wybrac jedna strzalkami albo utworzyc nowa z domyslna nazwa wynikajaca z organizacji.
Przegladarka dla manifest flow otwiera sie automatycznie. Jesli chcesz to wylaczyc, uzyj `--no-open-browser`.

Zmienne AWS bootstrapowe ustawia osobno [../aws/bootstrap-aws.py](../aws/bootstrap-aws.py).

## 3. Tryb reczny

- Tylko App: [app/README.md](app/README.md)
- Tylko Team: [team/README.md](team/README.md)

## 4. Instalacja appki

Po utworzeniu appki zainstaluj ja na repo, ktore beda bootstrapowane.
Jesli zmienisz permissiony appki po instalacji, zaakceptuj `Permission updates requested` w organizacji.
