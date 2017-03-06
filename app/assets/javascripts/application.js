/*
  The following comments are parsed by Gulp include
  (https://www.npmjs.com/package/gulp-include) which uses
  Sprockets-style (https://github.com/sstephenson/sprockets)
  directives to concatenate multiple Javascript files into one.
*/
//= include ../../../node_modules/govuk_frontend_toolkit/javascripts/vendor/polyfills/bind.js
//= include _details.polyfill.js

//= include ../../../bower_components/jquery/dist/jquery.js
//= include ../../../bower_components/hogan/web/builds/3.0.2/hogan-3.0.2.js
//= include ../../../bower_components/digitalmarketplace-frontend-toolkit/toolkit/javascripts/list-entry.js
//= include ../../../bower_components/digitalmarketplace-frontend-toolkit/toolkit/javascripts/word-counter.js
//= include ../../../bower_components/digitalmarketplace-frontend-toolkit/toolkit/javascripts/validation.js
//= include ../../../node_modules/govuk_frontend_toolkit/javascripts/govuk/selection-buttons.js
//= include ../../../node_modules/govuk_frontend_toolkit/javascripts/govuk/shim-links-with-button-role.js
//= include ../../../node_modules/govuk_frontend_toolkit/javascripts/govuk/stick-at-top-when-scrolling.js
//= include ../../../node_modules/govuk_frontend_toolkit/javascripts/govuk/stop-scrolling-at-footer.js
//= include ../../../bower_components/digitalmarketplace-frontend-toolkit/toolkit/javascripts/show-hide-content.js
//= include _analytics.js
//= include _selection-buttons.js
//= include _shim-links-with-button-role.js
//= include _stick-at-top-when-scrolling.js
//= include category-picker.js

(function(GOVUK, GDM) {

  "use strict";

  var module;

  if((typeof console === 'undefined') || (typeof console.time === 'undefined') || (typeof console.timeEnd === 'undefined')) {
    console = {
      log: function () {},
      time: function () {},
      timeEnd: function () {}
    };
  }

  if (
    (GDM.debug = !window.location.href.match(/gov.uk/) && !window.jasmine)
  ) {
    console.log(
      "%cDebug mode %cON",
      "color:#550; background:yellow; font-size: 11pt",
      "color:yellow; background: #550;font-size:11pt"
    );
    console.time("Modules loaded");
  }

  // Initialise our modules
  for (module in GDM) {

    if (GDM.debug && module !== "debug") {
      console.log(
        "%cLoading module %c" + module,
        "color:#6a6; background:#dfd; font-size: 11pt",
        "color:#dfd; background:green; font-size: 11pt"
      );
    }

    if ("function" === typeof GDM[module].init) {
      // If a module has an init() method then we want that to be called here
      GDM[module].init();
    } else if ("function" === typeof GDM[module]) {
      // If a module doesn't have an interface then call it directly
      GDM[module]();
    }

  }

  GOVUK.GDM = GDM;

  if (GDM.debug) console.timeEnd("Modules loaded");

}).apply(this, [GOVUK||{}, GOVUK.GDM||{}]);
