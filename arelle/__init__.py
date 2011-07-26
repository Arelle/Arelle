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
__tracer = trace.Trace()

def traceit(frame, event, arg):
    
    if (frame.f_code.co_filename.find("arelle/") == -1):
        return traceit

    global call_list, __tracer
    fn, mn, funcname = __tracer.file_module_function_of(frame)
    call_data = [funcname, mn, fn, frame.f_lineno]
    if event == 'call':
        call_data.insert(0, 'enter')
        call_list.append(call_data)
    if event == 'return':
        call_data.insert(0, 'exit')
        call_list.append(call_data)
        
    return traceit
