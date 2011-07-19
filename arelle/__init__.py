import six

arelle_mods = [
    ["urllib_parse", "urlparse", "urllib.parse"],
    ["urllib_request", "urllib", "urllib.request"],
    ["urllib_error", "urllib2", "urllib.error"]
]

for mod in arelle_mods:
    six.add_move(six.MovedModule(*mod))

import os, sys, linecache, inspect, os.path

def traceit(frame, event, arg):
    depth = len(inspect.stack())
    lineno = frame.f_lineno
    if '__file__' in frame.f_globals:
        filename = frame.f_globals['__file__']
        if (filename.endswith('.pyc') or
            filename.endswith('.pyo')):
            filename = filename[:-1]
        name = frame.f_globals['__name__']
        line = linecache.getline(filename, lineno)
    else:
        name = '[unknown]'
        try:
            src = inspect.getsourcelines(frame)
            line = src[lineno]
        except IOError:
            line = 'Unknown code named [%s].  VM instruction #%d' % \
                   (frame.f_code.co_name, frame.f_lasti)
            
    if event == 'call':
        fi = inspect.getframeinfo(frame)
        print("%s -> %s [%s:%s]" % (" "*depth, name, os.path.basename(fi[0]), lineno))
    elif event == 'line':
        # We don't want line level details
        pass
    elif event == 'return':
        fi = inspect.getframeinfo(frame)
        print("%s <- %s [%s:%s]" % (" "*depth, name, os.path.basename(fi[0]), lineno))
    elif event == 'exception':
        # We don't want exception details, yet
        pass
    elif event == 'c_call':
        print("%s -> %s [%s:%s]" % (" "*depth, name, os.path.basename(fi[0]), lineno))
    elif event == 'c_return':
        print("%s <- %s [%s:%s]" % (" "*depth, name, os.path.basename(fi[0]), lineno))
    elif event == 'c_exception':
        # We don't want exception details, yet
        pass

    return traceit
