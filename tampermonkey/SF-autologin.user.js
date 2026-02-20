// ==UserScript==
// @name         SFCC – Auto Login Storefront
// @namespace    sfcc-toolbox
// @version      1.0
// @description  Remplit automatiquement les formulaires de connexion sur les storefronts SFCC
// @match        https://*
// @grant        none
// @run-at       document-start
// @autor        [Merlin Perrot](merlin.perrot.pro@gmail.com)
// ==/UserScript==

(function () {
    'use strict';

    // ── Configuration ──────────────────────────────────────────────────────────
    // Les identifiants sont définis dans SF-autologin.credentials.js (gitignore).
    // Ce script doit être installé APRÈS credentials.js dans Tampermonkey
    // pour que window.__sfcc_creds soit disponible.
    //
    // Format de chaque entrée dans SF-autologin.credentials.js :
    //   hosts    : liste de hostnames directs
    //   sites    : liste de fragments de chemin (sur *.commercecloud.salesforce.com uniquement)
    //   username : optionnel — DEFAULT_USERNAME ('storefront') utilisé si absent
    //   password : mot de passe
    //
    const DEFAULT_USERNAME = 'storefront';

    // Lecture des credentials posés par credentials.js sur window
    // (@grant none → les deux scripts partagent le même window de page)
    const CREDENTIALS = window.__sfcc_creds || [];

    // Mettre à true pour cliquer automatiquement sur le bouton de connexion (formulaires HTML)
    const AUTO_SUBMIT = false;
    // ──────────────────────────────────────────────────────────────────────────

    function getCreds() {
        const hostname = location.hostname;
        const pathname = location.pathname;
        const isSFCC   = hostname.endsWith('.commercecloud.salesforce.com') || hostname.endsWith('.demandware.net');

        const normalizeHost = h => h.replace(/^https?:\/\//, '').replace(/\/$/, '');
        const matchHost     = c => c.hosts?.some(h => hostname === normalizeHost(h));
        const matchSite     = c => isSFCC && c.sites?.some(s => pathname.includes(s));

        return CREDENTIALS.find(c => matchHost(c) || matchSite(c)) || null;
    }

    // ── HTTP Basic Auth ────────────────────────────────────────────────────────
    // La boîte Basic Auth est native au navigateur : JS ne peut pas la remplir.
    // Solution : rediriger vers https://user:pass@host/path avant qu'elle apparaisse.
    // Le navigateur envoie alors les credentials automatiquement et met en cache
    // l'authentification pour toute la session → plus de boîte de dialogue.
    //
    // sessionStorage persiste dans le même onglet entre les navigations :
    // on ne redirige qu'une seule fois par onglet (évite la boucle infinie).

    const BASIC_AUTH_KEY = 'sfcc_tm_basic_auth';

    const creds = getCreds();
    if (creds && !sessionStorage.getItem(BASIC_AUTH_KEY)) {
        sessionStorage.setItem(BASIC_AUTH_KEY, '1');
        const url    = new URL(location.href);
        url.username = creds.username || DEFAULT_USERNAME;
        url.password = creds.password;
        location.replace(url.href);
        return; // arrêt — la page va se recharger avec les credentials
    }

    // ── Formulaires HTML (modales, dialogs) ────────────────────────────────────
    // Pour les login forms qui apparaissent dans le DOM (non-Basic-Auth).

    function setNativeValue(input, value) {
        // Compatible React / Vue / Angular
        const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
        if (setter) setter.call(input, value);
        else         input.value = value;
        ['input', 'change'].forEach(t => input.dispatchEvent(new Event(t, { bubbles: true })));
    }

    function fillContainer(container) {
        const c = getCreds();
        if (!c) return;

        const passwordField = container.querySelector('input[type="password"]');
        if (!passwordField) return;

        const allInputs     = Array.from(container.querySelectorAll('input:not([type="hidden"])'));
        const pwdIndex      = allInputs.indexOf(passwordField);
        const usernameField = allInputs.slice(0, pwdIndex).find(i => ['text', 'email', ''].includes(i.type));

        if (usernameField) setNativeValue(usernameField, c.username || DEFAULT_USERNAME);
        setNativeValue(passwordField, c.password);

        if (AUTO_SUBMIT) {
            container.querySelector('button[type="submit"], input[type="submit"], button:last-of-type')?.click();
        }
    }

    const filled = new WeakSet();

    function tryFill() {
        [
            ...document.querySelectorAll('form'),
            ...document.querySelectorAll('dialog, [role="dialog"], [aria-modal="true"]'),
        ].forEach(el => {
            if (filled.has(el) || !el.querySelector('input[type="password"]')) return;
            filled.add(el);
            fillContainer(el);
        });
    }

    function init() {
        new MutationObserver(tryFill).observe(document.documentElement ?? document, {
            childList: true,
            subtree:   true,
        });
        tryFill();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
