"use strict";

/*
 * Home-page carousel enhancement.
 * CSS still provides a fallback slideshow. When JavaScript is available, this
 * module switches to an explicit active-slide state and exposes a manual next
 * control that works with mouse, touch, and keyboard input.
 */
(() => {
    const carousel = document.querySelector("[data-home-carousel]");

    if (!carousel) {
        return;
    }

    const slides = Array.from(carousel.querySelectorAll(".hero-carousel-slide"));
    const nextButton = carousel.querySelector("[data-carousel-next]");
    const status = carousel.querySelector("[data-carousel-status]");

    if (slides.length === 0 || !nextButton) {
        return;
    }

    let activeIndex = 0;

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

    const showSlide = (nextIndex) => {
        activeIndex = (nextIndex + slides.length) % slides.length;

        slides.forEach((slide, index) => {
            slide.classList.toggle("is-active", index === activeIndex);
        });

        updateStatus();
    };

    const showNextSlide = () => {
        showSlide(activeIndex + 1);
    };

    carousel.classList.add("is-carousel-enhanced");
    showSlide(activeIndex);

    nextButton.addEventListener("click", showNextSlide);

    carousel.addEventListener("keydown", (event) => {
        if (event.key === "ArrowRight") {
            event.preventDefault();
            showNextSlide();
        }
    });

    /* Keep the live status message in sync when main.js changes the language. */
    const languageObserver = new MutationObserver(updateStatus);
    languageObserver.observe(document.documentElement, {
        attributes: true,
        attributeFilter: ["lang"]
    });
})();
