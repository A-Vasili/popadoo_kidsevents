"use strict";

/*
 * This small script applies the saved light or dark theme before the page appears, preventing a visible colour flash.
 * These comments explain the browser-side steps without changing the JavaScript behaviour.
 */

/* Apply the saved theme before the page paints to reduce theme flashing. */
(() => {
    /* The same key is used by main.js when visitors change the theme. */
    const storageKey = "popadoo-theme";
    let savedTheme = null;

    try {
        savedTheme = window.localStorage.getItem(storageKey);
    } catch (error) {
        savedTheme = null;
    }

    /* Fall back to the operating-system preference when no saved theme exists. */
    const preferredTheme = window.matchMedia("(prefers-color-scheme: dark)").matches
        ? "dark"
        : "light";
    const theme = savedTheme === "light" || savedTheme === "dark"
        ? savedTheme
        : preferredTheme;

    /* Set the root attribute early so CSS can render the correct color scheme. */
    document.documentElement.setAttribute("data-theme", theme);
})();
