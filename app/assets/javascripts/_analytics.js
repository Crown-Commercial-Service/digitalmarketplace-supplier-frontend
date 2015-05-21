(function() {
  "use strict";
  GOVUK.Tracker.load();
  var cookieDomain = (document.domain === 'www.beta.digitalmarketplace.service.gov.uk') ? '.digitalmarketplace.service.gov.uk' : document.domain;
  GOVUK.analytics = new GOVUK.Tracker({
    universalId: 'UA-49258698-3',
    cookieDomain: cookieDomain
  });
  GOVUK.analytics.trackPageview();
})();
