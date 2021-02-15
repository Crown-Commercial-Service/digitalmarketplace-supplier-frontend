/*
  The following comments are parsed by Gulp include
  (https://www.npmjs.com/package/gulp-include) which uses
  Sprockets-style (https://github.com/sstephenson/sprockets)
  directives to concatenate multiple Javascript files into one.
*/
//= require _details.polyfill.js

//= require ../../../node_modules/jquery/dist/jquery.js
//= require ../../../node_modules/digitalmarketplace-frontend-toolkit/toolkit/javascripts/list-entry.js
//= require ../../../node_modules/digitalmarketplace-frontend-toolkit/toolkit/javascripts/word-counter.js
//= require ../../../node_modules/govuk_frontend_toolkit/javascripts/govuk/selection-buttons.js
//= require ../../../node_modules/govuk_frontend_toolkit/javascripts/govuk/shim-links-with-button-role.js
//= require ../../../node_modules/govuk_frontend_toolkit/javascripts/govuk/stick-at-top-when-scrolling.js
//= require ../../../node_modules/digitalmarketplace-frontend-toolkit/toolkit/javascripts/shim-links-with-button-role.js
//= require ../../../node_modules/digitalmarketplace-frontend-toolkit/toolkit/javascripts/show-hide-content.js
//= require ../../../node_modules/govuk-frontend/all.js
//= require ../../../node_modules/digitalmarketplace-govuk-frontend/digitalmarketplace/all.js
//= require _selection-buttons.js
//= require _stick-at-top-when-scrolling.js
//= require _stop-scrolling-at-footer.js
//= require category-picker.js

GOVUKFrontend.initAll();
DMGOVUKFrontend.initAll();

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
