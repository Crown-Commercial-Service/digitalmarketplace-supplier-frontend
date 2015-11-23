(function (root) {
  "use strict";

  root.GOVUK.GDM.analytics.init = function () {
    this.register();
    this.pageViews.init();
    this.virtualPageViews();
    this.events.init();
  };
})(window);
