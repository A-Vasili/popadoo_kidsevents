"use strict";

/*
 * Dynamic package comparison for packages.html.
 * Users can add/remove package cards with the star button, remove individual
 * comparison items, clear the whole form, and send the most recent package
 * selection into the booking form via localStorage plus the package URL query.
 */
(() => {
    const compareStorageKey = "popadoo-compare-packages";
    const selectedPackageStorageKey = "popadoo-selected-package";
    const cards = Array.from(document.querySelectorAll("[data-package-card]"));
    const compareForm = document.querySelector("#package-comparison-form");
    const comparisonList = document.querySelector("#comparison-list");
    const comparisonEmpty = document.querySelector("#comparison-empty");
    const comparisonStatus = document.querySelector("#comparison-status");
    const clearButton = document.querySelector("#comparison-clear");

    if (!compareForm || cards.length === 0) {
        return;
    }

    const packages = new Map(cards.map((card) => [
        card.dataset.packageId,
        {
            id: card.dataset.packageId,
            nameKey: card.dataset.packageNameKey,
            summaryKey: card.dataset.packageSummaryKey,
            bestForKey: card.dataset.packageBestForKey
        }
    ]));

    let selectedPackageIds = [];

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
            /* The comparison still works for the current page if storage is blocked. */
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

    const loadSelectedPackages = () => {
        try {
            const storedIds = JSON.parse(getStoredValue(compareStorageKey) ?? "[]");
            return Array.isArray(storedIds)
                ? storedIds.filter((id, index, list) => packages.has(id) && list.indexOf(id) === index)
                : [];
        } catch (error) {
            return [];
        }
    };

    const saveSelectedPackages = () => {
        storeValue(compareStorageKey, JSON.stringify(selectedPackageIds));
    };

    const announce = (message) => {
        if (comparisonStatus) {
            comparisonStatus.textContent = message;
        }
    };

    const getPackageName = (packageData) => translate(packageData.nameKey);

    const updateCardToggles = () => {
        cards.forEach((card) => {
            const packageId = card.dataset.packageId;
            const isSelected = selectedPackageIds.includes(packageId);
            const toggle = card.querySelector("[data-package-toggle]");
            const hiddenText = toggle?.querySelector(".visually-hidden");
            const packageData = packages.get(packageId);
            const packageName = packageData ? getPackageName(packageData) : "";
            const labelKey = isSelected ? "packages.compareRemove" : "packages.compareAdd";
            const label = `${translate(labelKey)}: ${packageName}`;

            card.classList.toggle("is-compared", isSelected);
            toggle?.setAttribute("aria-pressed", String(isSelected));
            toggle?.setAttribute("aria-label", label);

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
        updateCardToggles();

        if (comparisonEmpty) {
            comparisonEmpty.hidden = selectedPackageIds.length > 0;
        }

        if (clearButton) {
            clearButton.disabled = selectedPackageIds.length === 0;
        }

        if (!comparisonList) {
            return;
        }

        comparisonList.replaceChildren(
            ...selectedPackageIds
                .map((id) => packages.get(id))
                .filter(Boolean)
                .map(renderComparisonItem)
        );
    };

    const togglePackage = (packageId) => {
        const packageData = packages.get(packageId);

        if (!packageData) {
            return;
        }

        if (selectedPackageIds.includes(packageId)) {
            selectedPackageIds = selectedPackageIds.filter((id) => id !== packageId);
            announce(`${getPackageName(packageData)} ${translate("packages.statusRemoved")}`);
        } else {
            selectedPackageIds = [...selectedPackageIds, packageId];
            announce(`${getPackageName(packageData)} ${translate("packages.statusAdded")}`);
        }

        saveSelectedPackages();
        renderComparison();
    };

    const removePackage = (packageId) => {
        const packageData = packages.get(packageId);
        selectedPackageIds = selectedPackageIds.filter((id) => id !== packageId);
        saveSelectedPackages();
        renderComparison();

        if (packageData) {
            announce(`${getPackageName(packageData)} ${translate("packages.statusRemoved")}`);
        }
    };

    const clearComparison = () => {
        selectedPackageIds = [];
        saveSelectedPackages();
        renderComparison();
        announce(translate("packages.statusCleared"));
    };

    /* Event delegation supports any future package cards added to the grid. */
    document.addEventListener("click", (event) => {
        const toggle = event.target.closest("[data-package-toggle]");
        const removeButton = event.target.closest("[data-package-remove]");
        const selectLink = event.target.closest("[data-package-select]");

        if (toggle) {
            togglePackage(toggle.dataset.packageId);
        }

        if (removeButton) {
            removePackage(removeButton.dataset.packageRemove);
        }

        if (selectLink) {
            storeValue(selectedPackageStorageKey, selectLink.dataset.packageSelect);
        }
    });

    clearButton?.addEventListener("click", clearComparison);

    document.addEventListener("popadoo:language-applied", renderComparison);

    selectedPackageIds = loadSelectedPackages();
    renderComparison();
})();
