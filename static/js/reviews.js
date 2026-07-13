"use strict";

(() => {
    const form = document.querySelector("[data-review-form]");
    if (!form) return;

    const status = form.querySelector("[data-review-status]");
    const submit = form.querySelector("[data-review-submit]");
    const csrf = form.querySelector("input[name='csrfmiddlewaretoken']");
    const nameSection = form.querySelector("[data-testimonial-name-section]");
    const visibilityInputs = Array.from(
        form.querySelectorAll("input[name='visibility']")
    );

    const selectedVisibility = () => (
        visibilityInputs.find((input) => input.checked)?.value || "private"
    );

    const updateNameSection = () => {
        if (!nameSection) return;
        const isTestimonial = selectedVisibility() === "testimonial";
        nameSection.hidden = !isTestimonial;
        nameSection.setAttribute("aria-hidden", String(!isTestimonial));
    };

    visibilityInputs.forEach((input) => {
        input.addEventListener("change", updateNameSection);
    });
    updateNameSection();

    if (!window.fetch) return;

    const showStatus = (message, kind) => {
        status.hidden = false;
        status.className = `review-alert ${kind}`;
        status.textContent = message;
        status.focus();
    };

    const clearErrors = () => {
        form.querySelectorAll("[data-error-for]").forEach((node) => {
            node.replaceChildren();
        });
        form.querySelectorAll("[aria-invalid='true']").forEach((node) => {
            node.removeAttribute("aria-invalid");
        });
    };

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        clearErrors();
        submit.disabled = true;
        submit.textContent = "Saving…";

        try {
            const response = await fetch(form.action, {
                method: "POST",
                body: new FormData(form),
                credentials: "same-origin",
                headers: {
                    "X-CSRFToken": csrf.value,
                    "X-Requested-With": "XMLHttpRequest",
                    "Accept": "application/json",
                },
            });
            const payload = await response.json();

            if (!response.ok) {
                Object.entries(payload.errors || {}).forEach(([name, messages]) => {
                    const escapedName = CSS.escape(name);
                    const container = form.querySelector(
                        `[data-error-for='${escapedName}']`
                    );
                    const field = form.querySelector(`[name='${escapedName}']`);
                    if (container) container.textContent = messages.join(" ");
                    if (field) field.setAttribute("aria-invalid", "true");
                });
                updateNameSection();
                showStatus(
                    payload.message || "The review could not be saved.",
                    "error"
                );
                return;
            }

            const packageStats = payload.stats?.package;
            const packageSummary = form.querySelector(
                "[data-package-rating-summary]"
            );
            if (packageSummary && packageStats) {
                packageSummary.textContent = packageStats.count
                    ? `Community average: ${packageStats.average.toFixed(1)} / 5 from ${packageStats.count} review${packageStats.count === 1 ? "" : "s"}.`
                    : "No verified package ratings yet.";
            }

            Object.entries(payload.stats?.addons || {}).forEach(
                ([addonId, addonStats]) => {
                    const summary = form.querySelector(
                        `[data-addon-rating-summary='${CSS.escape(addonId)}']`
                    );
                    if (summary) {
                        summary.textContent = addonStats.count
                            ? `Community average: ${addonStats.average.toFixed(1)} / 5 from ${addonStats.count} review${addonStats.count === 1 ? "" : "s"}.`
                            : "No verified ratings yet.";
                    }
                }
            );

            showStatus(payload.message, "success");
        } catch (_error) {
            showStatus(
                "The review could not be sent. Please try the normal form again.",
                "error"
            );
        } finally {
            submit.disabled = false;
            submit.textContent = "Save review";
        }
    });
})();
