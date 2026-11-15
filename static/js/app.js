
/* ========================================
   EVENTSPHERE - HOMEPAGE JAVASCRIPT
======================================== */


/* ========================================
   MOBILE NAVIGATION
======================================== */

const menuButton = document.getElementById("menuButton");
const navLinks = document.getElementById("navLinks");

if (menuButton && navLinks) {

    menuButton.addEventListener("click", () => {

        const isOpen = navLinks.classList.toggle("show");

        menuButton.setAttribute(
            "aria-expanded",
            String(isOpen)
        );

    });

    navLinks.querySelectorAll("a").forEach(link => {

        link.addEventListener("click", () => {

            navLinks.classList.remove("show");

            menuButton.setAttribute(
                "aria-expanded",
                "false"
            );

        });

    });

}


/* ========================================
   EVENT ELEMENTS
======================================== */

const eventGrid = document.getElementById("eventGrid");

const eventStatus = document.getElementById("eventStatus");

const eventSearch = document.getElementById("eventSearch");

const categoryGrid = document.getElementById("categoryGrid");

const clearFilters = document.getElementById("clearFilters");


/* ========================================
   EVENT DATA
======================================== */

let allEvents = [];

let selectedCategory = "";


/* ========================================
   PREVENT HTML INJECTION
======================================== */

function escapeHtml(value) {

    return String(value ?? "").replace(
        /[&<>"']/g,
        char => ({
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#39;"
        })[char]
    );

}


/* ========================================
   FORMAT EVENT DATE
======================================== */

function formatDate(value) {

    if (!value) {
        return "Date to be announced";
    }

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
        return "Date to be announced";
    }

    return date.toLocaleString(undefined, {
        dateStyle: "medium",
        timeStyle: "short"
    });

}


/* ========================================
   CREATE EVENT CARD
======================================== */

function eventCard(event) {

    const category = event.category || "Event";

    const venue =
        event.venue_name ||
        event.venue?.name ||
        "University venue";

    const description =
        event.description ||
        "Discover this event and reserve your place.";

    const date = formatDate(event.start_time);

    const safeCategory = escapeHtml(category);

    const safeTitle = escapeHtml(
        event.title || "Untitled event"
    );

    const safeDescription = escapeHtml(description);

    const safeVenue = escapeHtml(venue);

    const safeDate = escapeHtml(date);

    const imageCategory = category
        .toLowerCase()
        .replace(/[^a-z]/g, "") || "event";

    return `

        <article class="event-card">

            <div class="event-photo event-photo-${imageCategory}">

                <span>${safeCategory.toUpperCase()}</span>

            </div>

            <div class="event-info">

                <span class="event-category">
                    ${safeCategory}
                </span>

                <h3>${safeTitle}</h3>

                <p>${safeDescription}</p>

                <div class="event-meta">

                    <span>
                        ◷ ${safeDate}
                    </span>

                    <span>
                        ⌖ ${safeVenue}
                    </span>

                </div>

                <a class="event-link"
                   href="/login">

                    View booking options

                    <span>→</span>

                </a>

            </div>

        </article>

    `;

}


/* ========================================
   DISPLAY EVENTS
======================================== */

function renderEvents() {

    if (!eventGrid) {
        return;
    }

    const searchTerm = (
        eventSearch?.value || ""
    ).trim().toLowerCase();


    const filteredEvents = allEvents.filter(event => {

        const matchesCategory =
            !selectedCategory ||
            String(event.category || "").toLowerCase() ===
            selectedCategory.toLowerCase();


        const searchableText = `

            ${event.title || ""}

            ${event.description || ""}

            ${event.category || ""}

        `.toLowerCase();


        const matchesSearch =
            searchableText.includes(searchTerm);


        return matchesCategory && matchesSearch;

    });


    eventGrid.innerHTML = filteredEvents
        .map(eventCard)
        .join("");


    if (eventStatus) {

        if (filteredEvents.length > 0) {

            eventStatus.textContent =
                `${filteredEvents.length} event(s) found`;

        } else {

            eventStatus.textContent =
                "No published events match your search yet.";

        }

    }

}


/* ========================================
   LOAD EVENTS FROM FASTAPI
======================================== */

async function loadEvents() {

    if (!eventGrid) {
        return;
    }

    try {

        const response = await fetch(
            "/api/events/",
            {
                headers: {
                    "Accept": "application/json"
                }
            }
        );


        if (!response.ok) {

            throw new Error(
                `Could not load events (${response.status})`
            );

        }


        const data = await response.json();


        allEvents = Array.isArray(data)
            ? data
            : (data.events || []);


        renderEvents();


    } catch (error) {

        console.error(
            "Event loading error:",
            error
        );

        eventGrid.innerHTML = "";

        if (eventStatus) {

            eventStatus.textContent =
                "Events could not be loaded. Please refresh the page or try again later.";

        }

    }

}


/* ========================================
   SEARCH EVENTS
======================================== */

if (eventSearch) {

    eventSearch.addEventListener(
        "input",
        renderEvents
    );

}


/* ========================================
   FILTER EVENTS BY CATEGORY
======================================== */

if (categoryGrid) {

    categoryGrid
        .querySelectorAll("[data-category]")
        .forEach(button => {

            button.addEventListener("click", () => {

                selectedCategory =
                    button.dataset.category || "";


                categoryGrid
                    .querySelectorAll(".category-card")
                    .forEach(card => {

                        card.classList.remove("active");

                    });


                button.classList.add("active");


                renderEvents();


                document
                    .getElementById("events")
                    ?.scrollIntoView({
                        behavior: "smooth"
                    });

            });

        });

}


/* ========================================
   CLEAR SEARCH AND FILTERS
======================================== */

if (clearFilters) {

    clearFilters.addEventListener("click", () => {

        selectedCategory = "";

        if (eventSearch) {
            eventSearch.value = "";
        }


        categoryGrid
            ?.querySelectorAll(".category-card")
            .forEach(card => {

                card.classList.toggle(
                    "active",
                    card.dataset.category === ""
                );

            });


        renderEvents();

    });

}


/* ========================================
   START APPLICATION
======================================== */

loadEvents();
