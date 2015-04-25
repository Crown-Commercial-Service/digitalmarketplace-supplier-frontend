from app import login_manager, api_client


@login_manager.user_loader
def load_user(user_id):
    print "\n\n\n\n USER ID {}".format(user_id)
    return api_client.user_by_id(int(user_id))