(function () {
  var script = document.currentScript;
  if (!script) {
    return;
  }

  var loaderUrl = new URL("./widget/widget_loader.js?v=1.0.0", script.src).toString();
  import(loaderUrl)
    .then(function (module) {
      if (module && typeof module.bootstrap === "function") {
        module.bootstrap(script);
      }
    })
    .catch(function (error) {
      console.error("Advanced Business RAG widget failed to load.", error);
    });
})();
