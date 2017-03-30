(function(GOVUK, GDM) {

  GDM.selectionButtons = function() {

    if (!GOVUK.SelectionButtons) return;

    new GOVUK.SelectionButtons('.selection-button input');

    new GOVUK.ShowHideContent().init();

  };

  GOVUK.GDM = GDM;

}).apply(this, [GOVUK||{}, GOVUK.GDM||{}]);
