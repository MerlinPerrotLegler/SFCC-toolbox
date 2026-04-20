# Site Import

Scripts de traitement des exports de site SFCC pour préparer leur import sur un **sandbox** depuis un environnement de **staging**.

## Scripts disponibles

### `transform-site-export-for-sandbox.py`

Transforme le contenu d'un dossier d'export de site SFCC pour le rendre compatible avec un environnement sandbox. Il parcourt récursivement tous les fichiers et applique les transformations suivantes :

| Transformation | Fichiers concernés | Détail |
|---|---|---|
| Copie staging → development | Tous les `*.xml` (hors exclusions) | Le contenu de la balise `<staging>` remplace celui de `<development>` |
| Désactivation des jobs | `jobs.xml` (partout) | `run-recurring enabled="true"` → `false` |
| Réinitialisation des alias URL | `sites/**/urls/aliases` | Remplacé par `{}` |
| Suppression des timestamps d'inventaire | `inventory-lists/inventory*.xml` | Supprime les balises `<allocation-timestamp>` |
| Désactivation du cache | `sites/**/cache-settings.xml` | `static-cache-ttl=0` et `page-cache-enabled=false` sous `<development>` |
| External location du master catalog | `catalogs/**/catalog.xml` | Configure `<header><image-settings><external-location>` avec `Sites-<catalog-id>` |
| Nettoyage des fichiers temporaires | `._*`, `__MACOSX/`, `Thumbs.db`… | Supprime les artefacts macOS et Windows |

**Dossiers exclus** de la transformation staging → development : `custom-objects`, `pricebooks`, `customer-lists`, `libraries`.

## Utilisation

1. Extraire le zip d'export de site SFCC dans un dossier local.
2. Exécuter le script en passant ce dossier en argument :

```bash
python transform-site-export-for-sandbox.py <chemin_vers_le_dossier>
```

**Exemple :**

```bash
python transform-site-export-for-sandbox.py ~/Downloads/site-export
```

3. Re-zipper le dossier traité et l'importer via le Business Manager.

## Prérequis

- Python 3.x
- Aucune dépendance externe (bibliothèques standard uniquement)
