(function (root) {
  "use strict";

  root.GOVUK.GDM = root.GOVUK.GDM || {};
  root.GOVUK.GDM.analytics = {
    'register': function () {
      GOVUK.Analytics.load();
      var cookieDomain = (root.document.domain === 'www.beta.digitalmarketplace.service.gov.uk') ? '.digitalmarketplace.service.gov.uk' : root.document.domain;
      var property = (root.document.domain === 'www.digitalmarketplace.service.gov.uk') ? 'UA-49258698-1' : 'UA-49258698-3';
      GOVUK.analytics = new GOVUK.Analytics({
        universalId: property,
        cookieDomain: cookieDomain
      });
    }
  };
})(window);
