(function() {
  "use strict";
  GOVUK.Tracker.load();
  var cookieDomain = (document.domain === 'www.beta.digitalmarketplace.service.gov.uk') ? '.digitalmarketplace.service.gov.uk' : document.domain;
  var property = (document.domain === 'www.digitalmarketplace.service.gov.uk') ? 'UA-49258698-1' : 'UA-49258698-3';
  GOVUK.analytics = new GOVUK.Tracker({
    universalId: property,
    cookieDomain: cookieDomain
  });
  GOVUK.analytics.trackPageview();
})();
