// extension/background.js
const API = "http://127.0.0.1:8000/watch/text";

// Create context menu on install
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "watchdogAssess",
    title: "Assess with EthicsBot Watchdog",
    contexts: ["selection"],
  });
});

// ---- helpers ----
async function ensureContent(tabId) {
  const ping = () =>
    new Promise((resolve) => {
      let done = false;
      try {
        chrome.tabs.sendMessage(tabId, { type: "PING" }, (resp) => {
          done = true;
          resolve(Boolean(resp && resp.ok));
        });
        setTimeout(() => !done && resolve(false), 300);
      } catch {
        resolve(false);
      }
    });

  if (await ping()) return true;

  try {
    await chrome.scripting.executeScript({
      target: { tabId },
      files: ["content.js"],
    });
  } catch (e) {
    console.warn("[Watchdog] executeScript failed:", e?.message || e);
    return false; // restricted page
  }
  return await ping();
}

// Send a message but do NOT wait for a response (avoids “port closed” noise)
async function post(tabId, msg) {
  const ok = await ensureContent(tabId);
  if (!ok) throw new Error("Cannot inject content script on this page.");
  try {
    chrome.tabs.sendMessage(tabId, msg); // no callback on purpose
  } catch (e) {
    throw e;
  }
}

async function notify(title, message) {
  // Safe even if no packaged icon
  const tiny =
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAASsJTYQAAAAASUVORK5CYII=";
  const iconUrl = (() => {
    try {
      return chrome.runtime.getURL("icon128.png");
    } catch {
      return tiny;
    }
  })();
  try {
    await chrome.notifications.create({
      type: "basic",
      iconUrl,
      title: String(title || "Watchdog"),
      message: String(message || ""),
    });
  } catch (e) {
    console.error("[Watchdog] notification failed:", e?.message || e);
  }
}

// ---- context menu → assess ----
chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId !== "watchdogAssess" || !info.selectionText || !tab?.id)
    return;
  const tabId = tab.id;

  try {
    await post(tabId, { type: "WATCHDOG_BUSY" });

    const res = await fetch(API, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text: info.selectionText,
        k: 3,
        model: "llama3.2", // or remove to use server default
      }),
    });

    if (!res.ok) {
      const txt = await res.text().catch(() => "");
      throw new Error(`HTTP ${res.status}${txt ? `: ${txt}` : ""}`);
    }

    const data = await res.json();
    const overallRisk = Number(data.overall_risk ?? data.risk ?? 0);

    await post(tabId, {
      type: "WATCHDOG_RESULT",
      payload: {
        label: data.label ?? "Result",
        overall_risk: Number.isFinite(overallRisk) ? overallRisk : 0,
        summary: (data.summary || "Assessment complete.").toString(),
        signals: Array.isArray(data.signals) ? data.signals : [],
        incidents: Array.isArray(data.incidents) ? data.incidents : [],
      },
    });
  } catch (e) {
    const msg = e?.message || String(e) || "Unknown error";
    console.error("[Watchdog] assess error:", msg);

    // Try to show the error in-page; if not possible, notify
    try {
      await post(tabId, { type: "WATCHDOG_ERROR", payload: msg });
    } catch (err2) {
      console.warn(
        "[Watchdog] could not post error to tab:",
        err2?.message || err2
      );
      await notify("Watchdog Error", msg);
    }
  }
});

// ---- toolbar button → show “Ready” sidebar ----
chrome.action.onClicked.addListener(async (tab) => {
  if (!tab?.id) return;
  const tabId = tab.id;
  try {
    await post(tabId, {
      type: "WATCHDOG_RESULT",
      payload: {
        label: "Ready",
        risk: 0,
        summary:
          "Select text on the page, then right‑click → “Assess with EthicsBot Watchdog”.",
        signals: [],
        incidents: [],
      },
    });
  } catch (e) {
    console.warn("[Watchdog] toolbar click couldn’t inject:", e?.message || e);
    await notify(
      "EthicsBot Watchdog",
      "Open a normal https page and try again."
    );
  }
});
