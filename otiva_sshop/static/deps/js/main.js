
const menuButton = document.getElementById("menuButton");
const nav = document.getElementById("nav");

const infoDropdown = document.querySelector(".nav-dropdown");
const dropdownButton = document.querySelector(".dropdown-button");


// ======================================
// Мобильное меню
// ======================================

if (menuButton) {
    menuButton.addEventListener("click", () => {
        nav.classList.toggle("open");
    });
}


// ======================================
// Dropdown "Информация"
// ======================================

if (dropdownButton) {

    dropdownButton.addEventListener("click", (event) => {

        // На компьютере оставляем hover
        if (window.innerWidth > 800) {
            return;
        }

        event.preventDefault();

        infoDropdown.classList.toggle("open");
    });
}


// ======================================
// Закрытие мобильного меню
// после перехода по ссылке
// ======================================

const navLinks = document.querySelectorAll(
    ".nav-link:not(.dropdown-button), .dropdown-link"
);

navLinks.forEach((link) => {

    link.addEventListener("click", () => {

        nav.classList.remove("open");
        infoDropdown?.classList.remove("open");

    });

});

