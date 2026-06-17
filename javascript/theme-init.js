"use strict";

/* Apply the saved theme before the page paints to reduce theme flashing. */
(() => {
    const storageKey = "popadoo-theme";
    let savedTheme = null;

    try {
        savedTheme = window.localStorage.getItem(storageKey);
    } catch (error) {
        savedTheme = null;
    }

    const preferredTheme = window.matchMedia("(prefers-color-scheme: dark)").matches
        ? "dark"
        : "light";
    const theme = savedTheme === "light" || savedTheme === "dark"
        ? savedTheme
        : preferredTheme;

    document.documentElement.setAttribute("data-theme", theme);
})();
