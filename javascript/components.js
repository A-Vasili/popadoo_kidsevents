"use strict";

/*
 * Reusable site chrome.
 *
 * The custom elements below keep the header and footer in one maintained file,
 * so page templates no longer duplicate large blocks of navigation markup.
 * Each component renders semantic HTML and then lets main.js apply translations,
 * theme behaviour, keyboard navigation, and the current-page state.
 */
(() => {
    const navigationItems = [
        { page: "index", href: "index.html", key: "nav.home", label: "Home" },
        { page: "gallery", href: "gallery.html", key: "nav.gallery", label: "Gallery" },
        { page: "packages", href: "packages.html", key: "nav.packages", label: "Packages" },
        { page: "about", href: "about.html", key: "nav.about", label: "About Us" },
        { page: "testimonials", href: "testimonials.html", key: "nav.testimonials", label: "Testimonials" }
    ];

    const getCurrentPage = () => document.body?.dataset.page ?? "index";

    class PopadooHeader extends HTMLElement {
        connectedCallback() {
            const currentPage = getCurrentPage();
            const navigationLinks = navigationItems.map((item) => {
                const isCurrent = item.page === currentPage;
                const activeClass = isCurrent ? " active" : "";
                const ariaCurrent = isCurrent ? ' aria-current="page"' : "";

                return `
                    <li>
                        <a class="site-navigation-link${activeClass}"${ariaCurrent}
                           href="${item.href}"
                           data-i18n="${item.key}">${item.label}</a>
                    </li>`;
            }).join("");

            const contactActiveClass = currentPage === "contact" ? " active" : "";
            const contactAriaCurrent = currentPage === "contact" ? ' aria-current="page"' : "";

            this.innerHTML = `
                <header class="site-header">
                    <div class="container">
                        <nav class="site-navigation" aria-label="Primary navigation" data-i18n-aria-label="nav.primaryLabel">
                            <a class="site-logo" href="index.html" aria-label="Popadoo Kids Events home" data-i18n-aria-label="nav.logoLabel">
                                <img class="site-logo-mark" src="assets/svg/popadoo-logo.svg" alt="" width="128" height="128"/>
                                <span class="site-logo-text">Popadoo Kids Events</span>
                            </a>

                            <button
                                class="site-navigation-toggle"
                                type="button"
                                aria-controls="primary-navigation"
                                aria-expanded="false"
                                aria-label="Open primary navigation"
                            >
                                <span class="site-navigation-toggle-line" aria-hidden="true"></span>
                                <span class="site-navigation-toggle-line" aria-hidden="true"></span>
                                <span class="site-navigation-toggle-line" aria-hidden="true"></span>
                            </button>

                            <div class="site-navigation-menu" id="primary-navigation">
                                <ul class="site-navigation-links">
                                    ${navigationLinks}
                                </ul>

                                <div class="site-controls">
                                    <div class="language-control">
                                        <label class="visually-hidden" for="language-selector" data-i18n="language.label">Language</label>
                                        <select
                                            class="language-selector"
                                            id="language-selector"
                                            aria-label="Language"
                                            data-i18n-aria-label="language.label"
                                        >
                                            <option value="en" lang="en" data-i18n="language.english">English</option>
                                            <option value="el" lang="el" data-i18n="language.greek">Greek</option>
                                        </select>
                                    </div>

                                    <button
                                        class="theme-toggle"
                                        id="theme-toggle"
                                        type="button"
                                        role="switch"
                                        aria-checked="false"
                                        aria-label="Switch to dark mode"
                                    >
                                        <span class="theme-toggle-track" aria-hidden="true">
                                            <span class="theme-toggle-stars"></span>
                                            <span class="theme-toggle-clouds"></span>
                                            <span class="theme-toggle-knob">
                                                <img class="theme-toggle-icon theme-toggle-icon-moon" src="assets/svg/moon-toggle.svg" alt="" width="82" height="82"/>
                                                <img class="theme-toggle-icon theme-toggle-icon-sun" src="assets/svg/sun-toggle.svg" alt="" width="82" height="82"/>
                                            </span>
                                        </span>
                                        <span class="visually-hidden" data-theme-status>Light mode</span>
                                    </button>

                                    <a class="book-now-button${contactActiveClass}"${contactAriaCurrent}
                                       href="contact.html"
                                       data-i18n="nav.bookNow">Book Now</a>
                                </div>
                            </div>
                        </nav>
                    </div>
                </header>`;
        }
    }

    class PopadooFooter extends HTMLElement {
        connectedCallback() {
            const styleGuideAriaCurrent = getCurrentPage() === "styleGuide"
                ? ' aria-current="page"'
                : "";

            this.innerHTML = `
                <footer class="site-footer">
                    <div class="container site-footer-grid">
                        <div class="site-footer-brand">
                            <a class="site-footer-logo" href="index.html" aria-label="Popadoo Kids Events home" data-i18n-aria-label="nav.logoLabel">
                                <img src="assets/svg/popadoo-logo.svg" alt="" width="96" height="96"/>
                                <strong>Popadoo Kids Events</strong>
                            </a>
                            <p data-i18n="footer.tagline">Joyful children’s events, brought to your chosen venue.</p>
                        </div>

                        <div class="site-footer-contact" aria-labelledby="footer-contact-heading">
                            <h2 id="footer-contact-heading" class="site-footer-heading" data-i18n="footer.contactHeading">Contact</h2>
                            <a href="mailto:hello@popadookidsevents.gr">hello@popadookidsevents.gr</a>
                            <a
                                class="site-footer-social-link"
                                href="https://www.instagram.com/popadoo_kidsevents/"
                                target="_blank"
                                rel="noopener noreferrer"
                                aria-label="Visit Popadoo on Instagram"
                                data-i18n-aria-label="footer.instagramLabel"
                            >
                                <img class="site-footer-social-icon" src="assets/svg/instagram-icon.svg" alt="" width="28" height="28" aria-hidden="true"/>
                                <span class="visually-hidden" data-i18n="footer.instagram">Instagram</span>
                            </a>
                        </div>

                        <div class="site-footer-resources" aria-labelledby="footer-resources-heading">
                            <h2 id="footer-resources-heading" class="site-footer-heading" data-i18n="footer.resourcesHeading">Resources</h2>
                            <a href="style-guide.html"${styleGuideAriaCurrent} data-i18n="footer.styleGuide">Documentation</a>
                            <p data-i18n="footer.copyright">© 2026 Popadoo Kids Events</p>
                        </div>
                    </div>
                </footer>`;
        }
    }

    if (!customElements.get("popadoo-header")) {
        customElements.define("popadoo-header", PopadooHeader);
    }

    if (!customElements.get("popadoo-footer")) {
        customElements.define("popadoo-footer", PopadooFooter);
    }
})();
