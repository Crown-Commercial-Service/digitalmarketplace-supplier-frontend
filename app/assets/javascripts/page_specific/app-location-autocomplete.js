;(function() {

  "use strict";

  var CountryAutocomplete = function() {

    openregisterLocationPicker({
      selectElement: document.getElementById('input-country'),
      url: '/suppliers/static/location-autocomplete-graph.json'
    });

    document.getElementById("input-country").addEventListener("keyup", function(event) {
      // Clear the input value of the country select input, if the autocomplete is cleared.
      if (this.value.length < 2) {
        document.querySelector('#input-country-select').selectedIndex = -1;
      }
    });
  };

  CountryAutocomplete();
})();
