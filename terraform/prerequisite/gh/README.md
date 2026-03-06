# GitHub prerequisite (one-time per org)

Ten krok wykonujesz raz na organizacje GitHub. Tworzy GitHub App, ktora daje workflowom uprawnienia governance na repo.

## 1. Wymagane uprawnienia appki

Repository permissions:
- `Administration: Read and write`
- `Contents: Read and write`
- `Actions: Read and write`
- `Environments: Read and write`
- `Metadata: Read-only`

## 2. Utworzenie appki (semi-auto)

1. Uruchom skrypt:
   ```ps
   Set-Location terraform/prerequisite/gh
   python bootstrap-gh-app-manifest.py `
     --org KnightRadiants `
     --app-name "gha-template-bootstrap" `
     --description "Bootstrap app for template governance" `
     --output-dir "./out" `
     --open-browser
   ```
1. W przegladarce zatwierdz utworzenie appki.
1. Po callbacku skrypt zapisze:
   - `github-app-<APP_ID>.private-key.pem`
   - `github-app-<APP_ID>.credentials.json`
   - i wypisze `Install URL`.
1. Zainstaluj appke na repo, ktore beda bootstrapowane.
1. Jesli zmieniles permissiony appki po instalacji, zaakceptuj `Permission updates requested` w organizacji.

## 3. Sekrety dla workflow

Ustaw Secrets (repo albo org):
- `GH_APP_ID`
- `GH_APP_PRIVATE_KEY` (z pliku PEM)
