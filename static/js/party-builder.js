"use strict";

/*
 * The server remains responsible for validation and pricing. This file only
 * makes the builder faster to explore by updating visible choices and totals.
 */
(() => {
    const currencyFormatter = new Intl.NumberFormat("en-IE", {
        style: "currency",
        currency: "EUR",
        minimumFractionDigits: 2,
    });
    const toNumber = (value) => Number.parseFloat(value || "0") || 0;
    const activeLanguage = () => document.documentElement.lang || "en";
    const translate = (key) => {
        const language = activeLanguage();
        return window.popadooTranslations?.[language]?.[key]
            ?? window.popadooTranslations?.en?.[key]
            ?? key;
    };
    const optionalTranslation = (key) => {
        const language = activeLanguage();
        return window.popadooTranslations?.[language]?.[key]
            ?? window.popadooTranslations?.en?.[key]
            ?? null;
    };
    const interpolate = (template, values = {}) => Object.entries(values).reduce(
        (text, [name, value]) => text.replaceAll(`{${name}}`, String(value ?? "")),
        template
    );
    const catalogueText = (kind, slug, field, fallback = "") => {
        if (!slug) return fallback;
        return optionalTranslation(`catalogue.${kind}.${slug}.${field}`) ?? fallback;
    };
    const recommendationReasonText = (element) => {
        const key = element.dataset.recommendationReasonKey;
        if (!key) return element.textContent;
        const addonName = catalogueText(
            "addon",
            element.dataset.recommendationAddonSlug,
            "name",
            element.dataset.recommendationAddonName
        );
        const packageName = catalogueText(
            "package",
            element.dataset.recommendationPackageSlug,
            "name",
            element.dataset.recommendationPackageName
        );
        return interpolate(translate(key), {
            addon: addonName,
            package: packageName,
            count: element.dataset.recommendationCount,
        });
    };
    const applyBuilderTranslations = (root = document) => {
        root.querySelectorAll("[data-catalogue-i18n]").forEach((element) => {
            if (!element.dataset.catalogueOriginal) {
                element.dataset.catalogueOriginal = element.textContent;
            }
            element.textContent = optionalTranslation(element.dataset.catalogueI18n)
                ?? element.dataset.catalogueOriginal;
        });
        root.querySelectorAll("[data-recommendation-reason-key]").forEach((element) => {
            element.textContent = recommendationReasonText(element);
        });
        root.querySelectorAll("[data-i18n-aria-label][data-i18n-value-rating]").forEach((element) => {
            element.setAttribute("aria-label", interpolate(translate(element.dataset.i18nAriaLabel), {
                rating: element.dataset.i18nValueRating,
                count: element.dataset.i18nValueCount,
            }));
        });
    };

    const optionsForm = document.querySelector("[data-party-options-form]");
    if (optionsForm) {
        const packageRadios = Array.from(optionsForm.querySelectorAll("[data-package-radio]"));
        const addonCheckboxes = Array.from(optionsForm.querySelectorAll("[data-addon-checkbox]"));
        const addonOptions = Array.from(optionsForm.querySelectorAll("[data-addon-option]"));
        const recommendationSection = document.querySelector("[data-recommendations]");
        const recommendationList = recommendationSection?.querySelector("[data-recommendation-list]");
        const selectedPackageName = document.querySelector("[data-selected-package-name]");
        const selectedPackageCapacity = document.querySelector("#selected-package-capacity");
        const selectedPackagePrice = document.querySelector("#selected-package-price");
        const addonSummary = document.querySelector("#selected-addon-summary");
        const emptySummary = document.querySelector("#summary-empty");
        const totalOutput = document.querySelector("#party-total");
        const liveStatus = document.querySelector("#builder-live-status");
        let recommendationController = null;

        const selectedPackage = () => packageRadios.find((radio) => radio.checked);
        const selectedPackageId = () => selectedPackage()?.value || "";

        const updateChoiceLabels = () => {
            packageRadios.forEach((radio) => {
                const action = radio.closest(".package-option")?.querySelector("[data-package-action]");
                if (action) {
                    const key = radio.checked ? "builder.selectedPackage" : "builder.choosePackageAction";
                    action.dataset.i18n = key;
                    action.textContent = translate(key);
                }
            });
            addonCheckboxes.forEach((checkbox) => {
                const action = checkbox.closest(".addon-option")?.querySelector("[data-addon-action]");
                if (action) {
                    const key = checkbox.checked ? "builder.addedRemove" : "builder.addExperience";
                    action.dataset.i18n = key;
                    action.textContent = translate(key);
                }
            });
        };

        const renderCart = ({ announce = false } = {}) => {
            const packageChoice = selectedPackage();
            const selectedAddons = addonCheckboxes.filter((checkbox) => checkbox.checked);
            const packagePrice = toNumber(packageChoice?.dataset.packagePrice);
            const addonTotal = selectedAddons.reduce(
                (total, checkbox) => total + toNumber(checkbox.dataset.addonPrice),
                0
            );
            const total = packagePrice + addonTotal;

            if (recommendationSection) recommendationSection.dataset.packageId = selectedPackageId();
            if (selectedPackageName) {
                selectedPackageName.textContent = packageChoice
                    ? catalogueText("package", packageChoice.dataset.packageSlug, "name", packageChoice.dataset.packageName)
                    : "";
                selectedPackageName.dataset.packageSlug = packageChoice?.dataset.packageSlug || "";
            }
            if (selectedPackageCapacity) {
                selectedPackageCapacity.textContent = packageChoice
                    ? translate("builder.upToChildren").replace(
                        "{count}",
                        packageChoice.dataset.packageCapacity
                    )
                    : translate("builder.choosePackage");
            }
            if (selectedPackagePrice) selectedPackagePrice.textContent = packageChoice ? currencyFormatter.format(packagePrice) : "—";
            if (totalOutput) totalOutput.textContent = packageChoice ? currencyFormatter.format(total) : "—";

            if (addonSummary) {
                addonSummary.replaceChildren();
                selectedAddons.forEach((checkbox) => {
                    const item = document.createElement("li");
                    const name = document.createElement("span");
                    const price = document.createElement("strong");
                    item.className = "summary-addon-item";
                    name.textContent = catalogueText(
                        "addon",
                        checkbox.dataset.addonSlug,
                        "name",
                        checkbox.dataset.addonName
                    );
                    price.textContent = currencyFormatter.format(toNumber(checkbox.dataset.addonPrice));
                    item.append(name, price);
                    addonSummary.append(item);
                });
            }
            if (emptySummary) emptySummary.hidden = selectedAddons.length > 0;
            updateChoiceLabels();
            if (announce && liveStatus) {
                liveStatus.textContent = packageChoice
                    ? translate("builder.partyUpdated")
                        .replace("{count}", String(selectedAddons.length))
                        .replace("{total}", currencyFormatter.format(total))
                    : translate("builder.choosePackage");
            }
        };

        const addKeyboardNavigation = (container, controls) => {
            container?.addEventListener("keydown", (event) => {
                const visibleControls = controls.filter((control) => !control.closest("[hidden]"));
                const currentIndex = visibleControls.indexOf(event.target);
                if (currentIndex === -1) return;
                const destinations = {
                    ArrowRight: currentIndex + 1, ArrowDown: currentIndex + 1,
                    ArrowLeft: currentIndex - 1, ArrowUp: currentIndex - 1,
                    Home: 0, End: visibleControls.length - 1,
                };
                if (!(event.key in destinations)) return;
                event.preventDefault();
                const destination = (destinations[event.key] + visibleControls.length) % visibleControls.length;
                visibleControls[destination]?.focus();
            });
        };

        const renderRecommendations = (items) => {
            if (!recommendationList) return;
            recommendationList.replaceChildren();
            if (!items.length) {
                const empty = document.createElement("p");
                empty.dataset.i18n = "builder.noAdditionalSuggestions";
                empty.textContent = translate("builder.noAdditionalSuggestions");
                recommendationList.append(empty);
                return;
            }
            items.forEach((item) => {
                const card = document.createElement("article");
                card.className = "recommendation-card";
                const content = document.createElement("div");
                const footer = document.createElement("div");
                const heading = document.createElement("h3");
                const description = document.createElement("p");
                const reason = document.createElement("p");
                const price = document.createElement("strong");
                const button = document.createElement("button");
                content.className = "recommendation-card-content";
                footer.className = "recommendation-card-footer";
                heading.dataset.catalogueI18n = `catalogue.addon.${item.slug}.name`;
                heading.textContent = catalogueText("addon", item.slug, "name", item.name);
                description.className = "recommendation-description";
                description.dataset.catalogueI18n = `catalogue.addon.${item.slug}.description`;
                description.textContent = catalogueText("addon", item.slug, "description", item.short_description);
                reason.className = "recommendation-reason";
                reason.dataset.recommendationReasonKey = item.reason_key || "";
                reason.dataset.recommendationCount = item.reason_values?.count || "";
                reason.dataset.recommendationAddonName = item.reason_values?.addon_name || "";
                reason.dataset.recommendationAddonSlug = item.reason_values?.addon_slug || "";
                reason.dataset.recommendationPackageName = item.reason_values?.package_name || "";
                reason.dataset.recommendationPackageSlug = item.reason_values?.package_slug || "";
                reason.textContent = item.reason_key ? recommendationReasonText(reason) : item.reason;
                price.className = "recommendation-price";
                price.textContent = currencyFormatter.format(toNumber(item.price));
                button.type = "button";
                button.className = "button button-outline recommendation-action";
                button.dataset.i18n = "builder.selectExperience";
                button.textContent = translate("builder.selectExperience");
                button.addEventListener("click", () => {
                    const checkbox = optionsForm.querySelector(`[data-addon-checkbox][value='${CSS.escape(String(item.id))}']`);
                    if (checkbox && !checkbox.checked) {
                        checkbox.checked = true;
                        checkbox.dispatchEvent(new Event("change", { bubbles: true }));
                    }
                    checkbox?.focus();
                });
                content.append(heading, description, reason);
                footer.append(price, button);
                card.append(content, footer);
                recommendationList.append(card);
                applyBuilderTranslations(card);
            });
        };

        const refreshRecommendations = async () => {
            if (!recommendationSection || !recommendationList) return;
            recommendationController?.abort();
            recommendationController = new AbortController();
            const url = new URL(recommendationSection.dataset.endpoint, window.location.origin);
            url.searchParams.set("package", selectedPackageId());
            addonCheckboxes.filter((item) => item.checked).forEach((item) => url.searchParams.append("addons", item.value));
            try {
                const response = await fetch(url, { headers: { Accept: "application/json" }, signal: recommendationController.signal });
                if (response.ok) renderRecommendations((await response.json()).recommendations || []);
            } catch (error) {
                if (error.name !== "AbortError") {
                    // Server-rendered suggestions remain usable when the network is unavailable.
                }
            }
        };

        packageRadios.forEach((radio) => radio.addEventListener("change", () => {
            renderCart({ announce: true });
            refreshRecommendations();
        }));
        addonCheckboxes.forEach((checkbox) => checkbox.addEventListener("change", () => {
            renderCart({ announce: true });
            refreshRecommendations();
        }));

        const searchInput = optionsForm.querySelector("[data-addon-search]");
        const filterButtons = Array.from(optionsForm.querySelectorAll("[data-addon-filter]"));
        const filterStatus = optionsForm.querySelector("[data-addon-filter-status]");
        const filterEmpty = optionsForm.querySelector("[data-addon-filter-empty]");
        let activeCategory = "all";
        const applyAddonFilter = () => {
            const term = (searchInput?.value || "").trim().toLocaleLowerCase();
            let visibleCount = 0;
            addonOptions.forEach((option) => {
                const slug = option.querySelector("[data-addon-checkbox]")?.dataset.addonSlug || "";
                const translatedSearch = [
                    option.dataset.addonSearch,
                    catalogueText("addon", slug, "name"),
                    catalogueText("addon", slug, "description"),
                    optionalTranslation(`catalogue.category.${option.dataset.addonCategory}`),
                ].filter(Boolean).join(" ").toLocaleLowerCase();
                const matchesText = !term || translatedSearch.includes(term);
                const matchesCategory = activeCategory === "all" || option.dataset.addonCategory === activeCategory;
                option.hidden = !(matchesText && matchesCategory);
                if (!option.hidden) visibleCount += 1;
            });
            if (filterStatus) {
                const key = visibleCount === 1 ? "builder.experienceShown" : "builder.experiencesShown";
                filterStatus.textContent = translate(key).replace("{count}", String(visibleCount));
            }
            if (filterEmpty) filterEmpty.hidden = visibleCount > 0;
        };
        searchInput?.addEventListener("input", applyAddonFilter);
        filterButtons.forEach((button) => button.addEventListener("click", () => {
            activeCategory = button.dataset.addonFilter;
            filterButtons.forEach((item) => {
                const active = item === button;
                item.classList.toggle("active", active);
                item.setAttribute("aria-pressed", String(active));
            });
            applyAddonFilter();
        }));

        addKeyboardNavigation(optionsForm.querySelector("[data-package-grid]"), packageRadios);
        addKeyboardNavigation(optionsForm.querySelector("[data-addon-grid]"), addonCheckboxes);
        document.addEventListener("popadoo:language-applied", () => {
            applyBuilderTranslations();
            applyAddonFilter();
            renderCart();
        });
        applyBuilderTranslations();
        applyAddonFilter();
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
            submitButton.textContent = translate("builder.completingSimulation");
        }
    });
})();
