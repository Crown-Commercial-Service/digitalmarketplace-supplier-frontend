;(function() {

  "use strict";

  var CountryAutocomplete = function() {

    openregisterLocationPicker({
      selectElement: document.getElementById('location-autocomplete'),
      url: '/suppliers/static/location-autocomplete-graph.json'
    });

    $('#location-autocomplete').keyup(function(event) {
      // Clear the input value of the country select input, if the autocomplete is cleared.
      if ($(this).val().length < 2) {
        $('#location-autocomplete-select').val('');
      };
    });
  };

  CountryAutocomplete();
})();
