"use strict";

/*
 * Packages page interactions.
 *
 * This file powers:
 * - package comparison star toggles;
 * - selected package persistence for the Book Now page;
 * - the custom-package builder;
 * - the custom package booking handoff.
 */
(function () {
    if (window.PopadooPackagesInteractionsStarted) {
        return;
    }

    window.PopadooPackagesInteractionsStarted = true;

    const compareStorageKey = "popadoo-compare-packages";
    const selectedPackageStorageKey = "popadoo-selected-package";
    const customPackageStorageKey = "popadoo-custom-package";
    const customPackageId = "custom-package";

    let cards = [];
    let packageMap = {};
    let comparedPackageIds = [];
    let selectedCharacteristics = [];

    let comparisonSection = null;
    let comparisonList = null;
    let comparisonEmpty = null;
    let comparisonStatus = null;
    let comparisonClearButton = null;

    let customOptionButtons = [];
    let customSelectedList = null;
    let customEmpty = null;
    let customClearButton = null;
    let customFinishButton = null;
    let customStatus = null;
    let customBookLink = null;

    function onReady(callback) {
        if (document.readyState === "loading") {
            document.addEventListener("DOMContentLoaded", callback);
            return;
        }

        callback();
    }

    function toArray(list) {
        return Array.prototype.slice.call(list || []);
    }

    function elementMatches(element, selector) {
        const matcher =
            element.matches ||
            element.msMatchesSelector ||
            element.webkitMatchesSelector;

        return Boolean(matcher && matcher.call(element, selector));
    }

    function closestElement(element, selector) {
        let current = element;

        while (current && current.nodeType === 1) {
            if (elementMatches(current, selector)) {
                return current;
            }

            current = current.parentElement;
        }

        return null;
    }

    /*
     * Safe localStorage functions.
     *
     * The page will continue working during the current visit even when
     * localStorage is disabled or unavailable.
     */
    function getStoredValue(key) {
        try {
            return window.localStorage.getItem(key);
        } catch (error) {
            return null;
        }
    }

    function storeValue(key, value) {
        try {
            window.localStorage.setItem(key, value);
        } catch (error) {
            console.warn("Local storage is unavailable.", error);
        }
    }

    function removeStoredValue(key) {
        try {
            window.localStorage.removeItem(key);
        } catch (error) {
            console.warn("Local storage is unavailable.", error);
        }
    }

    function getCurrentLanguage() {
        return document.documentElement.getAttribute("lang") || "en";
    }

    /*
     * Retrieve a translation from translations.js.
     *
     * English is used as a fallback when a translation is unavailable.
     */
    function translate(key) {
        const translations = window.popadooTranslations || {};
        const language = getCurrentLanguage();

        if (
            translations[language] &&
            Object.prototype.hasOwnProperty.call(
                translations[language],
                key
            )
        ) {
            return translations[language][key];
        }

        if (
            translations.en &&
            Object.prototype.hasOwnProperty.call(translations.en, key)
        ) {
            return translations.en[key];
        }

        return key;
    }

    function textFromCard(card, selector) {
        const element = card ? card.querySelector(selector) : null;

        return element ? element.textContent.trim() : "";
    }

    function addUnique(list, value) {
        if (list.indexOf(value) === -1) {
            list.push(value);
        }

        return list;
    }

    function removeFromList(list, value) {
        return list.filter(function (item) {
            return item !== value;
        });
    }

    function packageExists(packageId) {
        return Boolean(packageId && packageMap[packageId]);
    }

    function packageName(packageData) {
        if (!packageData) {
            return "";
        }

        return packageData.nameKey
            ? translate(packageData.nameKey)
            : packageData.name;
    }

    function packageSummary(packageData) {
        if (!packageData) {
            return "";
        }

        return packageData.summaryKey
            ? translate(packageData.summaryKey)
            : packageData.summary;
    }

    function packageBestFor(packageData) {
        if (!packageData) {
            return "";
        }

        return packageData.bestForKey
            ? translate(packageData.bestForKey)
            : packageData.bestFor;
    }

    function announceComparison(message) {
        if (comparisonStatus) {
            comparisonStatus.textContent = message;
        }
    }

    function announceCustom(message) {
        if (customStatus) {
            customStatus.textContent = message;
        }
    }

    /*
     * Restore only package IDs that still exist in the current page.
     */
    function loadComparedPackages() {
        let storedIds;

        try {
            storedIds = JSON.parse(
                getStoredValue(compareStorageKey) || "[]"
            );
        } catch (error) {
            storedIds = [];
        }

        if (!Array.isArray(storedIds)) {
            return [];
        }

        return storedIds.filter(function (packageId, index) {
            return (
                packageExists(packageId) &&
                storedIds.indexOf(packageId) === index
            );
        });
    }

    function saveComparedPackages() {
        storeValue(
            compareStorageKey,
            JSON.stringify(comparedPackageIds)
        );
    }

    /*
     * Keep each package card and its star button synchronized with the
     * current comparison state.
     */
    function updateCardToggleState() {
        cards.forEach(function (card) {
            const packageId = card.getAttribute("data-package-id");
            const toggle = card.querySelector(
                "[data-package-toggle]"
            );
            const hiddenText = toggle
                ? toggle.querySelector(".visually-hidden")
                : null;
            const isCompared =
                comparedPackageIds.indexOf(packageId) !== -1;
            const data = packageMap[packageId];

            const labelKey = isCompared
                ? "packages.compareRemove"
                : "packages.compareAdd";

            const label =
                translate(labelKey) + ": " + packageName(data);

            card.classList.toggle("is-compared", isCompared);

            if (toggle) {
                toggle.classList.toggle("is-active", isCompared);

                toggle.setAttribute(
                    "aria-pressed",
                    isCompared ? "true" : "false"
                );

                toggle.setAttribute("aria-label", label);
                toggle.setAttribute(
                    "aria-controls",
                    "comparison-list"
                );

                if (!toggle.getAttribute("data-package-id")) {
                    toggle.setAttribute(
                        "data-package-id",
                        packageId
                    );
                }
            }

            if (hiddenText) {
                hiddenText.textContent = label;
            }
        });
    }

    /*
     * Create one selected package card for the comparison section.
     */
    function createComparisonItem(packageData) {
        const item = document.createElement("article");
        const hiddenInput = document.createElement("input");
        const header = document.createElement("div");
        const content = document.createElement("div");
        const heading = document.createElement("h3");
        const summary = document.createElement("p");
        const removeButton = document.createElement("button");
        const meta = document.createElement("dl");
        const bestForWrapper = document.createElement("div");
        const bestForTerm = document.createElement("dt");
        const bestForDescription = document.createElement("dd");
        const name = packageName(packageData);

        item.className = "comparison-item";

        item.setAttribute(
            "data-comparison-item",
            packageData.id
        );

        hiddenInput.type = "hidden";
        hiddenInput.name = "comparePackages[]";
        hiddenInput.value = packageData.id;

        header.className = "comparison-item-header";

        heading.textContent = name;
        summary.textContent = packageSummary(packageData);

        content.appendChild(heading);
        content.appendChild(summary);

        removeButton.className = "comparison-remove";
        removeButton.type = "button";

        removeButton.setAttribute(
            "data-package-remove",
            packageData.id
        );

        removeButton.setAttribute(
            "aria-label",
            translate("packages.compareRemove") + " " + name
        );

        removeButton.innerHTML =
            '<span aria-hidden="true">×</span>';

        header.appendChild(content);
        header.appendChild(removeButton);

        meta.className = "comparison-meta";

        bestForTerm.textContent =
            translate("packages.bestFor");

        bestForDescription.textContent =
            packageBestFor(packageData);

        bestForWrapper.appendChild(bestForTerm);
        bestForWrapper.appendChild(bestForDescription);
        meta.appendChild(bestForWrapper);

        item.appendChild(hiddenInput);
        item.appendChild(header);
        item.appendChild(meta);

        return item;
    }

    /*
     * Rebuild the comparison area whenever a package is selected or
     * removed.
     */
    function renderComparison() {
        const fragment = document.createDocumentFragment();

        updateCardToggleState();

        if (comparisonEmpty) {
            comparisonEmpty.hidden =
                comparedPackageIds.length > 0;
        }

        if (comparisonClearButton) {
            comparisonClearButton.disabled =
                comparedPackageIds.length === 0;
        }

        if (!comparisonList) {
            return;
        }

        comparisonList.textContent = "";

        comparedPackageIds.forEach(function (packageId) {
            if (packageMap[packageId]) {
                fragment.appendChild(
                    createComparisonItem(
                        packageMap[packageId]
                    )
                );
            }
        });

        comparisonList.appendChild(fragment);
    }

    function revealComparisonSection() {
        if (
            comparisonSection &&
            typeof comparisonSection.scrollIntoView === "function"
        ) {
            comparisonSection.scrollIntoView({
                behavior: "smooth",
                block: "nearest"
            });
        }
    }

    /*
     * Add or remove one package from the comparison list.
     */
    function toggleComparedPackage(
        packageId,
        shouldRevealComparison
    ) {
        const data = packageMap[packageId];

        if (!data) {
            return;
        }

        if (comparedPackageIds.indexOf(packageId) !== -1) {
            comparedPackageIds = removeFromList(
                comparedPackageIds,
                packageId
            );

            announceComparison(
                packageName(data) +
                    " " +
                    translate("packages.statusRemoved")
            );
        } else {
            addUnique(comparedPackageIds, packageId);

            announceComparison(
                packageName(data) +
                    " " +
                    translate("packages.statusAdded")
            );

            if (shouldRevealComparison) {
                revealComparisonSection();
            }
        }

        saveComparedPackages();
        renderComparison();
    }

    function removeComparedPackage(packageId) {
        const data = packageMap[packageId];

        if (!packageExists(packageId)) {
            return;
        }

        comparedPackageIds = removeFromList(
            comparedPackageIds,
            packageId
        );

        saveComparedPackages();
        renderComparison();

        announceComparison(
            packageName(data) +
                " " +
                translate("packages.statusRemoved")
        );
    }

    function clearComparison() {
        comparedPackageIds = [];

        removeStoredValue(compareStorageKey);
        renderComparison();

        announceComparison(
            translate("packages.statusCleared")
        );
    }

    function getPackageIdFromToggle(toggle) {
        const card = closestElement(
            toggle,
            "[data-package-card]"
        );

        return (
            toggle.getAttribute("data-package-id") ||
            (card ? card.getAttribute("data-package-id") : "")
        );
    }

    function handleCompareToggle(event, toggle) {
        const packageId = getPackageIdFromToggle(toggle);

        if (!packageId) {
            return;
        }

        event.preventDefault();
        event.stopPropagation();

        toggleComparedPackage(packageId, true);
    }

    /*
     * Retrieve one custom-package option from its button.
     */
    function getCharacteristicById(characteristicId) {
        let found = null;

        customOptionButtons.forEach(function (button) {
            if (
                button.getAttribute(
                    "data-custom-characteristic"
                ) === characteristicId
            ) {
                found = {
                    id: characteristicId,
                    labelKey: button.getAttribute(
                        "data-characteristic-label-key"
                    ),
                    label: button.textContent.trim()
                };
            }
        });

        return found;
    }

    function characteristicName(characteristic) {
        if (!characteristic) {
            return "";
        }

        return characteristic.labelKey
            ? translate(characteristic.labelKey)
            : characteristic.label;
    }

    /*
     * Update the selected styling and accessibility state of each
     * custom-package option.
     */
    function updateCustomOptionState() {
        customOptionButtons.forEach(function (button) {
            const characteristicId =
                button.getAttribute(
                    "data-custom-characteristic"
                );

            const isSelected =
                selectedCharacteristics.indexOf(
                    characteristicId
                ) !== -1;

            const labelKey = button.getAttribute(
                "data-characteristic-label-key"
            );

            const label = labelKey
                ? translate(labelKey)
                : button.textContent.trim();

            const action = isSelected
                ? translate(
                    "packages.customRemoveCharacteristic"
                )
                : translate(
                    "packages.customAddCharacteristic"
                );

            button.classList.toggle(
                "is-selected",
                isSelected
            );

            button.setAttribute(
                "aria-pressed",
                isSelected ? "true" : "false"
            );

            button.setAttribute(
                "aria-label",
                action + ": " + label
            );
        });
    }

    function createSelectedCharacteristicItem(
        characteristic
    ) {
        const item = document.createElement("li");
        const label = document.createElement("span");
        const removeButton = document.createElement("button");

        item.className = "custom-selected-item";

        label.textContent =
            characteristicName(characteristic);

        removeButton.className = "custom-selected-remove";
        removeButton.type = "button";

        removeButton.setAttribute(
            "data-custom-remove",
            characteristic.id
        );

        removeButton.setAttribute(
            "aria-label",
            translate(
                "packages.customRemoveCharacteristic"
            ) +
                " " +
                characteristicName(characteristic)
        );

        removeButton.innerHTML =
            '<span aria-hidden="true">×</span>';

        item.appendChild(label);
        item.appendChild(removeButton);

        return item;
    }

    /*
     * Read the contact-page URL generated by Django from the template.
     *
     * The related HTML element must contain:
     *
     * data-contact-url="{% url 'core:contact' %}"
     */
    function getLocalizedContactHref() {
        const baseHref = customBookLink
            ? customBookLink.getAttribute("data-contact-url")
            : "/contact/";

        const url = new URL(
            baseHref,
            window.location.href
        );

        url.searchParams.set(
            "package",
            customPackageId
        );

        url.searchParams.set(
            "lang",
            getCurrentLanguage()
        );

        return url.pathname + url.search;
    }

    /*
     * Render the currently selected custom-package characteristics.
     */
    function renderCustomPackage() {
        const selected = [];
        const fragment = document.createDocumentFragment();

        selectedCharacteristics.forEach(
            function (characteristicId) {
                const characteristic =
                    getCharacteristicById(
                        characteristicId
                    );

                if (characteristic) {
                    selected.push(characteristic);
                }
            }
        );

        updateCustomOptionState();

        if (customEmpty) {
            customEmpty.hidden = selected.length > 0;
        }

        if (customClearButton) {
            customClearButton.disabled =
                selected.length === 0;
        }

        if (customFinishButton) {
            customFinishButton.disabled =
                selected.length === 0;
        }

        if (customBookLink) {
            customBookLink.href =
                getLocalizedContactHref();
        }

        if (!customSelectedList) {
            return;
        }

        customSelectedList.textContent = "";

        selected.forEach(function (characteristic) {
            fragment.appendChild(
                createSelectedCharacteristicItem(
                    characteristic
                )
            );
        });

        customSelectedList.appendChild(fragment);
    }

    /*
     * Save the completed custom package so that the booking page can
     * later read it.
     */
    function saveCustomPackage() {
        const selected = [];

        selectedCharacteristics.forEach(
            function (characteristicId) {
                const characteristic =
                    getCharacteristicById(
                        characteristicId
                    );

                if (characteristic) {
                    selected.push(characteristic);
                }
            }
        );

        storeValue(
            customPackageStorageKey,
            JSON.stringify({
                id: customPackageId,
                nameKey: "packages.customPackageName",
                characteristics: selected,
                createdAt: new Date().toISOString()
            })
        );

        storeValue(
            selectedPackageStorageKey,
            customPackageId
        );
    }

    function toggleCustomCharacteristic(
        characteristicId
    ) {
        const characteristic =
            getCharacteristicById(characteristicId);

        if (!characteristic) {
            return;
        }

        if (
            selectedCharacteristics.indexOf(
                characteristicId
            ) !== -1
        ) {
            selectedCharacteristics = removeFromList(
                selectedCharacteristics,
                characteristicId
            );

            announceCustom(
                characteristicName(characteristic) +
                    " " +
                    translate(
                        "packages.customStatusRemoved"
                    )
            );
        } else {
            addUnique(
                selectedCharacteristics,
                characteristicId
            );

            announceCustom(
                characteristicName(characteristic) +
                    " " +
                    translate(
                        "packages.customStatusAdded"
                    )
            );
        }

        renderCustomPackage();
    }

    function removeCustomCharacteristic(
        characteristicId
    ) {
        const characteristic =
            getCharacteristicById(characteristicId);

        selectedCharacteristics = removeFromList(
            selectedCharacteristics,
            characteristicId
        );

        renderCustomPackage();

        if (characteristic) {
            announceCustom(
                characteristicName(characteristic) +
                    " " +
                    translate(
                        "packages.customStatusRemoved"
                    )
            );
        }
    }

    function clearCustomPackage() {
        selectedCharacteristics = [];

        renderCustomPackage();

        announceCustom(
            translate("packages.customStatusCleared")
        );

        removeStoredValue(customPackageStorageKey);

        if (customBookLink) {
            customBookLink.hidden = true;
        }
    }

    /*
     * Finalize the custom selection and reveal the booking link.
     */
    function finishCustomPackage() {
        if (selectedCharacteristics.length === 0) {
            announceCustom(
                translate("packages.customChooseFirst")
            );

            return;
        }

        saveCustomPackage();
        renderCustomPackage();

        if (customBookLink) {
            customBookLink.hidden = false;
            customBookLink.focus();
        }

        announceCustom(
            translate("packages.customStatusFinished")
        );
    }

    /*
     * Delegated click handling also supports buttons that are created
     * dynamically by JavaScript.
     */
    function handleDocumentClick(event) {
        const target = event.target;

        const compareToggle = closestElement(
            target,
            "[data-package-toggle]"
        );

        const compareRemove = closestElement(
            target,
            "[data-package-remove]"
        );

        const selectLink = closestElement(
            target,
            "[data-package-select]"
        );

        const customToggle = closestElement(
            target,
            "[data-custom-characteristic]"
        );

        const customRemove = closestElement(
            target,
            "[data-custom-remove]"
        );

        if (compareToggle) {
            handleCompareToggle(event, compareToggle);
            return;
        }

        if (compareRemove) {
            event.preventDefault();

            removeComparedPackage(
                compareRemove.getAttribute(
                    "data-package-remove"
                )
            );

            return;
        }

        if (selectLink) {
            storeValue(
                selectedPackageStorageKey,
                selectLink.getAttribute(
                    "data-package-select"
                )
            );

            return;
        }

        if (customToggle) {
            event.preventDefault();

            toggleCustomCharacteristic(
                customToggle.getAttribute(
                    "data-custom-characteristic"
                )
            );

            return;
        }

        if (customRemove) {
            event.preventDefault();

            removeCustomCharacteristic(
                customRemove.getAttribute(
                    "data-custom-remove"
                )
            );
        }
    }

    /*
     * Let keyboard users activate package comparison controls with
     * Enter or Space.
     */
    function handleCompareKeyboard(event) {
        const key = event.key || event.code;

        if (
            key !== "Enter" &&
            key !== " " &&
            key !== "Spacebar"
        ) {
            return;
        }

        handleCompareToggle(event, event.currentTarget);
    }

    function bindEvents() {
        document.addEventListener(
            "click",
            handleDocumentClick,
            true
        );

        toArray(
            document.querySelectorAll(
                "[data-package-toggle]"
            )
        ).forEach(function (toggle) {
            toggle.addEventListener(
                "keydown",
                handleCompareKeyboard
            );
        });

        if (comparisonClearButton) {
            comparisonClearButton.addEventListener(
                "click",
                clearComparison
            );
        }

        if (customClearButton) {
            customClearButton.addEventListener(
                "click",
                clearCustomPackage
            );
        }

        if (customFinishButton) {
            customFinishButton.addEventListener(
                "click",
                finishCustomPackage
            );
        }

        /*
         * main.js may dispatch this event after changing language.
         */
        document.addEventListener(
            "popadoo:language-applied",
            function () {
                renderComparison();
                renderCustomPackage();
            }
        );
    }

    /*
     * Collect package metadata from the HTML cards.
     */
    function collectPackages() {
        cards = toArray(
            document.querySelectorAll(
                "[data-package-card]"
            )
        );

        packageMap = {};

        cards.forEach(function (card) {
            const packageId =
                card.getAttribute("data-package-id");

            if (!packageId) {
                return;
            }

            packageMap[packageId] = {
                id: packageId,

                nameKey: card.getAttribute(
                    "data-package-name-key"
                ),

                summaryKey: card.getAttribute(
                    "data-package-summary-key"
                ),

                bestForKey: card.getAttribute(
                    "data-package-best-for-key"
                ),

                name: textFromCard(card, "h3"),

                summary: textFromCard(
                    card,
                    "p:not(.package-badge)"
                ),

                bestFor: textFromCard(
                    card,
                    "[data-package-best-for]"
                )
            };
        });
    }

    /*
     * Initialize the comparison and custom-package interfaces.
     */
    function init() {
        comparisonSection =
            document.querySelector(
                ".comparison-section"
            );

        comparisonList =
            document.querySelector(
                "#comparison-list"
            );

        comparisonEmpty =
            document.querySelector(
                "#comparison-empty"
            );

        comparisonStatus =
            document.querySelector(
                "#comparison-status"
            );

        comparisonClearButton =
            document.querySelector(
                "#comparison-clear"
            );

        customOptionButtons = toArray(
            document.querySelectorAll(
                "[data-custom-characteristic]"
            )
        );

        customSelectedList =
            document.querySelector(
                "#custom-selected-list"
            );

        customEmpty =
            document.querySelector(
                "#custom-package-empty"
            );

        customClearButton =
            document.querySelector(
                "#custom-package-clear"
            );

        customFinishButton =
            document.querySelector(
                "#custom-package-finish"
            );

        customStatus =
            document.querySelector(
                "#custom-package-status"
            );

        customBookLink =
            document.querySelector(
                "#custom-package-book-link"
            );

        collectPackages();

        if (cards.length === 0) {
            return;
        }

        comparedPackageIds =
            loadComparedPackages();

        bindEvents();
        renderComparison();
        renderCustomPackage();

        /*
         * Small development helper. It allows you to test comparison
         * from the browser console.
         */
        window.PopadooToggleComparedPackage =
            toggleComparedPackage;
    }

    onReady(init);
}());