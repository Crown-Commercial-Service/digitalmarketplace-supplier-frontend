from application import application


def next_url_is_valid(url):
    for rule in application.url_map.iter_rules():
        if "GET" in rule.methods:
            rule_string = "{}".format(rule)
            if rule_string.find('<') >= 0:
                rule_string = rule_string[:rule_string.find('<')]
            if url.startswith(rule_string):
                return True
    return False
