/**
 * UploadManager — Handles file uploads, webcam capture, and the upload dropdown.
 * Attaches to window.App.UploadManager
 */
(function () {
    const ns = (window.App = window.App || {});

    // ── Webcam capture ─────────────────────────────────────────────────────

    async function handleWebcamCapture() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ video: true });

            const video = document.createElement("video");
            video.srcObject = stream;
            video.style.display = "none";
            document.body.appendChild(video);
            video.play();

            await new Promise((resolve) => {
                video.onloadedmetadata = resolve;
            });

            const canvas = document.createElement("canvas");
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            const ctx = canvas.getContext("2d");
            ctx.drawImage(video, 0, 0);

            stream.getTracks().forEach((track) => track.stop());
            document.body.removeChild(video);

            canvas.toBlob(async (blob) => {
                const fileName = `webcam_${Date.now()}.png`;
                const arrayBuffer = await blob.arrayBuffer();
                const imageBuffer = new Uint8Array(arrayBuffer);

                const result = await window.electronAPI.uploadWebcam(
                    imageBuffer,
                    fileName
                );

                if (result.success) {
                    if (result.uploadedFiles) {
                        ns.ChatManager.pushUploadedDocs(result.uploadedFiles);
                        ns.ChatManager.renderUploadedDocs();
                    }
                    await ns.ChatManager.refreshDocumentList();
                } else {
                    ns.ChatManager.appendMessage(
                        false,
                        `❌ **Error**: ${result.message}`
                    );
                }
            }, "image/png");
        } catch (error) {
            console.error("Webcam capture error:", error);
            alert("Could not access webcam. Please check permissions.");
        }
    }

    // ── Generic upload handler ─────────────────────────────────────────────

    async function handleUpload(type, sourceButton = null) {
        const uploadBtn = sourceButton || document.getElementById("upload-btn");
        const uploadMenu = document.getElementById("upload-menu");
        const originalHTML = uploadBtn.innerHTML;

        if (uploadMenu) {
            uploadMenu.classList.remove("show");
        }

        if (type === "webcam") {
            await handleWebcamCapture();
            return;
        }

        try {
            uploadBtn.disabled = true;
            uploadBtn.innerHTML = '<span class="loading-spinner"></span>';

            const result = await window.electronAPI.uploadDocuments(type);

            if (result.success) {
                if (result.uploadedFiles) {
                    ns.ChatManager.pushUploadedDocs(result.uploadedFiles);
                    ns.ChatManager.renderUploadedDocs();
                } else {
                    ns.ChatManager.appendMessage(
                        false,
                        `✅ **Success**: ${result.message}`
                    );
                }
                await ns.ChatManager.refreshDocumentList();
            } else if (result.message !== "Upload canceled") {
                ns.ChatManager.appendMessage(
                    false,
                    `❌ **Error**: ${result.message}`
                );
            }
        } catch (error) {
            console.error("Upload Error:", error);
            ns.ChatManager.appendMessage(
                false,
                `❌ **Error**: An unexpected error occurred during ${type} upload.`
            );
        } finally {
            uploadBtn.disabled = false;
            uploadBtn.innerHTML = originalHTML;
        }
    }

    // ── Init ───────────────────────────────────────────────────────────────

    function init() {
        // Upload button dropdown toggle
        document.getElementById("upload-btn").addEventListener("click", (e) => {
            e.stopPropagation();
            document.getElementById("upload-menu").classList.toggle("show");
        });

        // Upload type buttons
        document.querySelectorAll(".upload-item").forEach((button) => {
            button.addEventListener("click", (e) => {
                e.stopPropagation();
                const type = button.getAttribute("data-type");
                handleUpload(type);
            });
        });
    }

    // ── Public API ─────────────────────────────────────────────────────────
    ns.UploadManager = { init, handleUpload };
})();
