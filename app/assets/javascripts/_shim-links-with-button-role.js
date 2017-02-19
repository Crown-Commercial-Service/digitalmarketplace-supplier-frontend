(function(GOVUK, GDM) {

  GDM.shimLinksWithButtonRole = function() {

    if (!GOVUK.shimLinksWithButtonRole) return;

    GOVUK.shimLinksWithButtonRole.init({
      selector: '[class^=link-button]'
    });

  };

  GOVUK.GDM = GDM;

}).apply(this, [GOVUK||{}, GOVUK.GDM||{}]);
