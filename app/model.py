
class User():
    def __init__(self, user_id, email_address, supplier_id, supplier_name):
        self.id = user_id
        self.email_address = email_address
        self.supplier_id = supplier_id
        self.supplier_name = supplier_name

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
            'emailAddress': self.email_address,
            'supplierId': self.supplier_id,
            'supplierName': self.supplier_name,
        }
