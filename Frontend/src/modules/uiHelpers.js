(function () {
  const ns = (window.App = window.App || {});

  function init() {
    const sidebar = document.getElementById("sidebar");
    const sidebarToggle = document.getElementById("sidebar-toggle");
    const chatContainer = document.getElementById("chat-container");
    const scrollDownBtn = document.getElementById("scroll-down-btn");

    sidebarToggle.addEventListener("click", () => {
      const isClosed = sidebar.classList.toggle("closed");
      sidebarToggle.title = isClosed ? "Open Sidebar" : "Close Sidebar";
    });

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

    scrollDownBtn.addEventListener("click", () => {
      chatContainer.scrollTo({
        top: chatContainer.scrollHeight,
        behavior: "smooth",
      });
    });

    window.addEventListener("click", () => {
      document.getElementById("upload-menu").classList.remove("show");
      document.getElementById("settings-menu").classList.remove("show");
    });
  }

  ns.UIHelpers = { init };
})();
