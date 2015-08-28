describe("GOVUK.Analytics", function () {
  var analytics;

  beforeEach(function () {
    window.ga = function() {};
    spyOn(window, 'ga');
  });

  describe('when created', function() {
    var universalSetupArguments;

    beforeEach(function() {
      analytics = new window.GOVUK.Analytics({
        universalId: 'universal-id',
        cookieDomain: 'www.digitalmarketplace.service.gov.uk'
      });
      universalSetupArguments = window.ga.calls.allArgs();
    });

    it('configures a universal tracker', function() {
      expect(universalSetupArguments[0]).toEqual(['create', 'universal-id', {
        'cookieDomain': 'www.digitalmarketplace.service.gov.uk'
      }]);
    });
  })
});
