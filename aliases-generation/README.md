# generate-aliases-inputs.py

Script to generate SFCC `aliases` files from a site-import folder.

## What it does

- Reads site data from `site.xml` and `preferences.xml` under an input folder.
- Generates one file per `siteId` at:
  - `./site-exports/alias-site-import/sites/{{siteId}}/urls/aliases`
- Builds JSON aliases content using:
  - `siteId`, `brandShort`, locales from `SiteLocales`
  - `--format` hostname template (must contain `{{brand}}`)

## Parameters

- `--inputFolder <path>`
  - Optional.
  - Folder containing `sites`, or a parent folder that contains exactly one valid child with `sites`.
  - If omitted, the script asks you to pick a folder in `./site-imports` (TTY selection).
- `--outputFolder <path>`
  - Optional.
  - Default: `./site-exports`
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
python3 "generate-aliases-inputs.py" --inputFolder "../site-imports/dev-alaias-sitemaps-site-desc/" --outputFolder "../site-exports" --format "{{brand}}-dev.bollebrands.com"
```
