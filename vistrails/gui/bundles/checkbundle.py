###############################################################################
##
## Copyright (C) 2011-2013, NYU-Poly.
## Copyright (C) 2006-2011, University of Utah. 
## All rights reserved.
## Contact: contact@vistrails.org
##
## This file is part of VisTrails.
##
## "Redistribution and use in source and binary forms, with or without 
## modification, are permitted provided that the following conditions are met:
##
##  - Redistributions of source code must retain the above copyright notice, 
##    this list of conditions and the following disclaimer.
##  - Redistributions in binary form must reproduce the above copyright 
##    notice, this list of conditions and the following disclaimer in the 
##    documentation and/or other materials provided with the distribution.
##  - Neither the name of the University of Utah nor the names of its 
##    contributors may be used to endorse or promote products derived from 
##    this software without specific prior written permission.
##
## THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" 
## AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, 
## THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR 
## PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR 
## CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, 
## EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, 
## PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; 
## OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, 
## WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR 
## OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF 
## ADVISED OF THE POSSIBILITY OF SUCH DAMAGE."
##
###############################################################################

"""Module with utilities to inspect bundles, if possible."""
from vistrails.gui.bundles.utils import guess_system
import vistrails.gui.bundles.checkbundle # this is on purpose
import sys

##############################################################################

def linux_ubuntu_check(package_name):
    import apt_pkg
    apt_pkg.init()
    cache = apt_pkg.GetCache()
    depcache = apt_pkg.GetDepCache(cache)

    def get_single_package(name):
        if not isinstance(name, str):
            raise TypeError("Expected string")
        cache = apt_pkg.GetCache()
        depcache = apt_pkg.GetDepCache(cache)
        records = apt_pkg.GetPkgRecords(cache)
        sourcelist = apt_pkg.GetPkgSourceList()
        pkg = apt_pkg.package.Package(cache, depcache, records,
                                      sourcelist, None, cache[sys.argv[1]])
        return pkg

    if isinstance(package_name, str):
        return get_single_package(package_name).candidateVersion
    elif isinstance(package_name, list):
        return [get_single_package(name).candidateVersion
                for name in package_name]

def get_version(dependency_dictionary):
    """Tries to determine a bundle version.
    """
    distro = guess_system()
    if not dependency_dictionary.has_key(distro):
        return None
    else:
        callable_ = getattr(vistrails.gui.bundles.checkbundle,
                            distro.replace('-', '_') + '_get_version')
        
        return callable_(dependency_dictionary[distro])
