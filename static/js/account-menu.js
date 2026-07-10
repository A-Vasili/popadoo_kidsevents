"use strict";

/*
 * Accessible account dropdowns for the upper utility stripe.
 *
 * The same controller works for guest and signed-in menus. It supports mouse,
 * touch, arrow keys, Home/End, Escape, and normal Tab navigation.
 */
(() => {
    class AccountMenu {
        constructor(root) {
            this.root = root;
            this.button = root.querySelector("[data-account-menu-button]");
            this.panel = root.querySelector("[data-account-menu-panel]");
            this.items = Array.from(
                root.querySelectorAll("[data-account-menu-item]")
            );

            if (!this.button || !this.panel) {
                return;
            }

            this.bindEvents();
        }

        bindEvents() {
            this.button.addEventListener("click", () => this.toggle());
            this.button.addEventListener("keydown", (event) => {
                if (["Enter", " ", "ArrowDown", "ArrowUp"].includes(event.key)) {
                    event.preventDefault();
                    this.open(event.key === "ArrowUp" ? this.items.length - 1 : 0);
                } else if (event.key === "Escape") {
                    this.close(true);
                }
            });

            this.panel.addEventListener("keydown", (event) => {
                this.handlePanelKeyboard(event);
            });

            document.addEventListener("click", (event) => {
                if (!this.root.contains(event.target)) {
                    this.close();
                }
            });
        }

        isOpen() {
            return this.button.getAttribute("aria-expanded") === "true";
        }

        open(focusIndex = null) {
            this.panel.hidden = false;
            this.button.setAttribute("aria-expanded", "true");

            /* Close the language popover so two menus never overlap. */
            document.querySelectorAll("[data-custom-popover-open='true']").forEach((control) => {
                control.dispatchEvent(new CustomEvent("popadoo:close-control"));
            });

            if (Number.isInteger(focusIndex) && this.items.length) {
                this.items[Math.max(0, Math.min(focusIndex, this.items.length - 1))].focus();
            }
        }

        close(returnFocus = false) {
            this.panel.hidden = true;
            this.button.setAttribute("aria-expanded", "false");

            if (returnFocus) {
                this.button.focus();
            }
        }

        toggle() {
            if (this.isOpen()) {
                this.close();
            } else {
                this.open();
            }
        }

        focusItem(index) {
            if (!this.items.length) {
                return;
            }

            const safeIndex = (index + this.items.length) % this.items.length;
            this.items[safeIndex].focus();
        }

        handlePanelKeyboard(event) {
            const currentIndex = this.items.indexOf(document.activeElement);

            if (event.key === "Escape") {
                event.preventDefault();
                this.close(true);
                return;
            }

            if (currentIndex < 0) {
                return;
            }

            if (event.key === "ArrowDown") {
                event.preventDefault();
                this.focusItem(currentIndex + 1);
            } else if (event.key === "ArrowUp") {
                event.preventDefault();
                this.focusItem(currentIndex - 1);
            } else if (event.key === "Home") {
                event.preventDefault();
                this.focusItem(0);
            } else if (event.key === "End") {
                event.preventDefault();
                this.focusItem(this.items.length - 1);
            } else if (event.key === "Tab") {
                window.setTimeout(() => {
                    if (!this.root.contains(document.activeElement)) {
                        this.close();
                    }
                }, 0);
            }
        }
    }

    document.querySelectorAll("[data-account-menu]").forEach(
        (root) => new AccountMenu(root)
    );
})();
