import six

arelle_mods = [
    ["urllib_parse", "urlparse", "urllib.parse"],
    ["urllib_request", "urllib", "urllib.request"],
    ["urllib_error", "urllib2", "urllib.error"]
]

for mod in arelle_mods:
    six.add_move(six.MovedModule(*mod))
