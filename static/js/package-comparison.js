"use strict";

/*
 * Package comparison enhancement.
 *
 * The page remains navigable without JavaScript. This script adds comparison
 * controls and remembers the latest package selection in localStorage.
 */
(() => {
    const cards = Array.from(document.querySelectorAll("[data-package-card]"));
    const comparisonList = document.querySelector("#comparison-list");
    const comparisonEmpty = document.querySelector("#comparison-empty");
    const comparisonClear = document.querySelector("#comparison-clear");
    const comparisonStatus = document.querySelector("#comparison-status");

    if (cards.length === 0 || !comparisonList) {
        return;
    }

    const comparisonStorageKey = "popadoo-compare-packages";
    const selectedPackageStorageKey = "popadoo-selected-package";
    const packageMap = new Map();

    const safeRead = (key, fallback) => {
        try {
            return JSON.parse(window.localStorage.getItem(key)) ?? fallback;
        } catch (error) {
            return fallback;
        }
    };

    const safeWrite = (key, value) => {
        try {
            window.localStorage.setItem(key, JSON.stringify(value));
        } catch (error) {
            // Storage is optional; comparison still works during this visit.
        }
    };

    cards.forEach((card) => {
        const id = card.dataset.packageId;
        packageMap.set(id, {
            id,
            name: card.querySelector("h3")?.textContent.trim() || id,
            summary:
                card.querySelector(".package-card-content > p:not(.package-badge)")
                    ?.textContent.trim() || "",
        });
    });

    let selectedIds = safeRead(comparisonStorageKey, []).filter((id) =>
        packageMap.has(id)
    );

    const announce = (message) => {
        if (comparisonStatus) {
            comparisonStatus.textContent = message;
        }
    };

    const render = () => {
        comparisonList.replaceChildren();

        cards.forEach((card) => {
            const id = card.dataset.packageId;
            const button = card.querySelector("[data-package-toggle]");
            const isSelected = selectedIds.includes(id);

            card.classList.toggle("is-compared", isSelected);
            button?.classList.toggle("is-active", isSelected);
            button?.setAttribute("aria-pressed", String(isSelected));
        });

        selectedIds.forEach((id) => {
            const packageData = packageMap.get(id);
            const item = document.createElement("article");
            const copy = document.createElement("div");
            const heading = document.createElement("h3");
            const description = document.createElement("p");
            const removeButton = document.createElement("button");

            item.className = "comparison-item";
            heading.textContent = packageData.name;
            description.textContent = packageData.summary;
            removeButton.type = "button";
            removeButton.className = "comparison-remove";
            removeButton.dataset.packageRemove = id;
            removeButton.setAttribute(
                "aria-label",
                `Remove ${packageData.name} from comparison`
            );
            removeButton.textContent = "×";

            copy.append(heading, description);
            item.append(copy, removeButton);
            comparisonList.append(item);
        });

        if (comparisonEmpty) {
            comparisonEmpty.hidden = selectedIds.length > 0;
        }

        if (comparisonClear) {
            comparisonClear.disabled = selectedIds.length === 0;
        }

        safeWrite(comparisonStorageKey, selectedIds);
    };

    document.addEventListener("click", (event) => {
        const toggle = event.target.closest("[data-package-toggle]");
        const remove = event.target.closest("[data-package-remove]");
        const selectLink = event.target.closest("[data-package-select]");

        if (toggle) {
            const id = toggle.dataset.packageId;
            const packageData = packageMap.get(id);
            const isSelected = selectedIds.includes(id);

            selectedIds = isSelected
                ? selectedIds.filter((selectedId) => selectedId !== id)
                : [...selectedIds, id];

            render();
            announce(
                `${packageData.name} ${isSelected ? "removed from" : "added to"} comparison.`
            );
            return;
        }

        if (remove) {
            const id = remove.dataset.packageRemove;
            selectedIds = selectedIds.filter((selectedId) => selectedId !== id);
            render();
            announce("Package removed from comparison.");
            return;
        }

        if (selectLink) {
            try {
                window.localStorage.setItem(
                    selectedPackageStorageKey,
                    selectLink.dataset.packageSelect
                );
            } catch (error) {
                // The URL query parameter still carries the selected package.
            }
        }
    });

    comparisonClear?.addEventListener("click", () => {
        selectedIds = [];
        render();
        announce("Comparison cleared.");
    });

    render();
})();
