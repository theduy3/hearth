"use strict";
(async () => {
  const main = document.querySelector("main");
  const capability = location.hash.slice(1);
  history.replaceState(null, "", location.pathname);
  const show = html => {
    const parsed = new DOMParser().parseFromString(html, "text/html");
    main.innerHTML = parsed.querySelector("main").innerHTML;
  };
  const post = (path, fields) => fetch(path, {
    method: "POST", body: new URLSearchParams(fields), credentials: "omit",
    mode: "same-origin", redirect: "error", cache: "no-store",
    referrerPolicy: "no-referrer", signal: AbortSignal.timeout(25000)
  });
  if (!/^[A-Za-z0-9_-]{32,128}$/.test(capability)) {
    main.textContent = "Open your private approval link from Telegram.";
    return;
  }
  try {
    const response = await post("/approval/view", {capability});
    show(await response.text());
  } catch {
    main.textContent = "This approval could not be loaded. Open the latest link from Telegram.";
    return;
  }
  document.addEventListener("submit", async event => {
    if (!main.contains(event.target)) return;
    event.preventDefault();
    const decision = event.submitter?.value;
    if (decision !== "allow" && decision !== "deny") return;
    main.querySelectorAll("button").forEach(button => { button.disabled = true; });
    try {
      const response = await post("/approval/confirm", {capability, decision});
      show(await response.text());
    } catch {
      main.textContent = "The outcome could not be confirmed. Check the calendar before requesting another change.";
    }
  });
})();
