(function(GOVUK, GDM) {

  GOVUK.GDM = GDM;

  GDM.stickAtTopWhenScrolling = function() {

    if (!GOVUK.stickAtTopWhenScrolling) return;

    GOVUK.stickAtTopWhenScrolling.init();

    $('#checkbox-tree__inputs').on('click', 'details', function () {
      // immediately after the click, the details pane hasn't expanded yet
      setTimeout(function () {
        GOVUK.stopScrollingAtFooter.updateFooterTop()
      }, 100)
    })
  }

}).apply(this, [GOVUK||{}, GOVUK.GDM||{}]);
