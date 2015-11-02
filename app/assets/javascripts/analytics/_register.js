(function (root) {
  "use strict";

  root.GOVUK.GDM = root.GOVUK.GDM || {};
  root.GOVUK.GDM.analytics = {
    'register': function () {
      GOVUK.Analytics.load();
      var cookieDomain = (root.document.domain === 'www.digitalmarketplace.service.gov.uk') ? '.digitalmarketplace.service.gov.uk' : root.document.domain;
      var universalId = 'UA-49258698-1';
      GOVUK.analytics = new GOVUK.Analytics({
        universalId: universalId,
        cookieDomain: cookieDomain
      });
    }
  };
})(window);
