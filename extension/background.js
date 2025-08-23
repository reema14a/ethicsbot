const API = "http://127.0.0.1:8000/watch/text";

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "watchdogAssess",
    title: "Assess with EthicsBot Watchdog",
    contexts: ["selection"],
  });
});

function injectOverlay(tabId, payload) {
  return chrome.scripting.executeScript({
    target: { tabId },
    world: "MAIN",
    func: (data) => {
      // Remove any old overlay
      const old = document.getElementById("__ethicsbot_watchdog");
      if (old) old.remove();

      const wrap = document.createElement("div");
      wrap.id = "__ethicsbot_watchdog";
      wrap.style.position = "fixed";
      wrap.style.top = "20px";
      wrap.style.right = "20px";
      wrap.style.zIndex = "999999999"; // max priority
      wrap.style.padding = "16px";
      wrap.style.borderRadius = "12px";
      wrap.style.boxShadow = "0 6px 18px rgba(0,0,0,0.35)";
      wrap.style.maxWidth = "380px";
      wrap.style.fontFamily = "system-ui, sans-serif";
      wrap.style.fontSize = "14px";
      wrap.style.lineHeight = "1.4";
      wrap.style.background =
        data.label === "Likely Misinfo"
          ? "#ff4d4d"
          : data.label === "Needs Verification"
          ? "#ffec99"
          : "#4dff88";
      wrap.style.color = "#111";
      wrap.style.opacity = "0.95";

      // Title
      const title = document.createElement("div");
      title.style.fontWeight = "700";
      title.style.marginBottom = "6px";
      title.textContent = `Watchdog: ${data.label} (risk ${data.risk.toFixed(
        2
      )})`;
      wrap.appendChild(title);

      // Summary
      const body = document.createElement("div");
      body.textContent = data.summary || "Assessment complete.";
      wrap.appendChild(body);

      // Close button
      const close = document.createElement("button");
      close.textContent = "×";
      close.style.position = "absolute";
      close.style.top = "4px";
      close.style.right = "8px";
      close.style.border = "none";
      close.style.background = "transparent";
      close.style.fontSize = "20px";
      close.style.cursor = "pointer";
      close.onclick = () => wrap.remove();
      wrap.appendChild(close);

      document.body.appendChild(wrap);
    },
    args: [payload],
  });
}

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId !== "watchdogAssess" || !info.selectionText || !tab?.id)
    return;

  try {
    console.log("[Watchdog] sending to API:", API);
    const res = await fetch(API, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text: info.selectionText,
        k: 3,
        model: "llama3.2",
      }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    console.log("[Watchdog] API response:", data);

    // Try to inject an overlay banner into the page
    // await injectOverlay(tab.id, data);

    const title = `Watchdog: ${data.label} (risk ${data.overall_risk.toFixed(
      2
    )})`;
    const message = data.summary
      ? data.summary.slice(0, 200) + (data.summary.length > 200 ? "…" : "")
      : "Assessment complete.";

    chrome.notifications.create({
      type: "basic",
      iconUrl: "icon-128.png", // add any PNG in extension folder (128x128 recommended)
      title: title,
      message: message,
    });
    console.log("[Watchdog] overlay injected");
  } catch (err) {
    console.error("[Watchdog] failed to inject overlay:", err);
    // Fallback to a system notification
    try {
      chrome.notifications.create({
        type: "basic",
        iconUrl: "icon-128.png", // optional; add an icon to your extension folder
        title: `Watchdog: ${new Date().toLocaleTimeString()}`,
        message: `Assessment: ${
          err && err.message ? err.message : "see console"
        }`,
      });
    } catch (e2) {
      console.error("[Watchdog] notifications failed:", e2);
    }
  }
});
