(function (GOVUK) {
  "use strict";

  var sendVirtualPageView = function() {
    var $element = $(this);
    var url = $element.data('url');
    if (GOVUK.analytics  && url){
      var urlList = url.split("?")
      urlList[0] = urlList[0] + "/vpv"
      url = urlList.join("?")
      GOVUK.analytics.trackPageview(url);
    }
  };

  GOVUK.GDM.analytics.virtualPageViews = function() {
    var $messageSent;

    $('[data-analytics=trackPageView]').each(sendVirtualPageView);
    if (GOVUK.GDM.analytics.location.pathname().match(/^\/suppliers\/opportunities\/\d+\/ask-a-question/) !== null) {
      $messageSent = $('#content form').attr('data-message-sent') === 'true';

      if ($messageSent) {
        GOVUK.analytics.trackPageview(GOVUK.GDM.analytics.location.pathname() + '?submitted=true');
      }
    }
  };

})(window.GOVUK);
