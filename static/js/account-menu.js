"use strict";

/*
 * This script opens and closes the signed-in account menu in a keyboard-friendly way.
 * These comments explain the browser-side steps without changing the JavaScript behaviour.
 */

(() => {
    const menu = document.querySelector("[data-account-menu]");
    if (!menu) return;

    const button = menu.querySelector("[data-account-menu-button]");
    const panel = menu.querySelector("[data-account-menu-panel]");
    const focusableSelector = "a[href], button:not([disabled])";

    // This function changes whether close is visible.
    const close = (returnFocus = false) => {
        panel.hidden = true;
        button.setAttribute("aria-expanded", "false");
        if (returnFocus) button.focus();
    };

    // This function changes whether open is visible.
    const open = () => {
        panel.hidden = false;
        button.setAttribute("aria-expanded", "true");
        panel.querySelector(focusableSelector)?.focus();
    };

    button.addEventListener("click", () => {
        if (panel.hidden) open(); else close();
    });

    menu.addEventListener("keydown", (event) => {
        if (event.key === "Escape") close(true);
        if ((event.key === "Enter" || event.key === " ") && event.target === button) {
            event.preventDefault();
            if (panel.hidden) open(); else close();
        }
    });

    document.addEventListener("click", (event) => {
        if (!menu.contains(event.target)) close();
    });
})();
