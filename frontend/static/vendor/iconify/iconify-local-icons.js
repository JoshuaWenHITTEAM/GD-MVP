(function () {
  var collections = [
    "/static/vendor/iconify/material-symbols.json",
    "/static/vendor/iconify/mdi.json"
  ];

  function register(collection) {
    if (window.Iconify && typeof window.Iconify.addCollection === "function") {
      window.Iconify.addCollection(collection);
    }
  }

  collections.forEach(function (url) {
    fetch(url)
      .then(function (response) {
        if (!response.ok) throw new Error("Unable to load " + url);
        return response.json();
      })
      .then(register)
      .catch(function (error) {
        console.warn(error.message);
      });
  });
})();
