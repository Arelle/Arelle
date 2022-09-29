# -*- coding: utf-8 -*-

'''
This package is python_ntlm, unaltered, from the original at:

    https://github.com/mullender/python-ntlm/tree/master/python30/ntlm

This library is free software: you can redistribute it and/or
modify it under the terms of the GNU Lesser General Public
License as published by the Free Software Foundation, either
version 3 of the License, or (at your option) any later version.

This library is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public
License along with this library.  If not, see <http://www.gnu.org/licenses/> or <http://www.gnu.org/licenses/lgpl.txt>.


'''

# provide HTTPNtlmAuthHandler to Arelle as a plugin

def getHTTPNtlmAuthHandler(*args, **kwargs):
    try:
        from . import HTTPNtlmAuthHandler
        return HTTPNtlmAuthHandler
    except ImportError:
        return None

__pluginInfo__ = {
    'name': 'NTLM Proxy Handler',
    'version': '1.1.0',
    'description': "Python NTLM proxy handler.",
    'license': 'LGPL 3.0',
    'author': 'Matthijs Mullender',
    'copyright': 'Not copyrighted.',
    # classes of mount points (required)
    'Proxy.HTTPNtlmAuthHandler': getHTTPNtlmAuthHandler
    }
