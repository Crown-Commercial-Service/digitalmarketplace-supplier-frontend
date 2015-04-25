
class User():
    def __init__(self, user_id, email_address):
        self.id = user_id
        self.email_address = email_address
        self.supplier_id = 585274
        self.supplier_name = "Company 123"

    @staticmethod
    def is_authenticated():
        return True

    @staticmethod
    def is_active():
        return True

    @staticmethod
    def is_anonymous():
        return False

    def get_id(self):
        try:
            return unicode(self.id)  # python 2
        except NameError:
            return str(self.id)  # python 3

    def serialize(self):
        return {
            'id': self.id,
            'email_address': self.email_address,
            'supplier_id': self.supplier_id,
            'supplier_name': self.supplier_name,
        }
