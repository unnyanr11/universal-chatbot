document.querySelector("#setup").addEventListener("submit", (event) => {
  event.preventDefault();
  const script = document.createElement("script");
  script.src = "/widget-loader.js";
  script.dataset.assistant = document.querySelector("#assistant").value.trim();
  script.async = true;
  document.body.append(script);
  document.querySelector("#setup").hidden = true;
});
