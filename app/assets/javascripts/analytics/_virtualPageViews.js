(function (root) {
  "use strict";

  root.GOVUK.GDM.analytics.virtualPageViews = {
    'pathName': root.location.pathname,
    'declarationPages': {
      'firstPage': '/suppliers/frameworks/g-cloud-7/declaration/g_cloud_7_essentials',
      'lastPage': '/suppliers/frameworks/g-cloud-7/declaration/grounds_for_discretionary_exclusion'
    },
    'declarationVirtualPageViewsFor': function (element) {
      switch (element) {
        case 'firstQuestion':
          return this.declarationPages.firstPage + '/interactions/accept-terms-of-participation';
        case 'makeDeclarationButton':
          return this.declarationPages.lastPage + '/interactions/make-declaration';
        default:
          return '';
      }
    },
    'registerFirstQuestionInteraction': function (e) {
      var $target;

      $target = $(e.target);

      // if the click target is a child node of the label, get the label instead
      if ($target.prop('nodeName').toLowerCase() !== 'label') {
        $target = $target.closest('label');
      }

      GOVUK.analytics.trackPageview(this.declarationVirtualPageViewsFor('firstQuestion') + '/yes');
      GOVUK.analytics.trackPageview(this.declarationVirtualPageViewsFor('firstQuestion') + '/no');
    },
    'registerDeclarationMade': function (e) {
      if (this.pathName === this.declarationPages.lastPage) {
        GOVUK.analytics.trackPageview(this.declarationVirtualPageViewsFor('makeDeclarationButton'));
      }
    },
    'init': function () {
      var self = this;

      if (this.pathName === this.declarationPages.firstPage) {
        $('body').on('click', 'form.supplier-declaration fieldset:eq(0) label.selection-button', function (e) {
          self.registerFirstQuestionInteraction(e);
        });
      }
      if (this.pathName === this.declarationPages.lastPage) {
        $('body').on('click', 'form.supplier-declaration .button-save', function (e) {
          self.registerDeclarationMade(e);
        });
      }
    }
  };
})(window);
