describe("GOVUK.Analytics", function () {
  var analytics;

  beforeEach(function () {
    window.ga = function() {};
    spyOn(window, 'ga');
  });

  describe('when initialised', function () {

    it('should initialise pageviews, events and virtual pageviews', function () {
      spyOn(window.GOVUK.GDM.analytics, 'register');
      spyOn(window.GOVUK.GDM.analytics.pageViews, 'init');
      spyOn(window.GOVUK.GDM.analytics, 'virtualPageViews');
      spyOn(window.GOVUK.GDM.analytics.events, 'init');

      window.GOVUK.GDM.analytics.init();

      expect(window.GOVUK.GDM.analytics.register).toHaveBeenCalled();
      expect(window.GOVUK.GDM.analytics.pageViews.init).toHaveBeenCalled();
      expect(window.GOVUK.GDM.analytics.virtualPageViews).toHaveBeenCalled();
      expect(window.GOVUK.GDM.analytics.events.init).toHaveBeenCalled();
    });
  });

  describe('when registered', function() {
    var universalSetupArguments;

    beforeEach(function() {
      GOVUK.GDM.analytics.init();
      universalSetupArguments = window.ga.calls.allArgs();
    });

    it('configures a universal tracker', function() {
      var trackerId = 'UA-49258698-1';
      expect(universalSetupArguments[0]).toEqual(['create', trackerId, {
        'cookieDomain': document.domain
      }]);
    });
  });

  describe('pageViews', function () {
    beforeEach(function () {
      window.ga.calls.reset();
    });

    it('should register a pageview when initialised', function () {
      spyOn(window.GOVUK.GDM.analytics.pageViews, 'init').and.callThrough();

      window.GOVUK.GDM.analytics.pageViews.init();

      expect(window.ga.calls.argsFor(0)).toEqual(['send', 'pageview']);
    });
  });

  describe('link tracking', function () {
    var mockLink;

    beforeEach(function () {
      mockLink = document.createElement('a');
      window.ga.calls.reset();
    });

    it('sends the right event when an internal link is clicked', function() {
      mockLink.appendChild(document.createTextNode('Suppliers guide'));
      mockLink.href = window.location.hostname + '/suppliers/frameworks/g-cloud-7/download-supplier-pack';
      GOVUK.GDM.analytics.events.registerLinkClick({ 'target': mockLink });
      expect(window.ga.calls.first().args).toEqual(['send', {
        'hitType': 'event',
        'eventCategory': 'internal-link',
        'eventAction': 'Suppliers guide'
      }]);
    });
    it('sends the right event when an external link is clicked', function() {
      mockLink.appendChild(document.createTextNode('Open Government Licence v3.0'));
      mockLink.href = 'https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/';
      GOVUK.GDM.analytics.events.registerLinkClick({ 'target': mockLink });
      expect(window.ga.calls.first().args).toEqual(['send', {
        'hitType': 'event',
        'eventCategory': 'external-link',
        'eventAction': 'Open Government Licence v3.0'
      }]);
    });
    it('sends the right event when a download link is clicked', function() {
      mockLink.appendChild(document.createTextNode('Download guidance and legal documentation (.zip)'));
      mockLink.href = window.location.hostname + '/suppliers/frameworks/g-cloud-7/g-cloud-7-supplier-pack.zip';
      GOVUK.GDM.analytics.events.registerLinkClick({ 'target': mockLink });
      expect(window.ga.calls.first().args).toEqual(['send', {
        'hitType': 'event',
        'eventCategory': 'download',
        'eventAction': 'Download guidance and legal documentation (.zip)'
      }]);
    });
  });

  describe('button tracking', function () {
    var mockButton;

    beforeEach(function () {
      mockButton = document.createElement('input');
      mockButton.setAttribute('type', 'submit');
      window.ga.calls.reset();
    });

    it('sends the right event when a submit button is clicked', function() {
      mockButton.setAttribute('value', 'Save and continue');
      document.title = 'Features and benefits';
      GOVUK.GDM.analytics.events.registerSubmitButtonClick.call(mockButton);
      expect(window.ga.calls.first().args).toEqual(['send', {
          'hitType': 'event',
          'eventCategory': 'button',
          'eventAction': 'Save and continue',
          'eventLabel': 'Features and benefits'
        }
      ]);
    });

    it('knows if the user is on a service page', function () {

      expect(
        GOVUK.GDM.analytics.isQuestionPage("http://example.com/suppliers/submission/services/7478/edit/service_name")
      ).toEqual(true);

      expect(
        GOVUK.GDM.analytics.isQuestionPage("http://example.com/suppliers/submission/services/7478")
      ).toEqual(false);

      expect(
        GOVUK.GDM.analytics.isQuestionPage("http://example.com/suppliers/frameworks/g-cloud-7/services")
      ).toEqual(false);

      expect(
        GOVUK.GDM.analytics.isQuestionPage("file:///Users/Jo/gds/suppliers/spec.html")
      ).toEqual(false);

    });

  });

  describe("Virtual Page Views", function () {
    var $analyticsString;
    beforeEach(function () {
       window.ga.calls.reset();
    });

    afterEach(function () {
      $analyticsString.remove();

    });
    describe("When called", function () {

      it("Should not call google analytics without a url", function () {
        $analyticsString = $("<div data-analytics='trackPageView'/>");
        $(document.body).append($analyticsString);
        window.GOVUK.GDM.analytics.virtualPageViews();
        expect(window.ga.calls.any()).toEqual(false);
      });

      it("Should call google analytics if url exists", function () {
        $analyticsString = $("<div data-analytics='trackPageView' data-url='http://example.com'/>");
        $(document.body).append($analyticsString);
        window.GOVUK.GDM.analytics.virtualPageViews();
        expect(window.ga.calls.first().args).toEqual([ 'send', 'pageview', { page: 'http://example.com' } ]);
        expect(window.ga.calls.count()).toEqual(1);
      });
    });

  });
});
