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
});
