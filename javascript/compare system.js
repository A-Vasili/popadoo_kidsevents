"use strict";

/*
 * packages.html behaviour.
 * This file powers two independent features:
 * 1. Star buttons that add/remove package cards from the comparison form.
 * 2. A custom-package builder that stores selected characteristics for Book Now.
 */
(() => {
    const compareStorageKey = "popadoo-compare-packages";
    const selectedPackageStorageKey = "popadoo-selected-package";
    const customPackageStorageKey = "popadoo-custom-package";
    const customPackageId = "custom-package";

    const onReady = (callback) => {
        if (document.readyState === "loading") {
            document.addEventListener("DOMContentLoaded", callback, { once: true });
        } else {
            callback();
        }
    };

    onReady(() => {
        const cards = Array.from(document.querySelectorAll("[data-package-card]"));
        const compareForm = document.querySelector("#package-comparison-form");
        const comparisonList = document.querySelector("#comparison-list");
        const comparisonEmpty = document.querySelector("#comparison-empty");
        const comparisonStatus = document.querySelector("#comparison-status");
        const clearButton = document.querySelector("#comparison-clear");
        const customForm = document.querySelector("#custom-package-form");
        const customOptionButtons = Array.from(document.querySelectorAll("[data-custom-characteristic]"));
        const customSelectedList = document.querySelector("#custom-selected-list");
        const customEmpty = document.querySelector("#custom-package-empty");
        const customClearButton = document.querySelector("#custom-package-clear");
        const customFinishButton = document.querySelector("#custom-package-finish");
        const customStatus = document.querySelector("#custom-package-status");
        const customBookLink = document.querySelector("#custom-package-book-link");

        const packageMap = new Map(cards.map((card) => [
            card.dataset.packageId,
            {
                id: card.dataset.packageId,
                nameKey: card.dataset.packageNameKey,
                summaryKey: card.dataset.packageSummaryKey,
                bestForKey: card.dataset.packageBestForKey
            }
        ]));

        let comparedPackageIds = [];
        let selectedCharacteristics = [];

        const getStoredValue = (key) => {
            try {
                return window.localStorage.getItem(key);
            } catch (error) {
                return null;
            }
        };

        const storeValue = (key, value) => {
            try {
                window.localStorage.setItem(key, value);
            } catch (error) {
                /* The current interaction continues even when private browsing blocks storage. */
            }
        };

        const currentLanguage = () => document.documentElement.lang || "en";

        const translate = (key) => {
            const translations = window.popadooTranslations;
            const language = currentLanguage();

            return translations?.[language]?.[key]
                ?? translations?.en?.[key]
                ?? key;
        };

        const getLocalizedContactHref = () => {
            const url = new URL("contact.html", window.location.href);
            url.searchParams.set("package", customPackageId);
            url.searchParams.set("lang", currentLanguage());
            return `${url.pathname.substring(url.pathname.lastIndexOf("/") + 1)}${url.search}`;
        };

        const announceComparison = (message) => {
            if (comparisonStatus) {
                comparisonStatus.textContent = message;
            }
        };

        const announceCustom = (message) => {
            if (customStatus) {
                customStatus.textContent = message;
            }
        };

        const getPackageName = (packageData) => translate(packageData.nameKey);

        const loadComparedPackages = () => {
            try {
                const storedIds = JSON.parse(getStoredValue(compareStorageKey) ?? "[]");
                return Array.isArray(storedIds)
                    ? storedIds.filter((id, index, list) => packageMap.has(id) && list.indexOf(id) === index)
                    : [];
            } catch (error) {
                return [];
            }
        };

        const saveComparedPackages = () => {
            storeValue(compareStorageKey, JSON.stringify(comparedPackageIds));
        };

        const updateCardToggleState = () => {
            cards.forEach((card) => {
                const packageId = card.dataset.packageId;
                const isCompared = comparedPackageIds.includes(packageId);
                const toggle = card.querySelector("[data-package-toggle]");
                const hiddenText = toggle?.querySelector(".visually-hidden");
                const packageData = packageMap.get(packageId);
                const packageName = packageData ? getPackageName(packageData) : "";
                const labelKey = isCompared ? "packages.compareRemove" : "packages.compareAdd";
                const label = `${translate(labelKey)}: ${packageName}`;

                card.classList.toggle("is-compared", isCompared);
                toggle?.classList.toggle("is-active", isCompared);
                toggle?.setAttribute("aria-pressed", String(isCompared));
                toggle?.setAttribute("aria-label", label);
                toggle?.setAttribute("aria-controls", "comparison-list");

                if (hiddenText) {
                    hiddenText.textContent = label;
                }
            });
        };

        const renderComparisonItem = (packageData) => {
            const name = getPackageName(packageData);
            const item = document.createElement("article");
            item.className = "comparison-item";
            item.dataset.comparisonItem = packageData.id;

            const hiddenInput = document.createElement("input");
            hiddenInput.type = "hidden";
            hiddenInput.name = "comparePackages[]";
            hiddenInput.value = packageData.id;

            const header = document.createElement("div");
            header.className = "comparison-item-header";

            const content = document.createElement("div");
            const heading = document.createElement("h3");
            heading.textContent = name;
            const summary = document.createElement("p");
            summary.textContent = translate(packageData.summaryKey);
            content.append(heading, summary);

            const removeButton = document.createElement("button");
            removeButton.className = "comparison-remove";
            removeButton.type = "button";
            removeButton.dataset.packageRemove = packageData.id;
            removeButton.setAttribute("aria-label", `${translate("packages.compareRemove")} ${name}`);
            removeButton.innerHTML = '<span aria-hidden="true">×</span>';

            header.append(content, removeButton);

            const meta = document.createElement("dl");
            meta.className = "comparison-meta";
            const bestForWrapper = document.createElement("div");
            const bestForTerm = document.createElement("dt");
            bestForTerm.textContent = translate("packages.bestFor");
            const bestForDescription = document.createElement("dd");
            bestForDescription.textContent = translate(packageData.bestForKey);
            bestForWrapper.append(bestForTerm, bestForDescription);
            meta.append(bestForWrapper);

            item.append(hiddenInput, header, meta);
            return item;
        };

        const renderComparison = () => {
            updateCardToggleState();

            if (comparisonEmpty) {
                comparisonEmpty.hidden = comparedPackageIds.length > 0;
            }

            if (clearButton) {
                clearButton.disabled = comparedPackageIds.length === 0;
            }

            if (!comparisonList) {
                return;
            }

            comparisonList.textContent = "";
            comparedPackageIds
                .map((id) => packageMap.get(id))
                .filter(Boolean)
                .map(renderComparisonItem)
                .forEach((item) => comparisonList.append(item));
        };

        const toggleComparedPackage = (packageId) => {
            const packageData = packageMap.get(packageId);

            if (!packageData) {
                return;
            }

            if (comparedPackageIds.includes(packageId)) {
                comparedPackageIds = comparedPackageIds.filter((id) => id !== packageId);
                announceComparison(`${getPackageName(packageData)} ${translate("packages.statusRemoved")}`);
            } else {
                comparedPackageIds = [...comparedPackageIds, packageId];
                announceComparison(`${getPackageName(packageData)} ${translate("packages.statusAdded")}`);
            }

            saveComparedPackages();
            renderComparison();
        };

        const removeComparedPackage = (packageId) => {
            const packageData = packageMap.get(packageId);
            comparedPackageIds = comparedPackageIds.filter((id) => id !== packageId);
            saveComparedPackages();
            renderComparison();

            if (packageData) {
                announceComparison(`${getPackageName(packageData)} ${translate("packages.statusRemoved")}`);
            }
        };

        const clearComparison = () => {
            comparedPackageIds = [];
            saveComparedPackages();
            renderComparison();
            announceComparison(translate("packages.statusCleared"));
        };

        const getCharacteristicById = (characteristicId) => {
            const button = customOptionButtons.find((optionButton) => optionButton.dataset.customCharacteristic === characteristicId);

            return button
                ? {
                    id: characteristicId,
                    labelKey: button.dataset.characteristicLabelKey
                }
                : null;
        };

        const getCharacteristicName = (characteristic) => translate(characteristic.labelKey);

        const updateCustomOptionState = () => {
            customOptionButtons.forEach((button) => {
                const isSelected = selectedCharacteristics.includes(button.dataset.customCharacteristic);
                const label = button.dataset.characteristicLabelKey ? translate(button.dataset.characteristicLabelKey) : "";
                const action = isSelected ? translate("packages.customRemoveCharacteristic") : translate("packages.customAddCharacteristic");

                button.classList.toggle("is-selected", isSelected);
                button.setAttribute("aria-pressed", String(isSelected));
                button.setAttribute("aria-label", `${action}: ${label}`);
            });
        };

        const renderSelectedCharacteristic = (characteristic) => {
            const item = document.createElement("li");
            item.className = "custom-selected-item";

            const label = document.createElement("span");
            label.textContent = getCharacteristicName(characteristic);

            const removeButton = document.createElement("button");
            removeButton.className = "custom-selected-remove";
            removeButton.type = "button";
            removeButton.dataset.customRemove = characteristic.id;
            removeButton.setAttribute("aria-label", `${translate("packages.customRemoveCharacteristic")} ${getCharacteristicName(characteristic)}`);
            removeButton.innerHTML = '<span aria-hidden="true">×</span>';

            item.append(label, removeButton);
            return item;
        };

        const renderCustomPackage = () => {
            const selected = selectedCharacteristics.map(getCharacteristicById).filter(Boolean);
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
            selected.map(renderSelectedCharacteristic).forEach((item) => customSelectedList.append(item));
        };

        const saveCustomPackage = () => {
            const selected = selectedCharacteristics.map(getCharacteristicById).filter(Boolean);
            const payload = {
                id: customPackageId,
                nameKey: "packages.customPackageName",
                characteristics: selected,
                createdAt: new Date().toISOString()
            };

            storeValue(customPackageStorageKey, JSON.stringify(payload));
            storeValue(selectedPackageStorageKey, customPackageId);
        };

        const toggleCustomCharacteristic = (characteristicId) => {
            const characteristic = getCharacteristicById(characteristicId);

            if (!characteristic) {
                return;
            }

            if (selectedCharacteristics.includes(characteristicId)) {
                selectedCharacteristics = selectedCharacteristics.filter((id) => id !== characteristicId);
                announceCustom(`${getCharacteristicName(characteristic)} ${translate("packages.customStatusRemoved")}`);
            } else {
                selectedCharacteristics = [...selectedCharacteristics, characteristicId];
                announceCustom(`${getCharacteristicName(characteristic)} ${translate("packages.customStatusAdded")}`);
            }

            renderCustomPackage();
        };

        const removeCustomCharacteristic = (characteristicId) => {
            const characteristic = getCharacteristicById(characteristicId);
            selectedCharacteristics = selectedCharacteristics.filter((id) => id !== characteristicId);
            renderCustomPackage();

            if (characteristic) {
                announceCustom(`${getCharacteristicName(characteristic)} ${translate("packages.customStatusRemoved")}`);
            }
        };

        const clearCustomPackage = () => {
            selectedCharacteristics = [];
            renderCustomPackage();
            announceCustom(translate("packages.customStatusCleared"));

            if (customBookLink) {
                customBookLink.hidden = true;
            }
        };

        const finishCustomPackage = () => {
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
        };

        /* Direct listeners make the star buttons work even if nested icons receive the click target. */
        cards.forEach((card) => {
            const toggle = card.querySelector("[data-package-toggle]");
            toggle?.addEventListener("click", (event) => {
                event.preventDefault();
                toggleComparedPackage(toggle.dataset.packageId);
            });
        });

        comparisonList?.addEventListener("click", (event) => {
            const removeButton = event.target.closest("[data-package-remove]");

            if (removeButton) {
                removeComparedPackage(removeButton.dataset.packageRemove);
            }
        });

        clearButton?.addEventListener("click", clearComparison);

        document.addEventListener("click", (event) => {
            const selectLink = event.target.closest("[data-package-select]");

            if (selectLink) {
                storeValue(selectedPackageStorageKey, selectLink.dataset.packageSelect);
            }
        });

        customOptionButtons.forEach((button) => {
            button.addEventListener("click", () => {
                toggleCustomCharacteristic(button.dataset.customCharacteristic);
            });
        });

        customSelectedList?.addEventListener("click", (event) => {
            const removeButton = event.target.closest("[data-custom-remove]");

            if (removeButton) {
                removeCustomCharacteristic(removeButton.dataset.customRemove);
            }
        });

        customClearButton?.addEventListener("click", clearCustomPackage);
        customFinishButton?.addEventListener("click", finishCustomPackage);

        /* Re-render translated dynamic content when the shared language control changes. */
        document.addEventListener("popadoo:language-applied", () => {
            renderComparison();
            renderCustomPackage();
        });

        comparedPackageIds = loadComparedPackages();
        renderComparison();

        if (customForm) {
            renderCustomPackage();
        }
    });
})();
