/**
 * UIHelpers — Sidebar toggle, scroll-down button, and global click handler.
 * Attaches to window.App.UIHelpers
 */
(function () {
    const ns = (window.App = window.App || {});

    function init() {
        const sidebar = document.getElementById("sidebar");
        const sidebarToggle = document.getElementById("sidebar-toggle");
        const chatContainer = document.getElementById("chat-container");
        const scrollDownBtn = document.getElementById("scroll-down-btn");

        // Sidebar toggle
        sidebarToggle.addEventListener("click", () => {
            const isClosed = sidebar.classList.toggle("closed");
            sidebarToggle.title = isClosed ? "Open Sidebar" : "Close Sidebar";
        });

        // Scroll-down visibility
        chatContainer.addEventListener("scroll", () => {
            const threshold = 100;
            const isAtBottom =
                chatContainer.scrollHeight -
                chatContainer.scrollTop -
                chatContainer.clientHeight <=
                threshold;

            if (isAtBottom) {
                scrollDownBtn.classList.remove("show");
            } else {
                scrollDownBtn.classList.add("show");
            }
        });

        // Scroll-down click
        scrollDownBtn.addEventListener("click", () => {
            chatContainer.scrollTo({
                top: chatContainer.scrollHeight,
                behavior: "smooth",
            });
        });

        // Global click — close any open dropdowns
        window.addEventListener("click", () => {
            document.getElementById("upload-menu").classList.remove("show");
            document.getElementById("settings-menu").classList.remove("show");
        });
    }

    // ── Public API ─────────────────────────────────────────────────────────
    ns.UIHelpers = { init };
})();
