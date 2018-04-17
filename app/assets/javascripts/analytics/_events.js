(function (root, GOVUK) {
  "use strict";

  var CONFIG = {
    '/suppliers/frameworks/g-cloud-7/declaration/g_cloud_7_essentials': [
      ['Percent', 80]
    ]
  };

  function ScrollTracker(sitewideConfig) {
    this.config = this.getConfigForCurrentPath(sitewideConfig);
    this.SCROLL_TIMEOUT_DELAY = 500;

    if ( !this.config ) {
      this.enabled = false;
      return;
    }
    this.enabled = true;

    this.trackedNodes = this.buildNodes(this.config);

    $(root).scroll($.proxy(this.onScroll, this));
    this.trackVisibleNodes();
  }

  ScrollTracker.prototype.getConfigForCurrentPath = function getConfigForCurrentPath(sitewideConfig) {
    for (var path in sitewideConfig) {
      if ( GOVUK.GDM.analytics.location.pathname() == path ) return sitewideConfig[path];
    }
  };

  ScrollTracker.prototype.buildNodes = function buildNodes(config) {
    var nodes = [];
    var NodeConstructor, nodeData;

    for (var i=0; i<config.length; i++) {
      NodeConstructor = ScrollTracker[config[i][0] + "Node"];
      nodeData = config[i][1];
      nodes.push(new NodeConstructor(nodeData));
    }

    return nodes;
  };

  ScrollTracker.prototype.onScroll = function onScroll() {
    clearTimeout(this.scrollTimeout);
    this.scrollTimeout = setTimeout($.proxy(this.trackVisibleNodes, this), this.SCROLL_TIMEOUT_DELAY);
  };

  ScrollTracker.prototype.trackVisibleNodes = function trackVisibleNodes() {
    for ( var i=0; i<this.trackedNodes.length; i++ ) {
      if ( this.trackedNodes[i].isVisible() && !this.trackedNodes[i].alreadySeen ) {
        this.trackedNodes[i].alreadySeen = true;

        var action = this.trackedNodes[i].eventData.action,
            label = this.trackedNodes[i].eventData.label;

        GOVUK.analytics.trackEvent('ScrollOnSupplierDeclaration', action, {label: label, nonInteraction: true});
      }
    }
  };

  ScrollTracker.PercentNode = function PercentNode(percentage) {
    this.percentage = percentage;
    this.eventData = {action: "Percent", label: String(percentage)};
  };

  ScrollTracker.PercentNode.prototype.isVisible = function isVisible() {
    return this.currentScrollPercent() >= this.percentage;
  };

  ScrollTracker.PercentNode.prototype.currentScrollPercent = function currentScrollPercent() {
    var $document = $(document);
    var $root = $(root);
    return( ($root.scrollTop() / ($document.height() - $root.height())) * 100.0 );
  };

  ScrollTracker.HeadingNode = function HeadingNode(headingText) {
    this.$element = getHeadingElement(headingText);
    this.eventData = {action: "Heading", label: headingText};

    function getHeadingElement(headingText) {
      var $headings = $('h1, h2, h3, h4, h5, h6');
      for ( var i=0; i<$headings.length; i++ ) {
        if ( $.trim($headings.eq(i).text()).replace(/\s/g, ' ') == headingText ) return $headings.eq(i);
      }
    }
  };

  ScrollTracker.HeadingNode.prototype.isVisible = function isVisible() {
    if ( !this.$element ) return false;
    return this.elementIsVisible(this.$element);
  };

  ScrollTracker.HeadingNode.prototype.elementIsVisible = function elementIsVisible($element) {
    var $root = $(root);
    var positionTop = $element.offset().top;
    return ( positionTop > $root.scrollTop() && positionTop < ($root.scrollTop() + $root.height()) );
  };

  GOVUK.GDM.analytics.isQuestionPage = function(url) {
    return !!url.match(/suppliers\/submission\/services\/([\d]+)\/edit\/([^/]+)$/);
  };

  GOVUK.GDM.analytics.events = {
    'registerLinkClick': function (e) {
      var $target = $(e.target),
          href = $target.prop('href'),
          category = 'internal-link',
          action = $target.text(),
          fileTypesRegExp = /\.(pdf|pda|odt|ods|odp|zip)$/,
          currentHost = GOVUK.GDM.analytics.location.hostname(),
          currentHostRegExp = (currentHost !== '') ? new RegExp(currentHost) : /^$/g; // this ccode can run in an environment without a host, ie. a html file

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
      else if ((href.match(/^(https|http){1}/) !== null) && (href.match(currentHostRegExp) === null)) {
        category = 'external-link';
      }
      GOVUK.analytics.trackEvent(category, action);
    },
    'registerSubmitButtonClick': function () {

      var currentURL = GOVUK.GDM.analytics.location.href();

      if (
        currentURL.match(/^(https|http){1}/) &&
        !GOVUK.GDM.analytics.isQuestionPage(currentURL)
      ) return;

      GOVUK.analytics.trackEvent(
        'button', this.value, {'label': document.title}
      );
    },
    'ScrollTracker': ScrollTracker,
    trackEvent: function (e) {
      var $target = $(e.target);
      var category = $target.attr('data-analytics-category');
      var action = $target.attr('data-analytics-action');
      var label = $target.attr('data-analytics-label');
      var href = $target.attr('href');
      var text = $target.text();

      if ( !label && text ) label = text;
      else if ( !label && !text && href ) label = href;

      GOVUK.GDM.analytics.events.sendEvent(category, action, label);

    },
    sendEvent: function (category, action, label) {
      GOVUK.analytics.trackEvent(category, action, {
        'label': label,
        'transport': 'beacon'
      });
    },
    'init': function () {

      $('body')
        .on('click', 'a', this.registerLinkClick)
        .on('click', 'input[type=submit]', this.registerSubmitButtonClick)
        .on('click', '[data-analytics=trackEvent]', this.trackEvent);
      var scrollTracker = new this.ScrollTracker(CONFIG);

    }
  };
})(window, window.GOVUK);
