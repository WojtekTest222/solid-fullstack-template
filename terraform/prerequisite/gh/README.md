# GitHub prerequisite (one-time per owner)

Ten krok wykonujesz raz na ownera GitHub.

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
1. Przy ownerze typu `Organization` token `gh` powinien miec zakres `admin:org`:
   ```ps1
   gh auth refresh -h github.com -s admin:org
   ```
   Skrypt sprobuje odpalic ten refresh automatycznie, jesli scope bedzie brakowal.
   Przy ownerze typu `User` skrypt przechodzi na repo-level secrets i pomija bootstrap teamu.

## 2. Szybki start (zalecane)

```ps1
Set-Location terraform/prerequisite/gh

python bootstrap-gh.py `
  --org KnightRadiants `
  --bootstrap-repo solid-fullstack-template-manual `
  --scope org `
  --aws-region eu-central-1 `
  --app-description "Bootstrap app for template governance"
```

Co zrobi orchestrator:
1. Utworzy GitHub App (albo uzyje istniejacych credentials z `app/out`, ze wspoldzielonego cache na tym samym komputerze albo z AWS SSM Parameter Store, jesli juz sa).
1. Zapewni team `administrators` i maintainera.
1. Ustawi:
   - `GH_APP_ID` (secret)
   - `GH_APP_PRIVATE_KEY` (secret)

Przy `--scope org` i ownerze typu `Organization` wartosci sa zapisywane jako org-level i ograniczone do `--bootstrap-repo` (`visibility=selected`).
Przy ownerze typu `User` skrypt automatycznie wymusza repo-level secrets.
Nazwa Appki jest domyslnie skladana wedlug konwencji `gha-<pierwsze-20-znakow-ownera>-<hash6>`.
Ten schemat miesci sie w limicie GitHuba i jest stabilny dla danego ownera.
Jesli pominiesz `--app-name`, skrypt najpierw pokaze Appki znalezione w `app/out` oraz we wspoldzielonym cache credentials dla danego ownera i pozwoli wybrac jedna strzalkami albo utworzyc nowa z domyslna nazwa wynikajaca z ownera.
Przy starcie skrypt probuje zsynchronizowac zapisane credentials Appki z AWS SSM Parameter Store (`SecureString`) do lokalnego cache.
Jesli zapisane credentials wskazuja Appke, ktora zostala juz usunieta z GitHuba, skrypt pominie je i nie zaproponuje ich do reuse.
Takie stale credentials sa tez automatycznie sprzatane z `app/out`, ze wspoldzielonego cache oraz z AWS SSM.
Po wybraniu albo utworzeniu Appki wykonuje upsert jej `app_id` i `private_key_pem` do AWS SSM jako backup/fallback.
Jesli Appka nie jest jeszcze zainstalowana u ownera albo instalacja uzywa `selected repositories`, skrypt poda link do instalacji/konfiguracji, moze otworzyc przegladarke i poprosi o potwierdzenie konfiguracji dla `--bootstrap-repo`.
W trybie nieinteraktywnym skrypt moze automatycznie zre-uzyc konwencyjna Appke albo jednoznacznie jedyny znaleziony bundle credentials z tych lokalizacji.
Przegladarka dla manifest flow otwiera sie automatycznie. Jesli chcesz to wylaczyc, uzyj `--no-open-browser`.

Zmienne AWS bootstrapowe ustawia osobno [../aws/bootstrap-aws.py](../aws/bootstrap-aws.py).

## 3. Tryb reczny

- Tylko App: [app/README.md](app/README.md)
- Tylko Team: [team/README.md](team/README.md)

## 4. Instalacja appki

Po utworzeniu appki zainstaluj ja na repo, ktore beda bootstrapowane.
Jesli zmienisz permissiony appki po instalacji i ownerem jest organizacja, zaakceptuj `Permission updates requested` w organizacji.
