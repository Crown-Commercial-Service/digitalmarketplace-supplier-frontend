(function(GOVUK, GDM) {

  GDM.selectionButtons = function() {

    if (!GOVUK.SelectionButtons) return;

    new GOVUK.SelectionButtons('.selection-button input', {
      'focusedClass' : 'selection-button-focused',
      'selectedClass' : 'selection-button-selected'
    });

  };

  GOVUK.GDM = GDM;

}).apply(this, [GOVUK||{}, GOVUK.GDM||{}]);
