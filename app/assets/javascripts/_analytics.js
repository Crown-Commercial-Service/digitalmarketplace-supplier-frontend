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
  var declarationPages = {
    'firstPage': '/suppliers/frameworks/g-cloud-7/declaration/g_cloud_7_essentials',
    'lastPage': '/suppliers/frameworks/g-cloud-7/declaration/grounds_for_discretionary_exclusion'
  };
  var declarationVirtualPageViews = {
    'firstQuestion': declarationPages.firstPage + '/interactions/accept-terms-of-participation',
    'makeDeclarationButton': declarationPages.lastPage + '/interactions/make-declaration'
  };
  var externalLinkSelector = 'a[href^="https"]:not(a[href*="' + currentHost + '"])';
  var pathName = window.location.pathname

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
    if (pathName === declarationPages.lastPage) {
      GOVUK.analytics.trackPageview(declarationVirtualPageViews.makeDeclarationButton);
    }
  }

  var registerLinkClick = function (e) {
    var $target = $(e.target),
        href = $target.prop('href'),
        category = 'internal-link',
        action = $target.text(),
        fileTypesRegExp = /\.(pdf|pda|odt|ods|odp)$/;

    /* 
       File type matching based on those in:
       https://github.com/alphagov/digitalmarketplace-utils/blob/8251d45f47593bd73c5e3b993e1734b5ee505b4b/dmutils/documents.py#L105
    */
    if (href.match(fileTypesRegExp) !== null) { // download link
      category = 'download';
    }
    else if (href.match(/^(https|http){1}/) !== null) { // external link
      category = 'external-link';
    }
    GOVUK.analytics.trackEvent(category, action);
  };

  if (pathName === declarationPages.firstPage) {
    $('body').on('click', 'form.supplier-declaration fieldset:eq(0) label.selection-button', registerFirstQuestionInteraction);
  }
  if (pathName === declarationPages.lastPage) {
    $('form.supplier-declaration .button-save').on('click', registerDeclarationMade);
  }

  $('body').on('click', 'a', registerLinkClick);
})();
