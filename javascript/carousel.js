"use strict";

/*
 * Home-page carousel enhancement.
 *
 * CSS provides a graceful fallback slideshow if JavaScript is unavailable.
 * When this module loads, it adds a managed active-slide state plus
 * icon-only arrow controls that work with pointer input and keyboard navigation.
 */
(() => {
    const carousel = document.querySelector("[data-home-carousel]");

    if (!carousel) {
        return;
    }

    const slides = Array.from(carousel.querySelectorAll(".hero-carousel-slide"));
    const previousButton = carousel.querySelector("[data-carousel-previous]");
    const nextButton = carousel.querySelector("[data-carousel-next]");
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

    const updateStatus = () => {
        if (status) {
            status.textContent = getStatusMessage();
        }
    };

    /* Activate one slide, hide the others from assistive tech, and refresh status text. */
    const showSlide = (nextIndex) => {
        activeIndex = (nextIndex + slides.length) % slides.length;

        slides.forEach((slide, index) => {
            const isActive = index === activeIndex;
            slide.classList.toggle("is-active", isActive);
            slide.setAttribute("aria-hidden", String(!isActive));
        });

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

    /* Refresh status text when main.js changes the document language. */
    const languageObserver = new MutationObserver(updateStatus);
    languageObserver.observe(document.documentElement, {
        attributes: true,
        attributeFilter: ["lang"]
    });
})();
