# generate-aliases-inputs.py

Script to generate SFCC `aliases` files from a input folder.

## What it does

- Reads site data from `site.xml` and `preferences.xml` under an input folder.
- Generates one file per `siteId` at:
  - `./outputs/alias-input/sites/{{siteId}}/urls/aliases`
- Builds JSON aliases content using:
  - `siteId`, `brandShort`, locales from `SiteLocales`
  - `--format` hostname template (must contain `{{brand}}`)

## Parameters

- `--inputFolder <path>`
  - Optional.
  - Folder containing `sites`, or a parent folder that contains exactly one valid child with `sites`.
  - If omitted, the script asks you to pick a folder in `./inputs` (TTY selection).
- `--outputFolder <path>`
  - Optional.
  - Default: `./outputs`
- `--format <string>`
  - Required.
  - Hostname template, for example: `{{brand}}-dev.bollebrands.com`
- `--alone <string>`
  - Optional.
  - Printed once in console summary.
- `--hub <string>`
  - Optional.
  - Printed once in console summary.

## Console output (once)

The script prints this summary once:

- `outputFolder: {{outputFolder}}`
- `inputFolder: {{inputFolder}}`
- `hub: {{hub}}`
- `alone: {{alone}}`

## Example

```bash
python3 "generate-aliases-inputs.py" --inputFolder "../inputs/dev-alaias-sitemaps-site-desc/" --outputFolder "../outputs" --format "{{brand}}-dev.bollebrands.com"
```
