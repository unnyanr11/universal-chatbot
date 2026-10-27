/** Version 1 authenticated preview loader; no host-page collection or message bridge. */
(() => {
  const script = document.currentScript;
  if (!(script instanceof HTMLScriptElement) || !script.dataset.assistant)
    return;
  const origin = new URL(script.src).origin;
  const url = new URL(
    script.dataset.public === "1" ? "/chat.html" : "/",
    origin,
  );
  url.searchParams.set("widget", "1");
  url.searchParams.set("assistant", script.dataset.assistant);
  if (script.dataset.identity) {
    url.hash = new URLSearchParams({
      identity: script.dataset.identity,
    }).toString();
    delete script.dataset.identity;
  }
  const host = document.createElement("div");
  const shadow = host.attachShadow({ mode: "open" });
  const style = document.createElement("style");
  style.textContent =
    ":host{all:initial}button{position:fixed;right:24px;bottom:24px;background:#1e5548;color:white;border:0;border-radius:28px;padding:16px 22px;font:14px system-ui;cursor:pointer;z-index:2147483000}iframe{position:fixed;right:20px;bottom:88px;width:min(440px,calc(100vw - 40px));height:min(720px,calc(100dvh - 115px));border:1px solid #dce3d5;border-radius:14px;background:#fff;box-shadow:0 12px 70px #1233;z-index:2147483000}iframe[hidden]{display:none}";
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = "Chat with us";
  button.setAttribute("aria-expanded", "false");
  const frame = document.createElement("iframe");
  frame.title = "Business assistant";
  frame.hidden = true;
  frame.setAttribute("sandbox", "allow-scripts allow-same-origin allow-forms");
  frame.referrerPolicy = "no-referrer";
  button.addEventListener("click", () => {
    if (!frame.src) frame.src = url.href;
    frame.hidden = !frame.hidden;
    button.setAttribute("aria-expanded", String(!frame.hidden));
    button.textContent = frame.hidden ? "Chat with us" : "Close chat";
    if (frame.hidden) button.focus();
  });
  shadow.append(style, frame, button);
  document.body.append(host);
  // A host SPA may dispatch this event on the script to remove the integration.
  script.addEventListener("assistant:destroy", () => host.remove(), {
    once: true,
  });
})();
