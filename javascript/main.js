"use strict";

(() => {
    const translations = window.popadooTranslations;
    const languageStorageKey = "popadoo-language";
    const themeStorageKey = "popadoo-theme";
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
    const bookingDate = document.querySelector("#booking-date");

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

    const applyLanguage = (language) => {
        currentLanguage = translations?.[language] ? language : "en";
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
        storeValue(languageStorageKey, currentLanguage);
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

    if (languageSelector) {
        languageSelector.addEventListener("change", (event) => {
            applyLanguage(event.target.value);
        });
    }

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
     * Native HTML validation remains the source of truth; Bootstrap's
     * was-validated class adds visible feedback, and the live region confirms
     * a successful demonstration submission without pretending to use a server.
     */
    if (bookingDate) {
        const tomorrow = new Date();
        tomorrow.setDate(tomorrow.getDate() + 1);
        const year = tomorrow.getFullYear();
        const month = String(tomorrow.getMonth() + 1).padStart(2, "0");
        const day = String(tomorrow.getDate()).padStart(2, "0");
        bookingDate.min = `${year}-${month}-${day}`;
    }

    if (bookingForm) {
        bookingForm.addEventListener("submit", (event) => {
            event.preventDefault();
            event.stopPropagation();

            bookingForm.classList.add("was-validated");

            if (!bookingForm.checkValidity()) {
                bookingForm.querySelector(":invalid")?.focus();
                return;
            }

            bookingForm.reset();
            bookingForm.classList.remove("was-validated");

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

        bookingForm.addEventListener("input", () => {
            if (bookingConfirmation && !bookingConfirmation.hidden) {
                bookingConfirmation.hidden = true;
            }
        });
    }

    const savedLanguage = getStoredValue(languageStorageKey);
    const browserLanguage = navigator.language?.toLowerCase().startsWith("el") ? "el" : "en";
    applyLanguage(savedLanguage === "el" || savedLanguage === "en" ? savedLanguage : browserLanguage);
})();
