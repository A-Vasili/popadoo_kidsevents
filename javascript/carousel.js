"use strict";

/*
 * Home-page carousel enhancement.
 *
 * CSS provides a graceful fallback slideshow if JavaScript is unavailable.
 * When this module loads, it adds managed active-slide state, icon-only arrow
 * controls, keyboard support, and bottom-center dots that show the current slide.
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

    if (slides.length === 0 || !previousButton || !nextButton) {
        return;
    }

    /* Track the currently visible slide; wrapping is handled by showSlide(). */
    let activeIndex = 0;

    /* Build localized screen-reader text for the current slide position. */
    const getStatusMessage = () => {
        const current = activeIndex + 1;
        const total = slides.length;
        const language = document.documentElement.lang;

        return language === "el"
            ? `Φωτογραφία ${current} από ${total}`
            : `Photo ${current} of ${total}`;
    };

    const getIndicatorLabel = (index) => {
        const position = index + 1;
        const language = document.documentElement.lang;

        return language === "el"
            ? `Εμφάνιση εικόνας ${position}`
            : `Show image ${position}`;
    };

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

    const showPreviousSlide = () => {
        showSlide(activeIndex - 1);
    };

    const showNextSlide = () => {
        showSlide(activeIndex + 1);
    };

    carousel.classList.add("is-carousel-enhanced");
    showSlide(activeIndex);

    /* Pointer and keyboard controls all use the same slide navigation functions. */
    previousButton.addEventListener("click", showPreviousSlide);
    nextButton.addEventListener("click", showNextSlide);

    indicatorButtons.forEach((button) => {
        button.addEventListener("click", () => {
            showSlide(Number(button.dataset.carouselIndicator));
        });
    });

    carousel.addEventListener("keydown", (event) => {
        if (event.key === "ArrowLeft") {
            event.preventDefault();
            showPreviousSlide();
        }

        if (event.key === "ArrowRight") {
            event.preventDefault();
            showNextSlide();
        }
    });

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
