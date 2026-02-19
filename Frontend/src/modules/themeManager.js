(function () {
  const ns = (window.App = window.App || {});

  function init() {
    const settingsBtn = document.getElementById("settings-btn");
    const settingsMenu = document.getElementById("settings-menu");

    // Settings dropdown toggle
    settingsBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      settingsMenu.classList.toggle("show");
      document.getElementById("upload-menu").classList.remove("show");
    });

    document.querySelectorAll(".appearance-item").forEach((button) => {
      button.addEventListener("click", async (e) => {
        e.stopPropagation();
        const theme = button.getAttribute("data-theme");

        if (theme === "dark") {
          document.body.classList.add("dark-mode");
          document.body.classList.remove("light-mode");
          localStorage.setItem("baseTheme", "dark");
        } else {
          document.body.classList.add("light-mode");
          document.body.classList.remove("dark-mode");
          localStorage.setItem("baseTheme", "light");
        }
        localStorage.setItem("theme", theme);

        settingsMenu.classList.remove("show");
      });
    });

    const savedTheme = localStorage.getItem("theme");
    const savedBaseTheme = localStorage.getItem("baseTheme") || "dark";

    if (savedBaseTheme === "dark") {
      document.body.classList.add("dark-mode");
      document.body.classList.remove("light-mode");
    } else {
      document.body.classList.add("light-mode");
      document.body.classList.remove("dark-mode");
    }
  }

  ns.ThemeManager = { init };
})();
