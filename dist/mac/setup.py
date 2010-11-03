"""
This is a setup.py script generated by py2applet

Usage:
    python setup.py py2app
"""

from setuptools import setup
import sys

VERSION = '1.6.beta'

plist = dict(
    CFBundleName='VisTrails',
    CFBundleShortVersionString=VERSION,
    CFBundleGetInfoString=' '.join(['VisTrails', VERSION]),
    CFBundleExecutable='vistrails',
    CFBundleIdentifier='edu.utah.sci.vistrails',
)

sys.path.append('../../vistrails')
APP = ['../../vistrails/vistrails.py']
#comma-separated list of additional data files and
#folders to include (not for code!)
#DATA_FILES = ['/usr/local/graphviz-2.12/bin/dot',]
OPTIONS = {'argv_emulation': True,
           'iconfile': 'resources/vistrails_icon.icns',
           'includes': 'sip,pylab,xml,\
			libxml2,libxslt, Cookie, BaseHTTPServer, multifile, \
                        shelve, uuid, gridfield, gridfield.core, \
                        gridfield.algebra, gridfield.gfvis, gridfield.selfe, \
                        sine,st,Numeric,pexpect,psycopg2,sqlite3',
           'packages': 'PyQt4,vtk,MySQLdb,matplotlib,tables,packages,core,gui,db,numpy,scipy,ZSI,api,twisted,pyGridWare,Ft,Scientific,dbflib,shapelib,distutils,h5py',
           'plist': plist,
           }

setup(
    app=APP,
 #   data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
