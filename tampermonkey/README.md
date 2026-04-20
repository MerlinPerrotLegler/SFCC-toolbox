# Tampermonkey

Scripts [Tampermonkey](https://www.tampermonkey.net/) à injecter dans le **Business Manager (BM)** ou le **Storefront** de SFCC pour enrichir l'interface et faciliter son utilisation au quotidien.

## Installation

### Prérequis

Installer l'extension **[Tampermonkey](https://www.tampermonkey.net/)** dans votre navigateur.

---

### Option A — Via Git (recommandé)

Permet de bénéficier des mises à jour en faisant simplement un `git pull`.

1. Cloner le dépôt :
   ```bash
   git clone https://github.com/votre-org/sfcc-toolbox.git
   ```

2. Créer son fichier de credentials (voir section [Credentials](#credentials-identifiants) ci-dessous).

3. Glisser-déposer les deux fichiers suivants dans Tampermonkey (ou via **Utilitaires → Importer**) :
   - `SF-autologin.credentials.js` en premier
   - `SF-autologin.user.js` ensuite

> Pour récupérer les mises à jour : `git pull` puis mettre à jour `credentials.js` si nécessaire.

---

### Option B — Copier-coller manuel

1. Ouvrir le tableau de bord Tampermonkey → **Créer un nouveau script**.
2. Copier-coller le contenu de `SF-autologin.credentials.js` et sauvegarder.
3. Créer un second script avec le contenu de `SF-autologin.user.js` et sauvegarder.

---

## Credentials (identifiants)

Les mots de passe sont isolés dans un fichier séparé **non versionné** :

| Fichier | Rôle |
|---|---|
| `SF-autologin.credentials.example.js` | Template versionné — structure à suivre |
| `SF-autologin.credentials.js` | Fichier réel avec les mots de passe — **gitignore**, à créer localement |

**Première utilisation :**
```bash
cp tampermonkey/SF-autologin.credentials.example.js tampermonkey/SF-autologin.credentials.js
# puis éditer credentials.js avec les vrais mots de passe
```

Les deux scripts utilisent `@grant none` : ils s'exécutent directement dans le contexte de la page et partagent `window`. `credentials.js` pose `window.__sfcc_creds` au `document-start`, et `user.js` le lit immédiatement après.

> **Ordre d'installation important** : `credentials.js` doit avoir un numéro de script inférieur à `user.js` dans Tampermonkey (installer credentials.js en premier). Cela garantit qu'il s'exécute avant user.js.

---

## Scripts disponibles

### `SF-autologin.user.js`

Remplit automatiquement les formulaires de connexion (username + mot de passe) sur les storefronts SFCC, qu'ils apparaissent au chargement de la page ou de façon dynamique (modales, dialogs).

**Configuration dans `SF-autologin.credentials.js` :**

| Champ | Description |
|---|---|
| `hosts` | Liste de hostnames directs (ex: `monsite-staging.example.com`) |
| `sites` | Fragments de chemin sur `*.commercecloud.salesforce.com` (ex: `Sites-MonSite_`) |
| `username` | Optionnel — `storefront` utilisé par défaut si absent |
| `password` | Mot de passe |

**`AUTO_SUBMIT`** dans `SF-autologin.user.js` : mettre à `true` pour cliquer automatiquement sur le bouton de connexion.

**URLs couvertes :** toutes les URLs `https://` — le script ne s'active que si la page correspond à une entrée dans `credentials.js`.
