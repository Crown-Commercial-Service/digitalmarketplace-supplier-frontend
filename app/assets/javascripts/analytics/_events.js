(function (root) {
  "use strict";

  GOVUK.GDM.analytics.events = {
    'registerLinkClick': function (e) {
      var $target = $(e.target),
          href = $target.prop('href'),
          category = 'internal-link',
          action = $target.text(),
          fileTypesRegExp = /\.(pdf|pda|odt|ods|odp|zip)$/,
          currentHost = new RegExp(root.location.hostname);

      /* 
         File type matching based on those in:
         https://github.com/alphagov/digitalmarketplace-utils/blob/8251d45f47593bd73c5e3b993e1734b5ee505b4b/dmutils/documents.py#L105
      */

      // if the node clicked wasn't the link but a child of it
      if ($target[0].nodeName.toLowerCase() !== 'a') {
        $target = $target.closest('a');
        href = $target.prop('href');
      }
      if (href.match(fileTypesRegExp) !== null) { // download link
        category = 'download';
      }
      else if ((href.match(/^(https|http){1}/) !== null) && (href.match(currentHost) === null)) {
        category = 'external-link';
      }
      GOVUK.analytics.trackEvent(category, action);
    },
    'init': function () {
      $('body').on('click', 'a', this.registerLinkClick);
    }
  };
})(window);
