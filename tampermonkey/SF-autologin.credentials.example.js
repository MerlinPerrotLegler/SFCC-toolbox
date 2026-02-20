// ==UserScript==
// @name         SFCC – Auto Login – Credentials
// @namespace    sfcc-toolbox
// @version      1.0
// @description  Credentials pour SF-autologin — copier en SF-autologin.credentials.js et renseigner
// @match        https://*
// @grant        none
// @run-at       document-start
// @autor        [Merlin Perrot](merlin.perrot.pro@gmail.com)
// ==/UserScript==

// Doit être installé dans Tampermonkey AVANT SF-autologin.user.js

window.__sfcc_creds = [
    // Exemple avec hostname direct + site SFCC
    {
        hosts: [
            'monsite-staging.example.com',
            'monsite-dev.example.com',
        ],
        sites: [
            'Sites-MonSite_',
        ],
        password: 'mon-mot-de-passe',
    },

    // Exemple avec site SFCC uniquement (sandbox *.dx.commercecloud.salesforce.com)
    {
        sites: [
            'Sites-AutreSite_',
        ],
        password: 'autre-mot-de-passe',
    },

    // Exemple avec username personnalisé (DEFAULT_USERNAME = 'storefront' sinon)
    // {
    //     hosts: ['special.example.com'],
    //     username: 'admin',
    //     password: 'mot-de-passe-special',
    // },
];
