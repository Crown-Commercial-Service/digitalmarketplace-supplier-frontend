(function (GOVUK) {
  GOVUK.GDM.analytics.pageViews = {
    'init': function () {
      this.setCustomDimensions()
      GOVUK.analytics.trackPageview();
    },

    'setCustomDimensions': function() {
      var eligibility;
      
      if (/^\/suppliers\/opportunities\/(\d+)\/responses\/create$/.test(GOVUK.GDM.analytics.location.pathname())) {
        eligibility = $('[data-reason]').first().data('reason');

        // If we do not find a reason for ineligibility then we will assume that they are able to apply
        if (!eligibility) {
          eligibility = 'supplier-able-to-apply';
        }
        
        GOVUK.analytics.setDimension(25, eligibility);
      }
    }
  };
})(window.GOVUK);
