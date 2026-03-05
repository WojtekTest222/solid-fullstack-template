# Agent Working Rules

## Minimal Contracts First

- Do not add new Terraform inputs unless there is a concrete, current caller that needs to set them.
- Do not add new Terraform outputs unless there is a concrete, current consumer that reads them.
- Do not add workflow inputs/outputs "for future use".
- When in doubt, hardcode stable conventions and add configurability later only when a real need appears.
- Keep bootstrap workflows and modules opinionated and minimal; avoid optional switches that increase error surface.
