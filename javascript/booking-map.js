"use strict";

/*
 * Booking map integration.
 * Connects Leaflet with OpenStreetMap search so visitors can choose or verify
 * the event location without leaving the booking form.
 */
(() => {
    /* The module exits early on pages without a map or when Leaflet is unavailable. */
    const mapElement = document.querySelector("#booking-map");

    if (!mapElement || typeof window.L === "undefined") {
        return;
    }

    /* Form fields and status elements updated by geocoding results. */
    const addressField = document.querySelector("#booking-location");
    const postalCodeField = document.querySelector("#booking-postal-code");
    const statusElement = document.querySelector("#booking-map-status");
    const mapLink = document.querySelector("#booking-map-link");
    const defaultPosition = [39.0742, 21.8243];
    const geocodeEndpoint = "https://nominatim.openstreetmap.org";
    let searchTimer = null;

    /* Update the accessible status text used for map and search feedback. */
    const setStatus = (message) => {
        if (statusElement) {
            statusElement.textContent = message;
        }
    };

    const normaliseAddressPart = (value) => value?.trim() ?? "";

    /* Convert Nominatim address parts into a readable single-line address. */
    const buildAddressLine = (address = {}) => {
        const road = normaliseAddressPart(address.road || address.pedestrian || address.footway || address.path);
        const houseNumber = normaliseAddressPart(address.house_number);
        const neighbourhood = normaliseAddressPart(address.neighbourhood || address.suburb);
        const city = normaliseAddressPart(address.city || address.town || address.village || address.municipality);
        const country = normaliseAddressPart(address.country);
        const street = [road, houseNumber].filter(Boolean).join(" ");

        return [street, neighbourhood, city, country]
            .filter(Boolean)
            .filter((item, index, items) => items.indexOf(item) === index)
            .join(", ");
    };

    /* Combine address and postal-code inputs into the forward-geocoding query. */
    const buildSearchQuery = () => {
        return [addressField?.value, postalCodeField?.value]
            .map((value) => value?.trim())
            .filter(Boolean)
            .join(", ");
    };

    /* Keep the external OpenStreetMap link synchronized with the marker position. */
    const updateMapLink = (lat, lon, zoom = 16) => {
        if (!mapLink) {
            return;
        }

        mapLink.href = `https://www.openstreetmap.org/?mlat=${lat}&mlon=${lon}#map=${zoom}/${lat}/${lon}`;
    };

    /* Leaflet gives keyboard-accessible zoom/pan controls and lets users choose a location by clicking the map. */
    const map = window.L.map(mapElement, {
        center: defaultPosition,
        keyboard: true,
        scrollWheelZoom: false,
        zoom: 6
    });

    window.L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "&copy; OpenStreetMap contributors",
        maxZoom: 19
    }).addTo(map);

    const marker = window.L.marker(defaultPosition, {
        keyboard: true,
        title: "Selected party location"
    }).addTo(map);

    updateMapLink(defaultPosition[0], defaultPosition[1], 6);

    /* Move the marker, pan/zoom the map, and update the external map link together. */
    const setMarker = (lat, lon, zoom = 16) => {
        const position = [Number(lat), Number(lon)];
        marker.setLatLng(position);
        map.setView(position, zoom);
        updateMapLink(position[0], position[1], zoom);
    };

    /* Fetch JSON from OpenStreetMap and surface network failures as user messages. */
    const requestJson = async (url) => {
        const response = await fetch(url, {
            headers: {
                "Accept": "application/json",
                "Accept-Language": document.documentElement.lang || "en"
            }
        });

        if (!response.ok) {
            throw new Error(`Map lookup failed with status ${response.status}`);
        }

        return response.json();
    };

    /* Look up the clicked map position and write the resolved address into the form. */
    const reverseGeocode = async ({ lat, lng }) => {
        const url = new URL(`${geocodeEndpoint}/reverse`);
        url.searchParams.set("format", "jsonv2");
        url.searchParams.set("lat", lat);
        url.searchParams.set("lon", lng);
        url.searchParams.set("addressdetails", "1");
        url.searchParams.set("email", "hello@popadookidsevents.gr");

        setMarker(lat, lng);
        setStatus("Looking up the selected location…");

        try {
            const data = await requestJson(url);
            const addressLine = buildAddressLine(data.address) || data.display_name || "";

            if (addressField && addressLine) {
                addressField.value = addressLine;
                addressField.dispatchEvent(new Event("input", { bubbles: true }));
            }

            if (postalCodeField && data.address?.postcode) {
                postalCodeField.value = data.address.postcode;
                postalCodeField.dispatchEvent(new Event("input", { bubbles: true }));
            }

            setStatus("Location selected. Address and postal code fields have been updated.");
        } catch (error) {
            setStatus("The map point was selected, but the address could not be filled automatically. Please type the address manually.");
        }
    };

    /* Search for the typed address and move the map to the best returned match. */
    const forwardGeocode = async () => {
        const query = buildSearchQuery();

        if (query.length < 4) {
            return;
        }

        const url = new URL(`${geocodeEndpoint}/search`);
        url.searchParams.set("format", "jsonv2");
        url.searchParams.set("q", query);
        url.searchParams.set("addressdetails", "1");
        url.searchParams.set("limit", "1");
        url.searchParams.set("email", "hello@popadookidsevents.gr");

        setStatus("Updating map from the address…");

        try {
            const results = await requestJson(url);
            const firstResult = results[0];

            if (!firstResult) {
                setStatus("No map result found yet. Add more address details or click the map.");
                return;
            }

            setMarker(firstResult.lat, firstResult.lon);

            if (postalCodeField && !postalCodeField.value && firstResult.address?.postcode) {
                postalCodeField.value = firstResult.address.postcode;
                postalCodeField.dispatchEvent(new Event("input", { bubbles: true }));
            }

            setStatus("Map updated from the address field.");
        } catch (error) {
            setStatus("The map could not update from the typed address. You can still click the map or continue typing manually.");
        }
    };

    /* Debounce typing so the search endpoint is not called on every keystroke. */
    const scheduleForwardGeocode = () => {
        window.clearTimeout(searchTimer);
        searchTimer = window.setTimeout(forwardGeocode, 750);
    };

    map.on("click", (event) => {
        reverseGeocode(event.latlng);
    });

    [addressField, postalCodeField].forEach((field) => {
        field?.addEventListener("input", scheduleForwardGeocode);
        field?.addEventListener("change", forwardGeocode);
    });

    document.addEventListener("popadoo:booking-form-reset", () => {
        setMarker(defaultPosition[0], defaultPosition[1], 6);
        setStatus("Map ready. Click a point to select the party location.");
    });
})();
