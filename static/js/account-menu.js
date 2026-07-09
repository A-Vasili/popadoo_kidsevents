"use strict";

(() => {
    const menu = document.querySelector("[data-account-menu]");
    if (!menu) return;

    const button = menu.querySelector("[data-account-menu-button]");
    const panel = menu.querySelector("[data-account-menu-panel]");
    const focusableSelector = "a[href], button:not([disabled])";

    const close = (returnFocus = false) => {
        panel.hidden = true;
        button.setAttribute("aria-expanded", "false");
        if (returnFocus) button.focus();
    };

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
