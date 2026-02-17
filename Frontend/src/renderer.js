/**
 * renderer.js — Thin orchestrator.
 *
 * All logic has been moved into focused modules under ./modules/.
 * This file simply initialises them in the correct order once the DOM is ready.
 *
 * Module load order (via <script> tags in index.html):
 *   1. chatManager.js   — chat messages, sessions, history, document list
 *   2. uploadManager.js  — file / folder / webcam uploads
 *   3. audioManager.js   — microphone recording
 *   4. themeManager.js   — dark / light / custom-image themes
 *   5. uiHelpers.js      — sidebar toggle, scroll-down, dropdown close
 */

window.addEventListener("DOMContentLoaded", () => {
  // Theme runs first so the correct colours are painted before content appears
  window.App.ThemeManager.init();

  // UI chrome (sidebar, scroll button, global click handler)
  window.App.UIHelpers.init();

  // Core chat logic (messages, sessions, history list, document list)
  window.App.ChatManager.init();

  // Upload & audio wire-up (depends on ChatManager being ready)
  window.App.UploadManager.init();
  window.App.AudioManager.init();
});
