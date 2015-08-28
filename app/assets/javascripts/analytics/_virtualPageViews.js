(function (root, GOVUK) {
  "use strict";

  var pathName = root.location.pathname;
  var queryParams = (function () {
    var search = root.location.search,
        queryParams = {};

    // taken from https://developer.mozilla.org/en-US/docs/Web/API/URLUtils/search
    if (search.length > 1) {
      for (var aItKey, nKeyId = 0, aCouples = search.substr(1).split("&"); nKeyId < aCouples.length; nKeyId++) {
        aItKey = aCouples[nKeyId].split("=");
        queryParams[decodeURIComponent(aItKey[0])] = aItKey.length > 1 ? decodeURIComponent(aItKey[1]) : "";
      }
    }
    return queryParams;
  })();

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
        'dashboard': '/suppliers/frameworks/g-cloud-7'
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
      'registerDeclarationMade': function () {
        virtualPageViews.trackPageview(virtualPageViews.getViewFor('declaration', 'dashboard', 'declaration-made'));
      }
    },
    'createANewService': {
      'pages': {
        'firstPage': '/suppliers/submission/g-cloud-7/create',
        'services': '/suppliers/frameworks/g-cloud-7/services'
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
      },
      'registerServiceCreated': function () {
        var serviceId = queryParams['service_completed'],
            lot = queryParams['lot'];

        virtualPageViews.trackPageview(virtualPageViews.getViewFor('createANewService', 'services', 'service-' + serviceId + '-created-lot-' + lot));
      }
    },
    'init': function () {
      if (pathName === this.declaration.pages.firstPage) {
        $('body').on('click', 'form.supplier-declaration fieldset:eq(0) label.selection-button', this.declaration.registerFirstQuestionInteraction);
      }
      if ((pathName === this.declaration.pages.dashboard) && (typeof queryParams['declaration_completed'] !== 'undefined')) {
        this.declaration.registerDeclarationMade();
      }
      if (pathName === this.createANewService.pages.firstPage) {
        $('body').on('click', 'form fieldset label.selection-button', this.createANewService.registerLotSelection);
      }
      if ((pathName === this.createANewService.pages.services) && (typeof queryParams['service_completed'] !== 'undefined')) {
        this.createANewService.registerServiceCreated();
      }
    }
  };
  GOVUK.GDM.analytics.virtualPageViews = virtualPageViews;
})(window, window.GOVUK);
