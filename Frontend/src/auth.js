/**
 * const refresh_token = null;
 * auth.js — Renderer-side logic for auth.html
 *
 * Handles login/register form submissions, validation, and navigation
 * to the main chat page on successful login.
 */

(function () {
  // ---- DOM refs ----
  const loginForm = document.getElementById("login-form");
  const registerForm = document.getElementById("register-form");
  const statusBar = document.getElementById("status-bar");
  const showRegisterLink = document.getElementById("show-register");
  const showLoginLink = document.getElementById("show-login");

  // ---- Helpers ----
  function showStatus(message, type = "error") {
    statusBar.textContent = message;
    statusBar.className = `status-bar ${type}`;
  }

  function hideStatus() {
    statusBar.className = "status-bar hidden";
  }

  function setLoading(form, loading) {
    const btn = form.querySelector(".btn-primary");
    const text = btn.querySelector(".btn-text");
    const loader = btn.querySelector(".btn-loader");
    btn.disabled = loading;
    text.style.opacity = loading ? "0" : "1";
    loader.classList.toggle("hidden", !loading);
  }

  // ---- Toggle forms ----
  showRegisterLink.addEventListener("click", (e) => {
    e.preventDefault();
    hideStatus();
    loginForm.classList.remove("active");
    registerForm.classList.add("active");
  });

  showLoginLink.addEventListener("click", (e) => {
    e.preventDefault();
    hideStatus();
    registerForm.classList.remove("active");
    loginForm.classList.add("active");
  });

  // ---- Login ----
  loginForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    hideStatus();

    const email = document.getElementById("login-email").value.trim();
    const password = document.getElementById("login-password").value;

    if (!email || !password) {
      showStatus("Please fill in all fields.");
      return;
    }

    if (password.length > 200) {
      showStatus("Password must not exceed 200 characters.");
      return;
    }

    setLoading(loginForm, true);
    try {
      const result = await window.electronAPI.login(email, password);
      console.log("[Auth] login result:", JSON.stringify(result));
      if (result && result.success) {
        showStatus("Login successful! Redirecting…", "success");
        // Stop loading BEFORE navigating — the page is about to be destroyed
        //
        localStorage.setItem("access_token", result.body.access_token);
        localStorage.setItem("refresh_token", result.body.refresh_token);
        setLoading(loginForm, false);
        setTimeout(() => {
          window.electronAPI.navigateToChat();
        }, 600);
        return; // skip the finally block's setLoading
      } else {
        showStatus(result.message || "Login failed. Please try again.");
      }
    } catch (err) {
      console.error("[Auth] login error:", err);
      showStatus(err.message || "An unexpected error occurred.");
    }
    setLoading(loginForm, false);
  });

  // ---- Register ----
  registerForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    hideStatus();

    const username = document.getElementById("reg-username").value.trim();
    const email = document.getElementById("reg-email").value.trim();
    const password = document.getElementById("reg-password").value;
    const confirm = document.getElementById("reg-confirm").value;

    if (!username || !email || !password || !confirm) {
      showStatus("Please fill in all fields.");
      return;
    }

    if (password.length < 6) {
      showStatus("Password must be at least 6 characters.");
      return;
    }

    if (password.length > 200) {
      showStatus("Password must not exceed 200 characters.");
      return;
    }

    // Basic email format check
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      showStatus("Please enter a valid email address.");
      return;
    }

    if (password !== confirm) {
      showStatus("Passwords do not match.");
      return;
    }

    setLoading(registerForm, true);
    try {
      const result = await window.electronAPI.register(
        username,
        email,
        password
      );
      if (result.success) {
        showStatus(
          result.message || "Account created! You can now sign in.",
          "success"
        );
        setTimeout(() => {
          registerForm.classList.remove("active");
          loginForm.classList.add("active");
          hideStatus();
        }, 1500);
      } else {
        showStatus(result.message || "Registration failed.");
      }
    } catch (err) {
      showStatus(err.message || "An unexpected error occurred.");
    } finally {
      setLoading(registerForm, false);
    }
  });
})();
