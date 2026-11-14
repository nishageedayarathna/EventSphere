
const menuButton = document.getElementById("menuButton");
const navLinks = document.getElementById("navLinks");

if (menuButton && navLinks) {

    menuButton.addEventListener("click", () => {
        navLinks.classList.toggle("show");
    });

    navLinks.querySelectorAll("a").forEach(link => {
        link.addEventListener("click", () => {
            navLinks.classList.remove("show");
        });
    });
}


// Check FastAPI connection
async function checkBackend() {

    try {

        const response = await fetch("/api/health");
        const data = await response.json();

        console.log("EventSphere backend connected:", data);

    } catch (error) {

        console.error("Backend connection failed:", error);

    }

}

checkBackend();
