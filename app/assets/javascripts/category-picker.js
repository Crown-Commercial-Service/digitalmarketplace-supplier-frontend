;(function(root) {

  "use strict";

  var GOVUK = root.GOVUK;

  function _unique(array) {
    return $.grep(array, function(el, index) {
        return index === $.inArray(el, array);
    });
  }

  // wrapper around the categories data
  var Categories = function (_categories) {
    var primaries = []

    this._containers = []
    this._categories = _categories
    this.save_last_state()
  }
  Categories.prototype.save_last_state = function () {
    this._lastState = $.extend(true, {}, this._categories)
  }
  Categories.prototype.tick_by_name = function (category_names) {

    this.save_last_state()
    $(this._categories).each(function () {
      var category = this
      if ($.inArray(category.value, category_names) !== -1) {
        category.checked = !category.checked
      }
    })
  }
  Categories.prototype.all = function () {
    return this._categories
  }
  Categories.prototype.get_primaries = function () {
    var parents = []
    $.each(this._categories, function () {
      parents.push(this.parent)
    })
    return _unique(parents)
  }
  Categories.prototype.get_children_for = function (value) {
    return $(this._categories).filter(function () {
      return this.parent === value
    })
  }
  Categories.prototype.get_parent_for = function (category) {
    var category_parent = category.parent

    return $(this.get_primaries()).filter(function () { return this.value === category_parent })[0]
  }
  Categories.prototype.get_filtered_names = function (filter) {
    return $(this._categories).filter(filter).map(function () { return this.value })
  }
  Categories.prototype.get_checked = function (dedupe) {
    var results = $(this._categories).filter(function () { return this.checked })
    var unique_results = []

    if(dedupe === undefined) {
        return results
    }

    // de-dupe results
    $(results).each(function () {
      var category_name = this.value
      if ($.inArray(category_name, unique_results) === -1) {
        unique_results.push(category_name)
      }
    })
    return unique_results
  }
  Categories.prototype.diff = function (oldState, newState) {
    var diff = []

    oldState.each(function (index) {
      var newCategory = newState[index]
      if (this.checked !== newCategory.checked) {
        diff.push(newCategory)
      }
    })
    return diff
  }
  Categories.prototype.get_changes = function () {
    return this.diff(this._lastState, this._categories)
  }

  var categoryPicker = function () {
    var categories_data = $('#checkbox-tree__inputs input[type=checkbox]').map(function () {
      var $input = $(this)
      var $label = $input.parent()

      return {
        'value': $.trim($label.text()),
        'id': $input.attr('id'),
        'parent': $input.parents('details').find('.categories-heading').text(),
        'checked': $input.is(':checked')
      }
    })
    var globalCategories = new Categories(categories_data)
    function appendCounter(id) {
       var $_counter = $('#' + id)

       if(!$_counter.length) {
         $('.checkbox-tree__counter')
           .find('div')
           .append($("<p>", {"id": id, "role": "status", "aria-live": "polite"}))

         $_counter = $('#' + id)
       }

       return $_counter
    }

    function setCounter () {
      var checked = globalCategories.get_checked(true).length
      var suffix = (checked === 1) ? 'category' : 'categories'
      $counter.html('<strong>' + checked + '</strong> ' + suffix + ' selected.')
    }

    var $counter = appendCounter('counter')

    function renderCategories () {
      var updatedCategories = globalCategories.get_changes()

      $(updatedCategories).each(function () {
        var $input = $('#' + this.id)
        var action = (this.checked) ? 'addClass' : 'removeClass'

        $input.attr('checked', this.checked)
        $input.parent('label')[action]('selected')
      })
      setCounter()
    }

    function setParentContextCounters () {
      var parents = globalCategories.get_primaries()
      $.each(parents, function() {
        setParentContextCounter(this)
      })
    }

    function setParentContextCounter (parentCategory) {
      var childCategories = globalCategories.get_children_for(parentCategory)
      var checkedCategories = globalCategories.get_checked()
      var checkedChildCategories = $.map(childCategories, function (category) {
        return $.inArray(category, checkedCategories) < 0 ? null : category.value
      })

      // write the message
      var parentContext = childCategories.length + ' categories'
      parentContext += (checkedChildCategories.length) ? ', ' + checkedChildCategories.length + ' selected' : ''

      // update the .categories-summary span
      $('.categories-heading:contains("' + parentCategory + '")').next().text(parentContext)
    }

    renderCategories()
    setCounter()
    setParentContextCounters()

    // make clicks on checkboxes update the categories state
    // TODO: looks like the event is triggered four times
    $('#checkbox-tree__inputs').on('click', 'input', function (event) {
      var target = event.target
      var targetNodeName = target.nodeName.toLowerCase()
      var categoryName

      function getLabelTextForInput (input) {
        var text = $(input).siblings().first().text()
        return $.trim(text)
      }

      function updateView (categoryName) {
        globalCategories.tick_by_name([categoryName])
        renderCategories()
        setParentContextCounters()
        setCounter()

      }

      if (targetNodeName === 'input') {
        categoryName = getLabelTextForInput(target)
        updateView(categoryName)
      }
    })
  }

  root.GOVUK.GDM.categoryPicker = categoryPicker
  categoryPicker()

})(window);
