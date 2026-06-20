"use strict";

/*
 * Packages page interactions.
 *
 * This file intentionally uses defensive, browser-friendly JavaScript because
 * the compare stars are the main package-selection control. It does not depend
 * on Bootstrap, jQuery, or inline handlers. It powers:
 * - package comparison star toggles;
 * - selected package persistence for the Book Now page;
 * - the custom-package builder and its Book Now handoff.
 */
(function () {
    if (window.PopadooPackagesInteractionsStarted) {
        return;
    }

    window.PopadooPackagesInteractionsStarted = true;

    var compareStorageKey = "popadoo-compare-packages";
    var selectedPackageStorageKey = "popadoo-selected-package";
    var customPackageStorageKey = "popadoo-custom-package";
    var customPackageId = "custom-package";

    var cards = [];
    var packageMap = {};
    var comparedPackageIds = [];
    var selectedCharacteristics = [];

    var comparisonSection = null;
    var comparisonList = null;
    var comparisonEmpty = null;
    var comparisonStatus = null;
    var comparisonClearButton = null;

    var customOptionButtons = [];
    var customSelectedList = null;
    var customEmpty = null;
    var customClearButton = null;
    var customFinishButton = null;
    var customStatus = null;
    var customBookLink = null;

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
        var matcher = element.matches
            || element.msMatchesSelector
            || element.webkitMatchesSelector
            || element.mozMatchesSelector;

        return Boolean(matcher && matcher.call(element, selector));
    }

    function closestElement(element, selector) {
        var current = element;

        while (current && current.nodeType === 1) {
            if (elementMatches(current, selector)) {
                return current;
            }

            current = current.parentElement;
        }

        return null;
    }

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
            /* The page still works for the current visit when storage is blocked. */
        }
    }

    function getCurrentLanguage() {
        return document.documentElement.getAttribute("lang") || "en";
    }

    function translate(key) {
        var translations = window.popadooTranslations || {};
        var language = getCurrentLanguage();

        if (translations[language] && translations[language][key]) {
            return translations[language][key];
        }

        if (translations.en && translations.en[key]) {
            return translations.en[key];
        }

        return key;
    }

    function textFromCard(card, selector) {
        var element = card ? card.querySelector(selector) : null;
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

        return packageData.nameKey ? translate(packageData.nameKey) : packageData.name;
    }

    function packageSummary(packageData) {
        if (!packageData) {
            return "";
        }

        return packageData.summaryKey ? translate(packageData.summaryKey) : packageData.summary;
    }

    function packageBestFor(packageData) {
        if (!packageData) {
            return "";
        }

        return packageData.bestForKey ? translate(packageData.bestForKey) : "";
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

    function loadComparedPackages() {
        var storedIds;
        var filtered = [];

        try {
            storedIds = JSON.parse(getStoredValue(compareStorageKey) || "[]");
        } catch (error) {
            storedIds = [];
        }

        if (!Array.isArray(storedIds)) {
            return [];
        }

        storedIds.forEach(function (packageId) {
            if (packageExists(packageId) && filtered.indexOf(packageId) === -1) {
                filtered.push(packageId);
            }
        });

        return filtered;
    }

    function saveComparedPackages() {
        storeValue(compareStorageKey, JSON.stringify(comparedPackageIds));
    }

    function updateCardToggleState() {
        cards.forEach(function (card) {
            var packageId = card.getAttribute("data-package-id");
            var toggle = card.querySelector("[data-package-toggle]");
            var hiddenText = toggle ? toggle.querySelector(".visually-hidden") : null;
            var isCompared = comparedPackageIds.indexOf(packageId) !== -1;
            var data = packageMap[packageId];
            var labelKey = isCompared ? "packages.compareRemove" : "packages.compareAdd";
            var label = translate(labelKey) + ": " + packageName(data);

            card.classList.toggle("is-compared", isCompared);

            if (toggle) {
                toggle.classList.toggle("is-active", isCompared);
                toggle.setAttribute("aria-pressed", isCompared ? "true" : "false");
                toggle.setAttribute("aria-label", label);
                toggle.setAttribute("aria-controls", "comparison-list");

                if (!toggle.getAttribute("data-package-id")) {
                    toggle.setAttribute("data-package-id", packageId);
                }
            }

            if (hiddenText) {
                hiddenText.textContent = label;
            }
        });
    }

    function createComparisonItem(packageData) {
        var item = document.createElement("article");
        var hiddenInput = document.createElement("input");
        var header = document.createElement("div");
        var content = document.createElement("div");
        var heading = document.createElement("h3");
        var summary = document.createElement("p");
        var removeButton = document.createElement("button");
        var meta = document.createElement("dl");
        var bestForWrapper = document.createElement("div");
        var bestForTerm = document.createElement("dt");
        var bestForDescription = document.createElement("dd");
        var name = packageName(packageData);

        item.className = "comparison-item";
        item.setAttribute("data-comparison-item", packageData.id);

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
        removeButton.setAttribute("data-package-remove", packageData.id);
        removeButton.setAttribute("aria-label", translate("packages.compareRemove") + " " + name);
        removeButton.innerHTML = '<span aria-hidden="true">×</span>';

        header.appendChild(content);
        header.appendChild(removeButton);

        meta.className = "comparison-meta";
        bestForTerm.textContent = translate("packages.bestFor");
        bestForDescription.textContent = packageBestFor(packageData);
        bestForWrapper.appendChild(bestForTerm);
        bestForWrapper.appendChild(bestForDescription);
        meta.appendChild(bestForWrapper);

        item.appendChild(hiddenInput);
        item.appendChild(header);
        item.appendChild(meta);

        return item;
    }

    function renderComparison() {
        var fragment = document.createDocumentFragment();

        updateCardToggleState();

        if (comparisonEmpty) {
            comparisonEmpty.hidden = comparedPackageIds.length > 0;
        }

        if (comparisonClearButton) {
            comparisonClearButton.disabled = comparedPackageIds.length === 0;
        }

        if (!comparisonList) {
            return;
        }

        comparisonList.textContent = "";

        comparedPackageIds.forEach(function (packageId) {
            if (packageMap[packageId]) {
                fragment.appendChild(createComparisonItem(packageMap[packageId]));
            }
        });

        comparisonList.appendChild(fragment);
    }

    function revealComparisonSection() {
        if (!comparisonSection) {
            return;
        }

        if (typeof comparisonSection.scrollIntoView === "function") {
            comparisonSection.scrollIntoView({ behavior: "smooth", block: "nearest" });
        }
    }

    function toggleComparedPackage(packageId, shouldRevealComparison) {
        var data = packageMap[packageId];

        if (!data) {
            return;
        }

        if (comparedPackageIds.indexOf(packageId) !== -1) {
            comparedPackageIds = removeFromList(comparedPackageIds, packageId);
            announceComparison(packageName(data) + " " + translate("packages.statusRemoved"));
        } else {
            addUnique(comparedPackageIds, packageId);
            announceComparison(packageName(data) + " " + translate("packages.statusAdded"));

            if (shouldRevealComparison) {
                revealComparisonSection();
            }
        }

        saveComparedPackages();
        renderComparison();
    }

    function removeComparedPackage(packageId) {
        var data = packageMap[packageId];

        if (!packageExists(packageId)) {
            return;
        }

        comparedPackageIds = removeFromList(comparedPackageIds, packageId);
        saveComparedPackages();
        renderComparison();
        announceComparison(packageName(data) + " " + translate("packages.statusRemoved"));
    }

    function clearComparison() {
        comparedPackageIds = [];
        saveComparedPackages();
        renderComparison();
        announceComparison(translate("packages.statusCleared"));
    }

    function getPackageIdFromToggle(toggle) {
        var card = closestElement(toggle, "[data-package-card]");
        return toggle.getAttribute("data-package-id") || (card ? card.getAttribute("data-package-id") : "");
    }

    function handleCompareToggle(event, toggle) {
        var packageId = getPackageIdFromToggle(toggle);

        if (!packageId) {
            return;
        }

        event.preventDefault();
        event.stopPropagation();
        toggleComparedPackage(packageId, true);
    }

    function getCharacteristicById(characteristicId) {
        var found = null;

        customOptionButtons.forEach(function (button) {
            if (button.getAttribute("data-custom-characteristic") === characteristicId) {
                found = {
                    id: characteristicId,
                    labelKey: button.getAttribute("data-characteristic-label-key"),
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

        return characteristic.labelKey ? translate(characteristic.labelKey) : characteristic.label;
    }

    function updateCustomOptionState() {
        customOptionButtons.forEach(function (button) {
            var characteristicId = button.getAttribute("data-custom-characteristic");
            var isSelected = selectedCharacteristics.indexOf(characteristicId) !== -1;
            var labelKey = button.getAttribute("data-characteristic-label-key");
            var label = labelKey ? translate(labelKey) : button.textContent.trim();
            var action = isSelected ? translate("packages.customRemoveCharacteristic") : translate("packages.customAddCharacteristic");

            button.classList.toggle("is-selected", isSelected);
            button.setAttribute("aria-pressed", isSelected ? "true" : "false");
            button.setAttribute("aria-label", action + ": " + label);
        });
    }

    function createSelectedCharacteristicItem(characteristic) {
        var item = document.createElement("li");
        var label = document.createElement("span");
        var removeButton = document.createElement("button");

        item.className = "custom-selected-item";
        label.textContent = characteristicName(characteristic);

        removeButton.className = "custom-selected-remove";
        removeButton.type = "button";
        removeButton.setAttribute("data-custom-remove", characteristic.id);
        removeButton.setAttribute("aria-label", translate("packages.customRemoveCharacteristic") + " " + characteristicName(characteristic));
        removeButton.innerHTML = '<span aria-hidden="true">×</span>';

        item.appendChild(label);
        item.appendChild(removeButton);

        return item;
    }

    function getLocalizedContactHref() {
        var url = new URL("contact.html", window.location.href);
        var fileName;

        url.searchParams.set("package", customPackageId);
        url.searchParams.set("lang", getCurrentLanguage());
        fileName = url.pathname.substring(url.pathname.lastIndexOf("/") + 1) || "contact.html";

        return fileName + url.search;
    }

    function renderCustomPackage() {
        var selected = [];
        var fragment = document.createDocumentFragment();

        selectedCharacteristics.forEach(function (characteristicId) {
            var characteristic = getCharacteristicById(characteristicId);

            if (characteristic) {
                selected.push(characteristic);
            }
        });

        updateCustomOptionState();

        if (customEmpty) {
            customEmpty.hidden = selected.length > 0;
        }

        if (customClearButton) {
            customClearButton.disabled = selected.length === 0;
        }

        if (customFinishButton) {
            customFinishButton.disabled = selected.length === 0;
        }

        if (customBookLink) {
            customBookLink.href = getLocalizedContactHref();
        }

        if (!customSelectedList) {
            return;
        }

        customSelectedList.textContent = "";
        selected.forEach(function (characteristic) {
            fragment.appendChild(createSelectedCharacteristicItem(characteristic));
        });
        customSelectedList.appendChild(fragment);
    }

    function saveCustomPackage() {
        var selected = [];

        selectedCharacteristics.forEach(function (characteristicId) {
            var characteristic = getCharacteristicById(characteristicId);

            if (characteristic) {
                selected.push(characteristic);
            }
        });

        storeValue(customPackageStorageKey, JSON.stringify({
            id: customPackageId,
            nameKey: "packages.customPackageName",
            characteristics: selected,
            createdAt: new Date().toISOString()
        }));
        storeValue(selectedPackageStorageKey, customPackageId);
    }

    function toggleCustomCharacteristic(characteristicId) {
        var characteristic = getCharacteristicById(characteristicId);

        if (!characteristic) {
            return;
        }

        if (selectedCharacteristics.indexOf(characteristicId) !== -1) {
            selectedCharacteristics = removeFromList(selectedCharacteristics, characteristicId);
            announceCustom(characteristicName(characteristic) + " " + translate("packages.customStatusRemoved"));
        } else {
            addUnique(selectedCharacteristics, characteristicId);
            announceCustom(characteristicName(characteristic) + " " + translate("packages.customStatusAdded"));
        }

        renderCustomPackage();
    }

    function removeCustomCharacteristic(characteristicId) {
        var characteristic = getCharacteristicById(characteristicId);

        selectedCharacteristics = removeFromList(selectedCharacteristics, characteristicId);
        renderCustomPackage();

        if (characteristic) {
            announceCustom(characteristicName(characteristic) + " " + translate("packages.customStatusRemoved"));
        }
    }

    function clearCustomPackage() {
        selectedCharacteristics = [];
        renderCustomPackage();
        announceCustom(translate("packages.customStatusCleared"));

        if (customBookLink) {
            customBookLink.hidden = true;
        }
    }

    function finishCustomPackage() {
        if (selectedCharacteristics.length === 0) {
            announceCustom(translate("packages.customChooseFirst"));
            return;
        }

        saveCustomPackage();
        renderCustomPackage();

        if (customBookLink) {
            customBookLink.hidden = false;
            customBookLink.focus();
        }

        announceCustom(translate("packages.customStatusFinished"));
    }

    function handleDocumentClick(event) {
        var target = event.target;
        var compareToggle = closestElement(target, "[data-package-toggle]");
        var compareRemove = closestElement(target, "[data-package-remove]");
        var selectLink = closestElement(target, "[data-package-select]");
        var customToggle = closestElement(target, "[data-custom-characteristic]");
        var customRemove = closestElement(target, "[data-custom-remove]");

        if (compareToggle) {
            handleCompareToggle(event, compareToggle);
            return;
        }

        if (compareRemove) {
            event.preventDefault();
            removeComparedPackage(compareRemove.getAttribute("data-package-remove"));
            return;
        }

        if (selectLink) {
            storeValue(selectedPackageStorageKey, selectLink.getAttribute("data-package-select"));
            return;
        }

        if (customToggle) {
            event.preventDefault();
            toggleCustomCharacteristic(customToggle.getAttribute("data-custom-characteristic"));
            return;
        }

        if (customRemove) {
            event.preventDefault();
            removeCustomCharacteristic(customRemove.getAttribute("data-custom-remove"));
        }
    }

    function handleCompareKeyboard(event) {
        var key = event.key || event.code;

        if (key !== "Enter" && key !== " " && key !== "Spacebar") {
            return;
        }

        handleCompareToggle(event, event.currentTarget);
    }

    function bindEvents() {
        /* Capture-phase delegation runs before other handlers can stop the click. */
        document.addEventListener("click", handleDocumentClick, true);

        toArray(document.querySelectorAll("[data-package-toggle]")).forEach(function (toggle) {
            toggle.addEventListener("keydown", handleCompareKeyboard);
        });

        if (comparisonClearButton) {
            comparisonClearButton.addEventListener("click", clearComparison);
        }

        if (customClearButton) {
            customClearButton.addEventListener("click", clearCustomPackage);
        }

        if (customFinishButton) {
            customFinishButton.addEventListener("click", finishCustomPackage);
        }

        document.addEventListener("popadoo:language-applied", function () {
            renderComparison();
            renderCustomPackage();
        });
    }

    function collectPackages() {
        cards = toArray(document.querySelectorAll("[data-package-card]"));
        packageMap = {};

        cards.forEach(function (card) {
            var packageId = card.getAttribute("data-package-id");

            if (!packageId) {
                return;
            }

            packageMap[packageId] = {
                id: packageId,
                nameKey: card.getAttribute("data-package-name-key"),
                summaryKey: card.getAttribute("data-package-summary-key"),
                bestForKey: card.getAttribute("data-package-best-for-key"),
                name: textFromCard(card, "h3"),
                summary: textFromCard(card, "p:not(.package-badge)")
            };
        });
    }

    function init() {
        comparisonSection = document.querySelector(".comparison-section");
        comparisonList = document.querySelector("#comparison-list");
        comparisonEmpty = document.querySelector("#comparison-empty");
        comparisonStatus = document.querySelector("#comparison-status");
        comparisonClearButton = document.querySelector("#comparison-clear");
        customOptionButtons = toArray(document.querySelectorAll("[data-custom-characteristic]"));
        customSelectedList = document.querySelector("#custom-selected-list");
        customEmpty = document.querySelector("#custom-package-empty");
        customClearButton = document.querySelector("#custom-package-clear");
        customFinishButton = document.querySelector("#custom-package-finish");
        customStatus = document.querySelector("#custom-package-status");
        customBookLink = document.querySelector("#custom-package-book-link");

        collectPackages();

        if (cards.length === 0) {
            return;
        }

        comparedPackageIds = loadComparedPackages();
        bindEvents();
        renderComparison();
        renderCustomPackage();

        /* Expose a tiny debug hook so a developer can test from the console. */
        window.PopadooToggleComparedPackage = toggleComparedPackage;
    }

    onReady(init);
}());
