from wtforms import StringField


class StripWhitespaceStringField(StringField):
    def __init__(self, label=None, **kwargs):

        if 'filters' not in kwargs:
            kwargs['filters'] = []
        kwargs['filters'] += [strip_whitespace]

        super(StringField, self).__init__(label, **kwargs)


def strip_whitespace(value):
    if value is not None and hasattr(value, 'strip'):
        return value.strip()
    return value
