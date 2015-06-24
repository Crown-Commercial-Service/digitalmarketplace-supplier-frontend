from flask.ext.wtf import Form
from wtforms import validators, StringField
from wtforms import BooleanField as _BooleanField


class BooleanField(_BooleanField):
    """Tri-state boolean field

    This field supports having either 'yes', 'no' or 'not set'.
    """

    def process_data(self, value):
        if value is not None:
            value = bool(value)
        self.data = value

    def process_formdata(self, valuelist):
        if not valuelist:
            self.data = None
        elif valuelist[0] in self.false_values:
            self.data = False
        else:
            self.data = True


class G7SelectionQuestions(Form):
    registration_number = StringField(
        'Registration number',
        [validators.optional()])
    bankrupt = BooleanField('Are you bankrupt?',
                            false_values=('val-2',))
