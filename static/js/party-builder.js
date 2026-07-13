"use strict";

/*
 * This script improves the multi-step party builder with live prices, keyboard support, safe formatting, and submit protection.
 * These comments explain the browser-side steps without changing the JavaScript behaviour.
 */

/*
 * Multi-step Popadoo checkout enhancements.
 *
 * All essential validation remains server-side through Django forms. This file
 * adds live cart pricing, keyboard navigation, card-number formatting, and
 * double-submit protection without making JavaScript mandatory.
 */
(() => {
    const currencyFormatter = new Intl.NumberFormat("en-IE", {
        style: "currency",
        currency: "EUR",
        minimumFractionDigits: 2,
    });

    // This function converts a price stored in HTML into a safe number for the live total.
    const toNumber = (value) => Number.parseFloat(value || "0") || 0;

    const optionsForm = document.querySelector("[data-party-options-form]");
    if (optionsForm) {
        const tierRadios = Array.from(
            optionsForm.querySelectorAll("[data-tier-radio]")
        );
        const addonCheckboxes = Array.from(
            optionsForm.querySelectorAll("[data-addon-checkbox]")
        );
        const tierGrid = optionsForm.querySelector("[data-tier-grid]");
        const addonGrid = optionsForm.querySelector("[data-addon-grid]");
        const selectedTierLabel = document.querySelector("#selected-tier-label");
        const selectedTierPrice = document.querySelector("#selected-tier-price");
        const addonSummary = document.querySelector("#selected-addon-summary");
        const emptySummary = document.querySelector("#summary-empty");
        const totalOutput = document.querySelector("#party-total");
        const liveStatus = document.querySelector("#builder-live-status");

        // This function refreshes choice labels so the page matches the latest user choice.
        const updateChoiceLabels = () => {
            tierRadios.forEach((radio) => {
                const action = radio
                    .closest(".tier-option")
                    ?.querySelector("[data-tier-action]");
                if (action) {
                    action.textContent = radio.checked
                        ? "Selected"
                        : "Choose this group size";
                }
            });

            addonCheckboxes.forEach((checkbox) => {
                const action = checkbox
                    .closest(".addon-option")
                    ?.querySelector("[data-addon-action]");
                if (action) {
                    action.textContent = checkbox.checked
                        ? "Added — remove"
                        : "Add experience";
                }
            });
        };

        // This function rebuilds the visible cart from the current data.
        const renderCart = ({ announce = false } = {}) => {
            const selectedTier = tierRadios.find((radio) => radio.checked);
            const selectedAddons = addonCheckboxes.filter(
                (checkbox) => checkbox.checked
            );
            const tierPrice = toNumber(selectedTier?.dataset.tierPrice);
            const addonTotal = selectedAddons.reduce(
                (total, checkbox) => total + toNumber(checkbox.dataset.addonPrice),
                0
            );
            const total = tierPrice + addonTotal;

            if (selectedTierLabel) {
                selectedTierLabel.textContent =
                    selectedTier?.dataset.tierLabel || "Select a group size";
            }
            if (selectedTierPrice) {
                selectedTierPrice.textContent = selectedTier
                    ? currencyFormatter.format(tierPrice)
                    : "—";
            }
            if (totalOutput) {
                totalOutput.textContent = selectedTier
                    ? currencyFormatter.format(total)
                    : "—";
            }

            if (addonSummary) {
                addonSummary.replaceChildren();
                selectedAddons.forEach((checkbox) => {
                    const item = document.createElement("li");
                    const name = document.createElement("span");
                    const price = document.createElement("strong");
                    item.className = "summary-addon-item";
                    name.textContent = checkbox.dataset.addonName;
                    price.textContent = currencyFormatter.format(
                        toNumber(checkbox.dataset.addonPrice)
                    );
                    item.append(name, price);
                    addonSummary.append(item);
                });
            }

            if (emptySummary) {
                emptySummary.hidden = selectedAddons.length > 0;
            }

            updateChoiceLabels();

            if (announce && liveStatus) {
                liveStatus.textContent = selectedTier
                    ? `Cart updated. ${selectedAddons.length} optional experiences. Total ${currencyFormatter.format(total)}.`
                    : "Choose a guest bracket to continue.";
            }
        };

        // This function lets arrow, Home, and End keys move between related option controls.
        const addKeyboardNavigation = (container, controls) => {
            container?.addEventListener("keydown", (event) => {
                const currentIndex = controls.indexOf(event.target);
                if (currentIndex === -1) {
                    return;
                }

                const destinations = {
                    ArrowRight: currentIndex + 1,
                    ArrowDown: currentIndex + 1,
                    ArrowLeft: currentIndex - 1,
                    ArrowUp: currentIndex - 1,
                    Home: 0,
                    End: controls.length - 1,
                };

                if (!(event.key in destinations)) {
                    return;
                }

                event.preventDefault();
                const destination =
                    (destinations[event.key] + controls.length) % controls.length;
                controls[destination]?.focus();
            });
        };

        tierRadios.forEach((radio) => {
            radio.addEventListener("change", () => renderCart({ announce: true }));
        });
        const recommendationSection = document.querySelector("[data-recommendations]");
        const recommendationList = recommendationSection?.querySelector("[data-recommendation-list]");

        const renderRecommendations = (items) => {
            if (!recommendationList) return;
            recommendationList.replaceChildren();
            if (!items.length) {
                const empty = document.createElement("p");
                empty.textContent = "No additional suggestions are available yet.";
                recommendationList.append(empty);
                return;
            }
            items.forEach((item) => {
                const card = document.createElement("article");
                card.className = "recommendation-card";
                const heading = document.createElement("h3");
                const description = document.createElement("p");
                const reason = document.createElement("p");
                const price = document.createElement("p");
                const button = document.createElement("button");
                heading.textContent = item.name;
                description.textContent = item.short_description;
                reason.className = "recommendation-reason";
                reason.textContent = item.reason;
                price.textContent = currencyFormatter.format(toNumber(item.price));
                button.type = "button";
                button.className = "button button-outline";
                button.textContent = "Select this experience";
                button.addEventListener("click", () => {
                    const checkbox = optionsForm.querySelector(`[data-addon-checkbox][value='${CSS.escape(String(item.id))}']`);
                    if (checkbox && !checkbox.checked) {
                        checkbox.checked = true;
                        checkbox.dispatchEvent(new Event("change", { bubbles: true }));
                    }
                    checkbox?.focus();
                });
                card.append(heading, description, reason, price, button);
                recommendationList.append(card);
            });
        };

        const refreshRecommendations = async () => {
            if (!recommendationSection || !recommendationList) return;
            const url = new URL(recommendationSection.dataset.endpoint, window.location.origin);
            url.searchParams.set("package", recommendationSection.dataset.packageId);
            addonCheckboxes.filter((item) => item.checked).forEach((item) => url.searchParams.append("addons", item.value));
            try {
                const response = await fetch(url, { headers: { Accept: "application/json" } });
                if (response.ok) renderRecommendations((await response.json()).recommendations || []);
            } catch (_error) {
                // Server-rendered suggestions remain available when live updates fail.
            }
        };

        addonCheckboxes.forEach((checkbox) => {
            checkbox.addEventListener("change", () => {
                renderCart({ announce: true });
                refreshRecommendations();
            });
        });
        addKeyboardNavigation(tierGrid, tierRadios);
        addKeyboardNavigation(addonGrid, addonCheckboxes);
        renderCart();
    }

    const cardNumberInput = document.querySelector("[data-card-number]");
    cardNumberInput?.addEventListener("input", () => {
        const digits = cardNumberInput.value.replace(/\D/g, "").slice(0, 19);
        cardNumberInput.value = digits.replace(/(.{4})/g, "$1 ").trim();
    });

    const paymentForm = document.querySelector("[data-payment-form]");
    paymentForm?.addEventListener("submit", () => {
        const submitButton = paymentForm.querySelector("[data-checkout-submit]");
        if (submitButton) {
            submitButton.disabled = true;
            submitButton.textContent = "Completing simulation…";
        }
    });
})();
