(function (root, GOVUK) {
  "use strict";

  var pathName = root.location.pathname;

  var virtualPageViews = {
    'viewsTracked': [],
    'getViewFor': function (section, page, element) {
      return this[section].pages[page] + '/interactions/' + element;
    },
    'trackPageview': function (view) {
      if (this.viewsTracked.indexOf(view) === -1) {
        GOVUK.analytics.trackPageview(view);
        this.viewsTracked.push(view);
      }
    },
    'declaration': {
      'pages': {
        'firstPage': '/suppliers/frameworks/g-cloud-7/declaration/g_cloud_7_essentials',
        'lastPage': '/suppliers/frameworks/g-cloud-7/declaration/grounds_for_discretionary_exclusion'
      },
      'registerFirstQuestionInteraction': function (e) {
        var $target,
            option;

        $target = $(e.target);

        // if the click target is a child node of the label, get the label instead
        if ($target.prop('nodeName').toLowerCase() !== 'label') {
          $target = $target.closest('label');
        }

        option = $target.text().trim().toLowerCase();
        virtualPageViews.trackPageview(virtualPageViews.getViewFor('declaration', 'firstPage', 'accept-terms-of-participation') + '/' + option);
      },
      'registerDeclarationMade': function (e) {
        if (pathName === this.pages.lastPage) {
          virtualPageViews.trackPageview(virtualPageViews.getPageviewsFor('declaration', 'lastPage', 'make-declaration'));
        }
      }
    },
    'createANewService': {
      'pages': {
        'firstPage': '/suppliers/submission/g-cloud-7/create',
        'lastPage': ''
      },
      'registerLotSelection': function (e) {
        var $target = $(e.target),
            option;

        // if the click target is a child node of the label, get the label instead
        if ($target.prop('nodeName').toLowerCase() !== 'label') {
          $target = $target.closest('label');
        }

        option = $target.children('input').val().toLowerCase();
        virtualPageViews.trackPageview(virtualPageViews.getViewFor('createANewService', 'firstPage', 'lot') + '/'     + option);
      }
    },
    'init': function () {
      if (pathName === this.declaration.pages.firstPage) {
        $('body').on('click', 'form.supplier-declaration fieldset:eq(0) label.selection-button', this.declaration.registerFirstQuestionInteraction);
      }
      if (pathName === this.declaration.pages.lastPage) {
        $('body').on('click', 'form.supplier-declaration .button-save', this.declaration.registerDeclarationMade);
      }
      if (pathName === this.createANewService.pages.firstPage) {
        $('body').on('click', 'form fieldset label.selection-button', this.createANewService.registerLotSelection);
      }
    }
  };
  GOVUK.GDM.analytics.virtualPageViews = virtualPageViews;
})(window, window.GOVUK);
