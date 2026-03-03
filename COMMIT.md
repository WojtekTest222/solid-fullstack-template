# Commit Convention

Ten dokument definiuje rozszerzona konwencje commit message dla repozytorium.

## Goal

Konwencja ma:
- utrzymac czytelna historie zmian,
- wskazywac, czego dotyczy zmiana (typ + obszar + komponent),
- laczyc commit z branch i taskiem,
- dostarczac krotki changelog w sekcji `Details`.

## Message Format

Uzywaj formatu:

```text
<type1, type2, ...>(<scope1, scope2, ...>): <subject>

Component: <component-name>
BreakingChanges: <YES|NO>
Branch: <branch-name>
Task: <task-reference>

Details:
## <ScopeName>
* <change 1>
* <change 2>
## <AnotherScopeName>
* <change 1>
```

## Rules

1. `type`:
- Mozna podac wiele typow oddzielonych przecinkiem.
- Kolejnosc ma znaczenie: pierwszy typ to najwazniejsza zmiana.
- Typy pisz malymi literami.

2. `scope`:
- Mozna podac wiele scope oddzielonych przecinkiem.
- Scope pisz dokladnie wg slownika z sekcji `Allowed Scope`.
- Kolejnosc: od najbardziej dotknietego obszaru.

3. `subject`:
- 1 zdanie, konkretne, bez kropki na koncu.
- Opisuje efekt biznesowo-techniczny, nie liste plikow.

4. `Component`:
- Krotki motyw zmiany (np. `timer`, `flashcard`, `organizations-ou`).
- Uzywaj kebab-case.

5. `BreakingChanges`:
- Tylko `YES` albo `NO`.
- `YES` gdy zmiana lamie kompatybilnosc API/kontraktu/zachowania.

6. `Branch`:
- Aktualna nazwa brancha, np. `307-custom-timer`.

7. `Task`:
- Referencja zadania, np. `#307 custom timer`.
- Gdy brak taska: `Task: n/a`.

8. `Details`:
- Sekcje grupowane po scope (`## BE.Api`, `## FE.Service`, ...).
- Kazdy punkt zaczynaj od czasownika (np. `Add`, `Refactor`, `Fix`).
- Tylko najwazniejsze rzeczy; bez duplikacji `subject`.

## Allowed Type

- `feat` - nowa funkcjonalnosc
- `fix` - poprawka bledu
- `refactor` - zmiana struktury bez zmiany zachowania
- `perf` - poprawa wydajnosci
- `docs` - dokumentacja
- `test` - testy
- `build` - build/dependency/tooling
- `ci` - pipeline i automatyzacja CI/CD
- `chore` - prace porzadkowe/utrzymaniowe
- `revert` - cofniecie poprzedniego commita

## Allowed Scope

- `BE.Api`
- `BE.Core`
- `BE.Infra`
- `BE.Application`
- `FE.Service`
- `FE.Pages`
- `FE.Components`
- `FE.Shared`
- `TF.Main`
- `TF.Dev`
- `TF.BootstrapOrg`
- `TF.BootstrapIam`
- `Docs`
- `CI`
- `Repo`

## Examples

### Example 1

```text
feat, docs, test(BE.Api, FE.Service): add custom timer flow for study session

Component: timer
BreakingChanges: NO
Branch: 307-custom-timer
Task: #307 custom timer

Details:
## BE.Api
* Add endpoint for timer start/stop with validation
* Add DTOs for timer payload and result
* Add backend integration tests for timer endpoint
## FE.Service
* Add timer API client and mapping for response model
* Add frontend unit tests for timer service
## FE.Pages
* Integrate timer controls on session page
## Docs
* Document timer flow in API usage notes
```

### Example 2

```text
feat, docs(TF.BootstrapOrg, Docs): create initial AWS Organizations OU for app bootstrap

Component: organizations-ou
BreakingChanges: NO
Branch: main
Task: n/a

Details:
## TF.BootstrapOrg
* Add Terraform resource creating OU APP-TODO-LIST under organization root
* Add outputs exposing OU id and arn
## Docs
* Update bootstrap README with SSO-based execution steps
```

## Commit Checklist

Przed commit:
- Czy `type` i `scope` sa poprawne i uporzadkowane po istotnosci?
- Czy `BreakingChanges` jest ustawione poprawnie?
- Czy `Branch` i `Task` sa uzupelnione?
- Czy `Details` zawiera tylko kluczowe zmiany?
- Czy commit jest atomowy (jedna logiczna zmiana)?
