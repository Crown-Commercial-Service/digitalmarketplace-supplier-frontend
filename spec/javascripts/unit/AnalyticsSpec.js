describe("GOVUK.Analytics", function () {
  var analytics;

  beforeEach(function () {
    window.ga = function() {};
    spyOn(window, 'ga');
  });

  describe('when registered', function() {
    var universalSetupArguments;

    beforeEach(function() {
      GOVUK.GDM.analytics.init();
      universalSetupArguments = window.ga.calls.allArgs();
    });

    it('configures a universal tracker', function() {
      var trackerId = (document.domain === 'www.digitalmarketplace.service.gov.uk') ? 'UA-49258698-1' : 'UA-49258698-3';
      expect(universalSetupArguments[0]).toEqual(['create', trackerId, {
        'cookieDomain': document.domain
      }]);
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
      mockLink.href = window.location.hostname + '/suppliers/frameworks/g-cloud-7/download-supplier-pack'
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

  describe('virtual page views', function () {
    beforeEach(function () {
      
      window.ga.calls.reset();
    });

    it('tracks clicks on the first question of the supplier declaration', function () {
      var radio = document.createElement('input'),
          mockControl = document.createElement('label');

      radio.type = 'radio';
      mockControl.appendChild(document.createTextNode('Yes'));
      mockControl.appendChild(radio);

      GOVUK.GDM.analytics.virtualPageViews.declaration.registerFirstQuestionInteraction({
        'target': mockControl
      });
      expect(window.ga.calls.first().args).toEqual(['send', 'pageview', {
        'page': '/suppliers/frameworks/g-cloud-7/declaration/g_cloud_7_essentials/interactions/accept-terms-of-participation/yes'
      }]);
    });
    it('tracks completed supplier declarations', function () {
      GOVUK.GDM.analytics.virtualPageViews.declaration.registerDeclarationMade();
      expect(window.ga.calls.first().args).toEqual(['send', 'pageview', {
        'page': '/suppliers/frameworks/g-cloud-7/interactions/declaration-made'
      }]);
    });
    it('tracks the lot selection of a new service', function () {
      var radio = document.createElement('input'),
          mockControl = document.createElement('label');

      radio.type = 'radio';
      radio.value = 'iaas'
      mockControl.appendChild(radio);

      GOVUK.GDM.analytics.virtualPageViews.createANewService.registerLotSelection({
        'target': mockControl
      });
      expect(window.ga.calls.first().args).toEqual(['send', 'pageview', {
        'page': '/suppliers/submission/g-cloud-7/create/interactions/lot/iaas'
      }]);
    });
    it('tracks the completed services', function () {
      GOVUK.GDM.analytics.virtualPageViews.createANewService.registerServiceCreated(1, 'iaas');
      expect(window.ga.calls.first().args).toEqual(['send', 'pageview', {
        'page': '/suppliers/frameworks/g-cloud-7/services/interactions/service-1-created-lot-iaas'
      }]);
    });
  });
});
