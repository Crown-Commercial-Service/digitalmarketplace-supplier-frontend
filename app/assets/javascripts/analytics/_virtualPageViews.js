(function (GOVUK) {
  "use strict";

  var sendVirtualPageView = function() {
    var $element = $(this);
    var url = $element.data('url');
    if (GOVUK.analytics  && url){
      GOVUK.analytics.trackPageview(url);
    }
  };

  GOVUK.GDM.analytics.virtualPageViews = function() {
    var $flashMessage;

    $('[data-analytics=trackPageView]').each(sendVirtualPageView);
    if (GOVUK.GDM.analytics.location.pathname().match(/^\/suppliers\/opportunities\/\d+\/ask-a-question/) !== null) {
      $flashMessage = $('.banner-success-without-action .banner-message');

      if ($flashMessage.text().replace(/^\s+|\s+$/g, '').match(/^Your question has been sent/) !== null) {
        GOVUK.analytics.trackPageview(GOVUK.GDM.analytics.location.href() + '?submitted=true');
      }
    }
  };

})(window.GOVUK);
