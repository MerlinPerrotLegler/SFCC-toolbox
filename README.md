# SFCC Toolbox

Collection d'outils pour faciliter le travail quotidien avec **Salesforce Commerce Cloud (SFCC)**.

## Contenu

| Dossier | Description |
|---|---|
| [01-import-for-sb](./01-import-for-sb/) | Préparation d'exports SFCC pour Sandbox |
| [02-aliases-generation](./02-aliases-generation/) | Génération de fichiers `aliases` |
| [99-export-zipper](./99-export-zipper/) | Packaging ZIP des exports en sortie |
| [tampermonkey](./tampermonkey/) | Scripts Tampermonkey pour le Business Manager |

## Prérequis

- Python 3.x (pour les scripts du dossier Site Import)
- Extension navigateur [Tampermonkey](https://www.tampermonkey.net/) (pour les scripts BM)

## Exécution unifiée

```bash
npm run build
```

Le workflow unifié utilise les dossiers `#INPUTS` et `#OUTPUTS`.

---

*D'autres outils seront ajoutés au fil du temps.*
