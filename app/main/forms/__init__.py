from flask.ext.wtf import Form
from wtforms import FieldList


class StripWhitespaceForm(Form):
    class Meta:
        def bind_field(self, form, unbound_field, options):
            filters = unbound_field.kwargs.get('filters', [])
            if unbound_field.field_class is not FieldList:
                filters.append(strip_whitespace)
            return unbound_field.bind(form=form, filters=filters, **options)


def strip_whitespace(value):
    if value is not None and hasattr(value, 'strip'):
        return value.strip()
    return value
