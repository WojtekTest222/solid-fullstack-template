# 1. GitHub Prerequisite (One-Time, Per Org)

Ten katalog opisuje jednorazowy prerequisite po stronie GitHub Organization.
To nie jest krok per-repo. Robisz go raz, a potem korzystaja z niego wszystkie repo tworzone z template.

Cel:
- utworzyc GitHub App do operacji governance wymagajacych uprawnienia administracyjnego repo (np. zmiana `default_branch`),
- zapisac dane appki jako org/repo secrets dla workflow.

## 1.1. Dlaczego to jest pólautomatyczne

Utworzenie GitHub App opiera sie o manifest flow i wymaga kroku w przegladarce (redirect + code exchange).
To oznacza, ze mozna to zautomatyzowac tylko czesciowo skryptem.

## 1.2. Wymagane uprawnienia GitHub App

Minimalny zestaw (Repository permissions):
- `Administration: Read & write`
- `Contents: Read & write`
- `Actions: Read & write`
- `Environments: Read & write`

Jesli appka zostala utworzona wczesniej bez `Environments: Read & write`, edytuj uprawnienia appki i zaakceptuj update instalacji w organizacji.

## 1.3. One-time setup

1. Uruchom skrypt półautomatyczny (manifest flow):
    ```ps
    Set-Location terraform/prerequisite/gh
    python bootstrap-gh-app-manifest.py `
      --org KnightRadiants `
      --app-name "gha-template-bootstrap" `
      --description "Bootstrap app for template governance" `
      --output-dir "./out" `
      --open-browser
    ```
1. W przegladarce zatwierdz utworzenie appki (to jest wymagany krok manualny).
    - Skrypt uruchamia lokalny endpoint `http://127.0.0.1:<port>/start`, ktory wysyla `POST` z `manifest` do GitHub.
    - Nie otwieraj "golego" URL `/settings/apps/new` bez manifestu.
1. Po callbacku skrypt zapisze pliki:
    - `github-app-<APP_ID>.private-key.pem`
    - `github-app-<APP_ID>.credentials.json`
    - i wypisze bezposredni `Install URL` do appki (wyrózniony kolorem zielonym).
1. Zainstaluj appke na repo, ktore maja byc bootstrapowane.
1. Zapisz sekrety:
   - `GH_APP_ID`
   - `GH_APP_PRIVATE_KEY` (PEM)
