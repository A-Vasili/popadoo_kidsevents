"use strict";

/*
 * This script controls the home-page image carousel and keeps its buttons, indicators, and announcements synchronized.
 * These comments explain the browser-side steps without changing the JavaScript behaviour.
 */

/*
 * Home-page carousel enhancement.
 *
 * CSS provides a graceful fallback slideshow if JavaScript is unavailable.
 * When this module loads, it adds managed active-slide state, icon-only arrow
 * controls, keyboard support, bottom-center dots, and continuous autoplay.
 */
(() => {
    const carousel = document.querySelector("[data-home-carousel]");

    if (!carousel) {
        return;
    }

    const slides = Array.from(carousel.querySelectorAll(".hero-carousel-slide"));
    const previousButton = carousel.querySelector("[data-carousel-previous]");
    const nextButton = carousel.querySelector("[data-carousel-next]");
    const indicatorButtons = Array.from(carousel.querySelectorAll("[data-carousel-indicator]"));
    const status = carousel.querySelector("[data-carousel-status]");
    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    const autoplayInterval = 5000;

    if (slides.length === 0 || !previousButton || !nextButton) {
        return;
    }

    /* Track the currently visible slide; wrapping is handled by showSlide(). */
    let activeIndex = 0;
    let autoplayTimer = null;

    /* Build localized screen-reader text for the current slide position. */
    const getStatusMessage = () => {
        const current = activeIndex + 1;
        const total = slides.length;
        const language = document.documentElement.lang;

        return language === "el"
            ? `Φωτογραφία ${current} από ${total}`
            : `Photo ${current} of ${total}`;
    };

    // This function reads or prepares indicator label for the next step.
    const getIndicatorLabel = (index) => {
        const position = index + 1;
        const language = document.documentElement.lang;

        return language === "el"
            ? `Εμφάνιση εικόνας ${position}`
            : `Show image ${position}`;
    };

    // This function refreshes status so the page matches the latest user choice.
    const updateStatus = () => {
        if (status) {
            status.textContent = getStatusMessage();
        }
    };

    /* Keep dot labels and active state useful for screen readers and keyboard users. */
    const updateIndicators = () => {
        indicatorButtons.forEach((button, index) => {
            const isActive = index === activeIndex;
            button.classList.toggle("is-active", isActive);
            button.setAttribute("aria-current", String(isActive));
            button.setAttribute("aria-label", getIndicatorLabel(index));
        });
    };

    /* Activate one slide, hide the others from assistive tech, and refresh controls. */
    const showSlide = (nextIndex) => {
        activeIndex = (nextIndex + slides.length) % slides.length;

        slides.forEach((slide, index) => {
            const isActive = index === activeIndex;
            slide.classList.toggle("is-active", isActive);
            slide.setAttribute("aria-hidden", String(!isActive));
        });

        updateIndicators();
        updateStatus();
    };

    // This function handles the show previous slide part of the browser interaction.
    const showPreviousSlide = () => {
        showSlide(activeIndex - 1);
    };

    // This function handles the show next slide part of the browser interaction.
    const showNextSlide = () => {
        showSlide(activeIndex + 1);
    };

    // This function handles the stop autoplay part of the browser interaction.
    const stopAutoplay = () => {
        window.clearInterval(autoplayTimer);
        autoplayTimer = null;
    };

    // This function handles the start autoplay part of the browser interaction.
    const startAutoplay = () => {
        stopAutoplay();

        /* Honour reduced-motion preferences while keeping manual controls available. */
        if (slides.length < 2 || prefersReducedMotion.matches) {
            return;
        }

        autoplayTimer = window.setInterval(showNextSlide, autoplayInterval);
    };

    /* Manual navigation restarts the timer so auto-sliding never jumps immediately after a click. */
    const navigateManually = (navigationCallback) => {
        navigationCallback();
        startAutoplay();
    };

    carousel.classList.add("is-carousel-enhanced");
    showSlide(activeIndex);
    startAutoplay();

    previousButton.addEventListener("click", () => {
        navigateManually(showPreviousSlide);
    });

    nextButton.addEventListener("click", () => {
        navigateManually(showNextSlide);
    });

    indicatorButtons.forEach((button) => {
        button.addEventListener("click", () => {
            navigateManually(() => {
                showSlide(Number(button.dataset.carouselIndicator));
            });
        });
    });

    carousel.addEventListener("keydown", (event) => {
        if (event.key === "ArrowLeft") {
            event.preventDefault();
            navigateManually(showPreviousSlide);
        }

        if (event.key === "ArrowRight") {
            event.preventDefault();
            navigateManually(showNextSlide);
        }
    });

    /* Avoid wasting work while the tab is hidden; restart the loop as soon as it is visible. */
    document.addEventListener("visibilitychange", () => {
        if (document.hidden) {
            stopAutoplay();
            return;
        }

        startAutoplay();
    });

    if (typeof prefersReducedMotion.addEventListener === "function") {
        prefersReducedMotion.addEventListener("change", startAutoplay);
    } else if (typeof prefersReducedMotion.addListener === "function") {
        prefersReducedMotion.addListener(startAutoplay);
    }

    /* Refresh translated carousel labels when main.js changes the document language. */
    const languageObserver = new MutationObserver(() => {
        updateIndicators();
        updateStatus();
    });

    languageObserver.observe(document.documentElement, {
        attributes: true,
        attributeFilter: ["lang"]
    });
})();
