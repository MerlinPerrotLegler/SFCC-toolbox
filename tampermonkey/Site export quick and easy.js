// ==UserScript==
// @name         Site export quick and easy
// @namespace    http://tampermonkey.net/
// @version      2026-02-11
// @description  try to take over the world!
// @author       Merlin Perrot
// @match        https://*/on/demandware.store/Sites-Site/default*
// @icon         https://www.google.com/s2/favicons?sz=64&domain=bollebrands.com
// @grant        none
// ==/UserScript==


setTimeout((function() {
    'use strict';

    var form = document.querySelector('form#siteImpexBottom')
    if (form !== null) {
        console.log('loading Site export quick and easy ')
    } else {
        return
    }

    function checkLabel(str) {
        var spans = document.getElementById('unitSelection').querySelectorAll('span[unselectable]')
        str = str.toLowerCase()
        spans.forEach((span) => {
            let label = span.innerText.toLowerCase()
            if (label == str) {
                span.parentElement.querySelector('input').click()
            }
        })
    }

    function addCheckboxToElement(el, checkboxStrList) {
        // Créer le fieldset
        const fieldset = document.createElement('fieldset');
        fieldset.style.display = 'flex';
        fieldset.style.justifyContent = 'space-between';
        fieldset.style.flexWrap = 'wrap';

        // Parcourir la liste des checkboxes
        checkboxStrList.forEach((labelText, index) => {
            // Créer un conteneur pour chaque checkbox
            const checkboxWrapper = document.createElement('div');
            checkboxWrapper.style.minWidth = '25em';

            // Créer la checkbox
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.id = `checkbox-${index}`;
            checkbox.value = labelText; // La valeur = le label

            // Ajouter l'événement click
            checkbox.addEventListener('click', function() {
                checkLabel(labelText, this.checked);
            });

            // Créer le label
            const label = document.createElement('label');
            label.htmlFor = `checkbox-${index}`;
            label.textContent = labelText;

            // Assembler checkbox + label
            checkboxWrapper.appendChild(checkbox);
            checkboxWrapper.appendChild(label);

            // Ajouter au fieldset
            fieldset.appendChild(checkboxWrapper);
        });

        // Ajouter le fieldset à l'élément
        let target = document.getElementById('unitSelection')
        el.insertBefore(fieldset, target);
    }

    //openAll()
    setTimeout(() => {
        addCheckboxToElement(
            form,
            [
             "A/B Tests",
             "Active Data Feeds",
             "Cache Settings",
             "Campaigns and Promotions",
             "Content",
             "Coupons",
             "Customer CDN Settings",
             "Customer Groups",
             "Custom Objects",
             "Dynamic File Resources",
             "Distributed Commerce Extensions",
             "OCAPI Settings",
             "Payment Methods",
             "Payment Processors",
             "Redirect URLs",
             "Search Settings",
             "Shipping",
             "Site Descriptor",
             "Site Preferences",
             "Static, Dynamic and Alias Mappings",
             "Sitemap Settings",
             "Slots",
             "Sorting Rules",
             "Source Codes",
             "Stores",
             "Tax",
             "URL Rules"
            ]
        )
    }, 20)

}), 100);