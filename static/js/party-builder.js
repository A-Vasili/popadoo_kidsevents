"use strict";

/*
 * Accessible client-side enhancement for the Django party builder.
 *
 * The browser provides immediate feedback, while Django recalculates every
 * price from database records during submission. Client totals are never
 * trusted by the server.
 */
(() => {
    const form = document.querySelector("[data-party-builder]");

    if (!form) {
        return;
    }

    const addonGrid = form.querySelector("[data-addon-grid]");
    const addonCheckboxes = Array.from(
        form.querySelectorAll("[data-addon-checkbox]")
    );
    const summaryList = form.querySelector("#selected-addon-summary");
    const summaryEmpty = form.querySelector("#summary-empty");
    const totalOutput = form.querySelector("#party-total");
    const liveStatus = form.querySelector("#builder-live-status");
    const currency = form.dataset.currency || "EUR";
    const basePrice = Number.parseFloat(form.dataset.basePrice || "0");

    const currencyFormatter = new Intl.NumberFormat("el-GR", {
        style: "currency",
        currency,
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    });

    const parsePrice = (checkbox) => {
        const value = Number.parseFloat(checkbox.dataset.addonPrice || "0");
        return Number.isFinite(value) ? value : 0;
    };

    const selectedCheckboxes = () => {
        return addonCheckboxes.filter((checkbox) => checkbox.checked);
    };

    const setActionText = (checkbox) => {
        const card = checkbox.nextElementSibling;
        const action = card?.querySelector("[data-addon-action]");

        if (!action) {
            return;
        }

        action.textContent = checkbox.checked
            ? "Added — remove"
            : "Add experience";
    };

    const createSummaryItem = (checkbox) => {
        const item = document.createElement("li");
        const name = document.createElement("span");
        const price = document.createElement("strong");

        item.className = "summary-addon-item";
        name.textContent = checkbox.dataset.addonName || "Experience";
        price.textContent = currencyFormatter.format(parsePrice(checkbox));

        item.append(name, price);
        return item;
    };

    const renderSummary = ({ announce = false, changedCheckbox = null } = {}) => {
        const selected = selectedCheckboxes();
        const addonTotal = selected.reduce(
            (total, checkbox) => total + parsePrice(checkbox),
            0
        );
        const total = basePrice + addonTotal;

        addonCheckboxes.forEach(setActionText);
        summaryList.replaceChildren(...selected.map(createSummaryItem));
        summaryEmpty.hidden = selected.length > 0;
        totalOutput.value = currencyFormatter.format(total);
        totalOutput.textContent = currencyFormatter.format(total);

        if (announce && liveStatus) {
            const name = changedCheckbox?.dataset.addonName || "Experience";
            const action = changedCheckbox?.checked ? "added" : "removed";
            liveStatus.textContent = `${name} ${action}. Estimated total ${currencyFormatter.format(total)}.`;
        }
    };

    const focusCheckbox = (index) => {
        if (addonCheckboxes.length === 0) {
            return;
        }

        const normalizedIndex =
            (index + addonCheckboxes.length) % addonCheckboxes.length;
        addonCheckboxes[normalizedIndex].focus();
    };

    const handleGridKeyboard = (event) => {
        const currentIndex = addonCheckboxes.indexOf(event.target);

        if (currentIndex === -1) {
            return;
        }

        const navigationKeys = {
            ArrowRight: currentIndex + 1,
            ArrowDown: currentIndex + 1,
            ArrowLeft: currentIndex - 1,
            ArrowUp: currentIndex - 1,
            Home: 0,
            End: addonCheckboxes.length - 1,
        };

        if (!(event.key in navigationKeys)) {
            return;
        }

        event.preventDefault();
        focusCheckbox(navigationKeys[event.key]);
    };

    addonCheckboxes.forEach((checkbox) => {
        checkbox.addEventListener("change", () => {
            renderSummary({ announce: true, changedCheckbox: checkbox });
        });
    });

    addonGrid?.addEventListener("keydown", handleGridKeyboard);

    form.addEventListener("submit", () => {
        const submitButton = form.querySelector('button[type="submit"]');

        if (submitButton) {
            submitButton.disabled = true;
            submitButton.textContent = "Saving your request…";
        }
    });

    renderSummary();
})();
