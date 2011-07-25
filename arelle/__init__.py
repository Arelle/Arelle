import six, string, os

arelle_mods = [
    ["urllib_parse", "urlparse", "urllib.parse"],
    ["urllib_request", "urllib", "urllib.request"],
    ["urllib_error", "urllib2", "urllib.error"]
]

for mod in arelle_mods:
    six.add_move(six.MovedModule(*mod))

import os, sys, linecache, inspect, os.path, threading, trace

call_prefix = ""
call_list = list()

def traceit(frame, event, arg):

    if (frame.f_code.co_filename.find("arelle/") == -1):
        return traceit

    global call_list
    call_data = [frame.f_code.co_name, 
                 frame.f_code.co_filename,
                 frame.f_lineno]
    if event == 'call':
        call_data.insert(0, 'enter')
        call_list.append(call_data)
    if event == 'return':
        call_data.insert(0, 'exit')
        call_list.append(call_data)
        
    return traceit
