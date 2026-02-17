/**
 * RAGService — Connects the Electron frontend to the FastAPI backend.
 *
 * Endpoint base URL is configurable via the BACKEND_URL constant below.
 * No authentication headers are sent.
 */

const BACKEND_URL = "http://localhost:8000";

class RAGService {
  /**
   * Send a text query to the RAG backend and return { text, sources }.
   */
  async getResponse(message) {
    try {
      const res = await fetch(`${BACKEND_URL}/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: message }),
      });

      if (!res.ok) {
        throw new Error(`Backend returned HTTP ${res.status}`);
      }

      const data = await res.json();

      // The FastAPI endpoint returns { response, sources }.
      // Normalise to the shape the renderer expects: { text, sources }.
      return {
        text: data.response || data.text || "No response received.",
        sources: (data.sources || []).map((s) => {
          if (typeof s === "string") {
            return { name: s.split("/").pop().split("\\").pop(), path: s };
          }
          return s;
        }),
      };
    } catch (error) {
      console.error("RAGService.getResponse error:", error);
      return {
        text: `⚠️ Could not reach the backend at \`${BACKEND_URL}/query\`. Make sure the server is running.\n\nError: ${error.message}`,
        sources: [],
      };
    }
  }

  /**
   * Send a speech/audio buffer to the backend for STT + RAG processing.
   */
  async processSpeechQuery(audioBuffer, fileName) {
    try {
      const formData = new FormData();
      formData.append("audio", new Blob([audioBuffer]), fileName);
      formData.append("fileName", fileName);

      const res = await fetch(`${BACKEND_URL}/speech-query`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        throw new Error(`Backend returned HTTP ${res.status}`);
      }

      const data = await res.json();

      return {
        text: data.response || data.text || "No response received.",
        sources: (data.sources || []).map((s) => {
          if (typeof s === "string") {
            return { name: s.split("/").pop().split("\\").pop(), path: s };
          }
          return s;
        }),
      };
    } catch (error) {
      console.error("RAGService.processSpeechQuery error:", error);
      return {
        text: `⚠️ Speech query failed. Make sure the backend is running.\n\nError: ${error.message}`,
        sources: [],
      };
    }
  }

  /**
   * Upload document file paths to the backend for ingestion.
   */
  async uploadDocuments(filePaths, type = "document") {
    try {
      const res = await fetch(`${BACKEND_URL}/upload`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filePaths, type }),
      });

      if (!res.ok) {
        throw new Error(`Backend returned HTTP ${res.status}`);
      }

      return await res.json();
    } catch (error) {
      console.error("RAGService.uploadDocuments error:", error);
      return {
        success: false,
        message: `Upload failed — backend unreachable. ${error.message}`,
      };
    }
  }
}

module.exports = new RAGService();
