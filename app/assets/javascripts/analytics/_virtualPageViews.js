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
    $('[data-analytics=trackPageView]').each(sendVirtualPageView);
  };

})(window.GOVUK);
