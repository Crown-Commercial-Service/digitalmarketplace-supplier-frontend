(function (root) {
  "use strict";

  root.GOVUK.GDM.analytics.init = function () {
    this.register();
    this.virtualPageViews.init();
    this.events.init();
  };
  GOVUK.GDM.analytics.init();
})(window);
