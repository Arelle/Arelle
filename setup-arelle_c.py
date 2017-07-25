from distutils.core import setup
from distutils.extension import Extension
from Cython.Distutils import build_ext


def get_version():
    """
    Utility function to return the current version of the library, as defined
    by the version string in the arelle's _pkg_meta.py file. The format follows
    the standard Major.Minor.Fix notation.
    
    To compile for arelle (python) debugging (leaves .so in arelle where it is needed by debugger):

    src-cython hermf$ touch arelle_cython/arelle.arelle_c.pyx; time python3.5 setup-arelle_C.py build_ext --inplace > ~/temp/log.txt 2>&1

    :return: The version string in the standard Major.Minor.Fix notation.
    :rtype: str
    """
    import imp

    source_dir = 'arelle'

    with open('{}/_pkg_meta.py'.format(source_dir), 'rb') as fp:
        mod = imp.load_source('_pkg_meta', source_dir, fp)

    return mod.version

setup( name="Arelle_c",
       version=get_version(),
       author='arelle.org',
       author_email='support@arelle.org',
       url='http://www.arelle.org',
       download_url='http://www.arelle.org/download',
       license='Apache-2',
       keywords=['xbrl'],
       description='An open source XBRL platform',
       long_description=open('README.md').read(),
       packages=[ "arelle_c" ],
       classifiers=[ 
        'Development Status :: 1 - Active',
        'Intended Audience :: End Users/Desktop',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache-2 License',
        'Natural Language :: English',
        'Programming Language :: Cython',
        'Programming Language :: Python :: 3.5'
        ],
       cmdclass=dict( build_ext=build_ext ),
       ext_modules=[ Extension( "arelle.arelle_c",
                                [ "arelle_cython/arelle.arelle_c.pyx" ],
                                include_dirs = ['/usr/local/include'],
                                library_dirs = ['/usr/local/lib'],
                                language="c++",
                                libraries=[ "stdc++",
                                            "xerces-c" ] ) ] )
