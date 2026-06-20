"use strict";

(() => {
    const translations = window.popadooTranslations;
    const supportedLanguages = Object.keys(translations ?? { en: {} });
    const languageStorageKey = "popadoo-language";
    const themeStorageKey = "popadoo-theme";
    const selectedPackageStorageKey = "popadoo-selected-package";
    const customPackageStorageKey = "popadoo-custom-package";
    const customPackageId = "custom-package";
    const navigationBreakpoint = window.matchMedia("(max-width: 72rem)");
    const navigationToggle = document.querySelector(".site-navigation-toggle");
    const navigationMenu = document.querySelector("#primary-navigation");
    const languageSelector = document.querySelector("#language-selector");
    const themeToggle = document.querySelector("#theme-toggle");
    const themeStatus = document.querySelector("[data-theme-status]");
    const metaDescription = document.querySelector('meta[name="description"]');
    const themeColorMeta = document.querySelector('meta[name="theme-color"]');
    const bookingForm = document.querySelector("#booking-form");
    const bookingConfirmation = document.querySelector("#booking-confirmation");
    const bookingClearButton = document.querySelector("#booking-clear");
    const bookingName = document.querySelector("#booking-name");
    const bookingEmail = document.querySelector("#booking-email");
    const bookingPhone = document.querySelector("#booking-phone");
    const bookingDate = document.querySelector("#booking-date");
    const bookingTime = document.querySelector("#booking-time");
    const bookingGuests = document.querySelector("#booking-guest-count");
    const bookingPackage = document.querySelector("#booking-package");
    const bookingDetails = document.querySelector("#booking-details");
    const bookingPostalCode = document.querySelector("#booking-postal-code");

    let currentLanguage = "en";

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
            /* Preferences still work for the current page when storage is blocked. */
        }
    };

    const isSupportedLanguage = (language) => supportedLanguages.includes(language);

    const hasSelectOption = (selectElement, value) => {
        return Boolean(selectElement)
            && Array.from(selectElement.options).some((option) => option.value === value);
    };

    const getUrlLanguage = () => {
        const language = new URLSearchParams(window.location.search).get("lang");
        return isSupportedLanguage(language) ? language : null;
    };

    const getUrlPackage = () => {
        const packageId = new URLSearchParams(window.location.search).get("package");
        return packageId && hasSelectOption(bookingPackage, packageId)
            ? packageId
            : null;
    };

    const translate = (key) => {
        return translations?.[currentLanguage]?.[key]
            ?? translations?.en?.[key]
            ?? key;
    };

    const updateNavigationToggleLabel = () => {
        if (!navigationToggle) {
            return;
        }

        const isOpen = navigationToggle.getAttribute("aria-expanded") === "true";
        navigationToggle.setAttribute(
            "aria-label",
            translate(isOpen ? "nav.closeMenu" : "nav.openMenu")
        );
    };

    const updateThemeControl = () => {
        if (!themeToggle) {
            return;
        }

        const isDark = document.documentElement.getAttribute("data-theme") === "dark";
        themeToggle.setAttribute("aria-checked", String(isDark));
        themeToggle.setAttribute(
            "aria-label",
            translate(isDark ? "theme.switchToLight" : "theme.switchToDark")
        );

        if (themeStatus) {
            themeStatus.textContent = translate(isDark ? "theme.dark" : "theme.light");
        }

        if (themeColorMeta) {
            themeColorMeta.setAttribute("content", isDark ? "#15111c" : "#fff9fc");
        }
    };

    const shouldLocalizeHref = (href) => {
        return href
            && !href.startsWith("#")
            && !href.startsWith("mailto:")
            && !href.startsWith("tel:")
            && !href.startsWith("javascript:");
    };

    const getRelativeLocalizedHref = (url) => {
        const fileName = url.pathname.substring(url.pathname.lastIndexOf("/") + 1) || "index.html";
        return `${fileName}${url.search}${url.hash}`;
    };

    /*
     * Keep language state portable between pages.
     * localStorage remains the main preference store, while a lang query
     * parameter is added to internal links as a fallback for browsers that block
     * storage or users who open pages directly from a translated URL.
     */
    const updateInternalLanguageLinks = () => {
        document.querySelectorAll("a[href]").forEach((link) => {
            const originalHref = link.getAttribute("href");

            if (!shouldLocalizeHref(originalHref)) {
                return;
            }

            const url = new URL(originalHref, window.location.href);

            if (url.origin !== window.location.origin || !url.pathname.endsWith(".html")) {
                return;
            }

            url.searchParams.set("lang", currentLanguage);
            link.setAttribute("href", getRelativeLocalizedHref(url));
        });
    };

    const updateCurrentUrlLanguage = () => {
        const url = new URL(window.location.href);
        url.searchParams.set("lang", currentLanguage);
        window.history.replaceState({}, "", getRelativeLocalizedHref(url));
    };

    const formatDateForInput = (date) => {
        const localDate = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
        return localDate.toISOString().slice(0, 10);
    };

    const setDefaultBookingValues = () => {
        /* A late-afternoon default makes the time field useful without forcing a choice. */
        if (bookingTime && !bookingTime.value) {
            bookingTime.value = "16:00";
        }

        if (bookingGuests && !bookingGuests.value) {
            bookingGuests.value = "10";
        }
    };

    const getCustomPackage = () => {
        try {
            const customPackage = JSON.parse(getStoredValue(customPackageStorageKey) ?? "null");
            return customPackage?.id === customPackageId && Array.isArray(customPackage.characteristics)
                ? customPackage
                : null;
        } catch (error) {
            return null;
        }
    };

    const buildCustomPackageDetails = (customPackage) => {
        const characteristics = customPackage?.characteristics
            ?.map((characteristic) => translate(characteristic.labelKey))
            ?.filter(Boolean) ?? [];

        if (characteristics.length === 0) {
            return "";
        }

        return [
            translate("contact.customPackageDetailsIntro"),
            ...characteristics.map((characteristic) => `- ${characteristic}`)
        ].join("\n");
    };

    const applyCustomPackageDetails = () => {
        if (!bookingDetails || bookingPackage?.value !== customPackageId) {
            return;
        }

        const details = buildCustomPackageDetails(getCustomPackage());

        if (!details) {
            return;
        }

        /*
         * Custom package details are prefilled only when the box is empty or
         * when the previous value was auto-generated. User-written notes are
         * left untouched.
         */
        if (!bookingDetails.value.trim() || bookingDetails.dataset.autoCustomPackage === "true") {
            bookingDetails.value = details;
            bookingDetails.dataset.autoCustomPackage = "true";
        }
    };

    const applySelectedPackageToBookingForm = () => {
        if (!bookingPackage) {
            return;
        }

        /*
         * Package selections made on packages.html are carried here through a
         * URL parameter and localStorage. The URL wins so the newest clicked
         * package always fills the booking form first.
         */
        const selectedPackage = getUrlPackage() ?? getStoredValue(selectedPackageStorageKey);

        if (selectedPackage && hasSelectOption(bookingPackage, selectedPackage)) {
            bookingPackage.value = selectedPackage;
            storeValue(selectedPackageStorageKey, selectedPackage);
            applyCustomPackageDetails();
        }
    };

    const hideBookingConfirmation = () => {
        if (bookingConfirmation && !bookingConfirmation.hidden) {
            bookingConfirmation.hidden = true;
        }
    };

    const clearBookingForm = ({ preserveConfirmation = false } = {}) => {
        if (!bookingForm) {
            return;
        }

        /*
         * Clear returns the booking form to a neutral empty state without
         * showing validation errors. Required fields are checked again only
         * when the visitor submits a new reservation request.
         */
        bookingForm.reset();
        bookingForm.querySelectorAll("input, select, textarea").forEach((field) => {
            if (field.type === "checkbox" || field.type === "radio") {
                field.checked = false;
                return;
            }

            field.value = "";
            field.setCustomValidity("");
        });
        bookingForm.classList.remove("was-validated");
        document.dispatchEvent(new CustomEvent("popadoo:booking-form-reset"));

        if (!preserveConfirmation) {
            hideBookingConfirmation();
        }
    };

    const validateBookingFields = () => {
        const validators = [
            {
                field: bookingName,
                key: "contact.invalidName",
                isValid: (value) => Boolean(value) && value.length <= 50
            },
            {
                field: bookingEmail,
                key: "contact.invalidEmail",
                isValid: (value) => !value || /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/u.test(value)
            },
            {
                field: bookingPhone,
                key: "contact.invalidPhone",
                isValid: (value) => {
                    if (!value) {
                        return false;
                    }

                    const digitsOnly = value.replace(/\D/g, "");
                    return /^\+?[0-9\s().-]+$/u.test(value)
                        && digitsOnly.length >= 7
                        && digitsOnly.length <= 15;
                }
            },
            {
                field: bookingDate,
                key: "contact.invalidDate",
                isValid: (value) => Boolean(value) && Boolean(bookingDate?.min) && value >= bookingDate.min
            },
            {
                field: bookingGuests,
                key: "contact.invalidGuests",
                isValid: (value) => Number.parseInt(value, 10) >= 1
            },
            {
                field: bookingPostalCode,
                key: "contact.invalidPostalCode",
                isValid: (value) => Boolean(value) && /^[A-Za-z0-9][A-Za-z0-9\s-]{2,9}$/u.test(value)
            }
        ];

        validators.forEach(({ field, key, isValid }) => {
            if (!field) {
                return;
            }

            const trimmedValue = field.value.trim();
            field.setCustomValidity(isValid(trimmedValue) ? "" : translate(key));
        });
    };

    const applyLanguage = (language) => {
        currentLanguage = isSupportedLanguage(language) ? language : "en";
        document.documentElement.lang = currentLanguage;

        document.querySelectorAll("[data-i18n]").forEach((element) => {
            const key = element.getAttribute("data-i18n");
            element.textContent = translate(key);
        });

        ["aria-label", "alt", "placeholder", "title"].forEach((attributeName) => {
            const dataAttribute = `data-i18n-${attributeName}`;

            document.querySelectorAll(`[${dataAttribute}]`).forEach((element) => {
                const key = element.getAttribute(dataAttribute);
                element.setAttribute(attributeName, translate(key));
            });
        });

        const page = document.body.dataset.page;
        document.title = translate(`meta.${page}.title`);

        if (metaDescription) {
            metaDescription.setAttribute("content", translate(`meta.${page}.description`));
        }

        if (languageSelector) {
            languageSelector.value = currentLanguage;
        }

        updateNavigationToggleLabel();
        updateThemeControl();
        updateInternalLanguageLinks();
        applyCustomPackageDetails();
        validateBookingFields();
        storeValue(languageStorageKey, currentLanguage);
        updateCurrentUrlLanguage();
        document.dispatchEvent(new CustomEvent("popadoo:language-applied", { detail: { language: currentLanguage } }));
    };

    const closeNavigation = (returnFocus = false) => {
        if (!navigationToggle || !navigationMenu) {
            return;
        }

        navigationMenu.classList.remove("is-open");
        navigationToggle.setAttribute("aria-expanded", "false");
        updateNavigationToggleLabel();

        if (returnFocus) {
            navigationToggle.focus();
        }
    };

    const openNavigation = () => {
        if (!navigationToggle || !navigationMenu) {
            return;
        }

        navigationMenu.classList.add("is-open");
        navigationToggle.setAttribute("aria-expanded", "true");
        updateNavigationToggleLabel();
    };

    if (navigationToggle && navigationMenu) {
        navigationToggle.addEventListener("click", () => {
            const isOpen = navigationToggle.getAttribute("aria-expanded") === "true";
            isOpen ? closeNavigation() : openNavigation();
        });

        navigationMenu.addEventListener("click", (event) => {
            if (event.target.closest("a") && navigationBreakpoint.matches) {
                closeNavigation();
            }
        });

        document.addEventListener("click", (event) => {
            if (
                navigationBreakpoint.matches
                && navigationMenu.classList.contains("is-open")
                && !event.target.closest(".site-navigation")
            ) {
                closeNavigation();
            }
        });

        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape" && navigationMenu.classList.contains("is-open")) {
                closeNavigation(true);
            }
        });

        navigationBreakpoint.addEventListener("change", (event) => {
            if (!event.matches) {
                closeNavigation();
            }
        });
    }

    /* Event delegation keeps the language dropdown working even if the header is re-rendered. */
    document.addEventListener("change", (event) => {
        if (event.target.matches("#language-selector")) {
            applyLanguage(event.target.value);
        }
    });

    if (themeToggle) {
        themeToggle.addEventListener("click", () => {
            const currentTheme = document.documentElement.getAttribute("data-theme");
            const nextTheme = currentTheme === "dark" ? "light" : "dark";

            document.documentElement.setAttribute("data-theme", nextTheme);
            storeValue(themeStorageKey, nextTheme);
            updateThemeControl();
        });
    }

    /*
     * Contact-form enhancement.
     * Native HTML validation stays active, while custom validation tightens name,
     * phone, guest-count, postal-code, and date rules before the demo response.
     */
    if (bookingDate) {
        bookingDate.min = formatDateForInput(new Date());
    }

    if (bookingForm) {
        setDefaultBookingValues();
        applySelectedPackageToBookingForm();
        validateBookingFields();

        bookingForm.addEventListener("submit", (event) => {
            event.preventDefault();
            event.stopPropagation();

            validateBookingFields();
            bookingForm.classList.add("was-validated");

            if (!bookingForm.checkValidity()) {
                bookingForm.querySelector(":invalid")?.focus();
                return;
            }

            clearBookingForm({ preserveConfirmation: true });

            if (bookingConfirmation) {
                bookingConfirmation.hidden = false;
                bookingConfirmation.focus();
                const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
                bookingConfirmation.scrollIntoView({
                    behavior: prefersReducedMotion ? "auto" : "smooth",
                    block: "center"
                });
            }
        });

        bookingForm.addEventListener("input", (event) => {
            if (event.target === bookingDetails) {
                bookingDetails.dataset.autoCustomPackage = "false";
            }

            validateBookingFields();
            hideBookingConfirmation();
        });

        bookingPackage?.addEventListener("change", () => {
            if (bookingPackage.value === customPackageId) {
                applyCustomPackageDetails();
            }
        });

        bookingForm.addEventListener("change", validateBookingFields);

        bookingClearButton?.addEventListener("click", () => {
            clearBookingForm();
            bookingForm.querySelector("input, select, textarea")?.focus();
        });
    }

    const savedLanguage = getStoredValue(languageStorageKey);
    const browserLanguage = navigator.language?.toLowerCase().startsWith("el") ? "el" : "en";
    const requestedLanguage = getUrlLanguage() ?? (isSupportedLanguage(savedLanguage) ? savedLanguage : browserLanguage);

    applyLanguage(requestedLanguage);
})();
