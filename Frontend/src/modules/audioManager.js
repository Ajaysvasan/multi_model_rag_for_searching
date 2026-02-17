(function () {
  const ns = (window.App = window.App || {});

  let mediaRecorder = null;
  let audioChunks = [];
  let isRecording = false;

  async function toggleRecording() {
    const micBtn = document.getElementById("mic-btn");
    const messageInput = document.getElementById("message-input");

    if (!isRecording) {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: true,
        });

        let mimeType = "audio/webm";
        let extension = "webm";

        if (MediaRecorder.isTypeSupported("audio/mpeg")) {
          mimeType = "audio/mpeg";
          extension = "mp3";
        } else if (MediaRecorder.isTypeSupported("audio/wav")) {
          mimeType = "audio/wav";
          extension = "wav";
        } else if (MediaRecorder.isTypeSupported("audio/ogg; codecs=opus")) {
          mimeType = "audio/ogg; codecs=opus";
          extension = "ogg";
        } else if (MediaRecorder.isTypeSupported("audio/mp4")) {
          mimeType = "audio/mp4";
          extension = "m4a";
        }

        mediaRecorder = new MediaRecorder(stream, { mimeType });
        audioChunks = [];

        mediaRecorder.ondataavailable = (event) => {
          if (event.data.size > 0) {
            audioChunks.push(event.data);
          }
        };

        mediaRecorder.onstop = async () => {
          const audioBlob = new Blob(audioChunks, { type: mimeType });

          const audioFile = new File(
            [audioBlob],
            `speech_query_${Date.now()}.${extension}`,
            { type: mimeType }
          );

          ns.ChatManager.pushUploadedDoc({
            name: audioFile.name,
            type: "audio",
            path: URL.createObjectURL(audioBlob),
            file: audioFile,
          });

          ns.ChatManager.renderUploadedDocs();

          stream.getTracks().forEach((track) => track.stop());
        };

        mediaRecorder.start();
        isRecording = true;
        micBtn.classList.add("recording");
        micBtn.title = "Stop Recording";
        messageInput.placeholder = "Recording... Speak now.";
      } catch (err) {
        console.error("Error accessing microphone:", err);
        alert("Could not access microphone. Please check permissions.");
      }
    } else {
      mediaRecorder.stop();
      isRecording = false;
      micBtn.classList.remove("recording");
      micBtn.title = "Record Speech Query";
      messageInput.placeholder = "Ask anything about your documents...";
    }
  }

  function init() {
    document
      .getElementById("mic-btn")
      .addEventListener("click", toggleRecording);
  }

  ns.AudioManager = { init, toggleRecording };
})();
