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

  // Tracking for declaration pages
  declarationPages = {
    'firstPage': '/suppliers/frameworks/g-cloud-7/declaration/g_cloud_7_essentials',
    'lastPage': '/suppliers/frameworks/g-cloud-7/declaration/grounds_for_discretionary_exclusion'
  };
  declarationVirtualPageViews = {
    'firstQuestion': declarationPages.firstPage + '/interactions/accept-terms-of-participation',
    'makeDeclarationButton': declarationPages.lastPage + '/interactions/make-declaration'
  };

  var registerFirstQuestionInteraction = function (e) {
    var $target;

    $target = $(e.target);

    // if the click target is a child node of the label, get the label instead
    if ($target.prop('nodeName').toLowerCase() !== 'label') {
      $target = $target.closest('label');
    }

    GOVUK.analytics.trackPageview(declarationVirtualPageViews.firstQuestion + '/yes');
    GOVUK.analytics.trackPageview(declarationVirtualPageViews.firstQuestion + '/no');
  };

  var registerDeclarationMade = function (e) {
    if (window.location.pathname === declarationPages.lastPage) {
      GOVUK.analytics.trackPageview(declarationVirtualPageViews.makeDeclarationButton);
    }
  }

  if (window.location.pathname === declarationPages.firstPage) {
    $('body').on('click', 'form.supplier-declaration fieldset:eq(0) label.selection-button', registerFirstQuestionInteraction);
  }
  if (window.location.pathname === declarationPages.lastPage) {
    $('form.supplier-declaration .button-save').on('click', registerDeclarationMade);
  }
})();
