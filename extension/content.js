// --- PING HANDLER (must be at top, outside the IIFE) ---
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg && msg.type === "PING") {
    sendResponse({ ok: true }); // synchronous response so background knows we're alive
    return; // IMPORTANT: no async work here
  }
});

// --------------------------------------------------------
(function () {
  const HOST_ID = "__ethicsbot_sidebar_host";

  // Ensure a single sidebar (Shadow DOM) exists
  function ensureSidebar() {
    let host = document.getElementById(HOST_ID);
    if (host) return host;

    host = document.createElement("div");
    host.id = HOST_ID;
    host.style.position = "fixed";
    host.style.top = "96px";
    host.style.right = "24px";
    host.style.zIndex = "2147483647";
    host.style.width = "360px";
    host.style.height = "auto";
    host.style.pointerEvents = "none"; // container ignores events; inner card re-enables
    document.documentElement.appendChild(host);

    const shadow = host.attachShadow({ mode: "open" });
    const style = document.createElement("style");
    style.textContent = `
          :host { all: initial; }
          .card {
              pointer-events: auto;
              font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
              background: #fff;
              color: #111;
              border-radius: 12px;
              box-shadow: 0 10px 30px rgba(0,0,0,.25);
              border: 1px solid rgba(0,0,0,.08);
              overflow: hidden;              /* keep rounded corners */
              min-width: 280px;
              max-height: 70vh;              /* cap overall height */
              display: flex;                 /* flex layout */
              flex-direction: column;
          }
          .header {
              display: flex;
              align-items: center;
              gap: 8px;
              padding: 10px 12px;
              font-weight: 700;
              font-size: 14px;
              cursor: move;
              background: #f7f7f7;
              flex: 0 0 auto;                /* header fixed height */
          }
          .badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 700;
            color: #111;
          }
          .body {
              padding: 10px 12px;
              font-size: 13px;
              line-height: 1.4;
              white-space: pre-wrap;
              overflow: auto;                /* scrolls when long */
              max-height: 50vh;              /* extra safety */
          }
          .row {
              display: flex;
              gap: 8px;
              padding: 8px 12px 12px;
              flex: 0 0 auto;                /* buttons stay visible */
          }
          .btn {
            pointer-events: auto;
            border: 1px solid rgba(0,0,0,.15);
            background: #fff; color: #111;
            border-radius: 8px; padding: 6px 10px;
            font-size: 12px; cursor: pointer;
          }
          .btn:hover { background: #f2f2f2; }
          .close {
            margin-left: auto;
            border: none; background: transparent;
            font-size: 18px; cursor: pointer;
          }
          .muted { color: #666; font-size: 12px; }
          .resizer {
              width: 14px; height: 14px;
              position: absolute; right: 6px; bottom: 6px;
              cursor: nwse-resize;
              opacity: 0.6;
              background:
                  linear-gradient(135deg, transparent 50%, rgba(0,0,0,.25) 50%),
                  linear-gradient(45deg, rgba(0,0,0,.05) 25%, transparent 25%),
                  linear-gradient(45deg, transparent 75%, rgba(0,0,0,.05) 75%);
              background-size: 100% 100%, 8px 8px, 8px 8px;
              background-position: 0 0, 0 0, 4px 4px;
              border-radius: 4px;
          }
          .spinner {
            width: 16px; height: 16px;
            border: 2px solid #ccc; border-top-color: #666;
            border-radius: 50%; animation: spin 0.8s linear infinite;
            display: inline-block; vertical-align: middle; margin-left: 6px;
          }
          @keyframes spin { to { transform: rotate(360deg); } }
        `;

    const wrap = document.createElement("div");
    wrap.className = "card";
    wrap.innerHTML = `
          <div class="header">
            <span id="badge" class="badge">Watchdog</span>
            <span id="status" class="muted"></span>
            <button class="close" title="Close" aria-label="Close">×</button>
          </div>
          <div class="body" id="summary">Select text and choose “Assess with EthicsBot Watchdog”.</div>
          <div class="row">
            <button id="copy" class="btn" style="display:none;">Copy</button>
            <button id="openui" class="btn">Open Local UI</button>
            <span id="extra" class="muted"></span>
          </div>
          <div class="resizer" id="resizer" title="Resize"></div>
        `;

    shadow.append(style, wrap);
    host.__shadow = shadow;

    // Close button
    shadow
      .querySelector(".close")
      .addEventListener("click", () => host.remove());

    // Dragging (on header)
    let dragging = false,
      startX = 0,
      startY = 0,
      origTop = 0,
      origRight = 0;
    const header = shadow.querySelector(".header");
    header.addEventListener("mousedown", (e) => {
      dragging = true;
      startX = e.clientX;
      startY = e.clientY;
      const rect = host.getBoundingClientRect();
      origTop = rect.top;
      origRight = window.innerWidth - rect.right;
      e.preventDefault();
    });
    window.addEventListener("mousemove", (e) => {
      if (!dragging) return;
      const dx = e.clientX - startX;
      const dy = e.clientY - startY;
      host.style.top = Math.max(8, origTop + dy) + "px";
      host.style.right = Math.max(8, origRight - dx) + "px";
    });
    window.addEventListener("mouseup", () => (dragging = false));

    // Resizing (on resizer)
    const resizer = shadow.getElementById("resizer");
    let resizing = false,
      startRX = 0,
      startRY = 0,
      startW = 0,
      startH = 0;

    resizer.addEventListener("mousedown", (e) => {
      resizing = true;
      startRX = e.clientX;
      startRY = e.clientY;
      const rect = host.getBoundingClientRect();
      startW = rect.width;
      startH = rect.height;
      e.preventDefault();
    });

    window.addEventListener("mousemove", (e) => {
      if (!resizing) return;
      const dx = e.clientX - startRX;
      const dy = e.clientY - startRY;
      const w = Math.max(280, startW + dx);
      const h = Math.max(180, startH + dy);
      host.style.width = w + "px";
      // Let the card grow in height up to viewport cap
      shadow.querySelector(".card").style.maxHeight = "80vh";
      host.style.height = h + "px";
    });

    window.addEventListener("mouseup", () => (resizing = false));

    // Buttons
    shadow.getElementById("copy").addEventListener("click", async () => {
      const summary = shadow.getElementById("summary").textContent || "";
      try {
        await navigator.clipboard.writeText(summary);
        setStatus("Copied.");
      } catch {
        setStatus("Copy failed.");
      }
    });
    shadow.getElementById("openui").addEventListener("click", () => {
      // Opens your local Gradio UI (if running)
      window.open("http://localhost:7860", "_blank", "noopener");
    });

    // Helpers
    function setStatus(msg, busy = false) {
      const s = shadow.getElementById("status");
      s.textContent = msg;
      s.innerHTML = busy ? `${msg} <span class="spinner"></span>` : msg;
    }
    host.__setStatus = setStatus;

    return host;
  }

  function setBadge(shadow, label, risk) {
    const el = shadow.getElementById("badge");
    const r = Number.isFinite(Number(risk)) ? Number(risk) : 0;
    const bg =
      label === "Likely Misinfo"
        ? "#ffd5d5"
        : label === "Needs Verification"
        ? "#fff5cc"
        : "#d9f7d9";
    el.style.background = bg;
    el.textContent = `Watchdog: ${label} (risk ${r.toFixed(2)})`;
  }

  function setSummary(shadow, text, signals = [], incidents = []) {
    const body = shadow.getElementById("summary");
    const lines = [text.trim() || "Assessment complete."];
    if (signals.length) {
      const sig = signals
        .map((s) => `- ${s.name}: ${(s.score ?? 0).toFixed(2)}`)
        .join("\n");
      lines.push("\nSignals:\n" + sig);
    }
    if (incidents.length) {
      const inc = incidents
        .slice(0, 3)
        .map((e) => `- ${e.snippet || ""}`)
        .join("\n");
      lines.push("\nRelated incidents:\n" + inc);
    }
    body.textContent = lines.join("\n");
  }

  chrome.runtime.onMessage.addListener((msg) => {
    if (!msg) return;
    const host = ensureSidebar();
    const shadow = host.__shadow;

    if (msg.type === "WATCHDOG_BUSY") {
      host.__setStatus?.("Assessing…", true);
      // Hide Copy button while assessing
      shadow.getElementById("copy").style.display = "none";
      return;
    }
    if (msg.type === "WATCHDOG_ERROR") {
      setBadge(shadow, "Error", 0);
      setSummary(shadow, String(msg.payload || "Error"));
      host.__setStatus?.("");
      // Hide Copy button while assessing
      shadow.getElementById("copy").style.display = "none";
      return;
    }
    if (msg.type === "WATCHDOG_RESULT") {
      const {
        label = "Result",
        overall_risk = 0,
        summary = "",
        signals = [],
        incidents = [],
      } = msg.payload || {};
      setBadge(shadow, label, overall_risk);
      setSummary(shadow, summary, signals, incidents);
      host.__setStatus?.("Done");
      setTimeout(() => host.__setStatus?.(""), 1500);
      // Now show the Copy button
      shadow.getElementById("copy").style.display = "inline-block";
      return;
    }
  });
})();
