# Prerequisite

Ten katalog zawiera kroki wykonywane raz, zanim zaczniesz bootstrapowac kolejne repo z template.

- `aws/` - prerequisite po stronie AWS (rola OIDC dla workflow, S3 backend, DynamoDB lock table)
- `gh/` - prerequisite po stronie GitHub (GitHub App do operacji governance)

Po wykonaniu obu krokow ustawiasz Variables/Secrets i uruchamiasz `bootstrap-all`.
