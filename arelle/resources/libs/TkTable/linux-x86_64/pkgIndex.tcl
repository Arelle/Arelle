# -*- tcl -*-
# Tcl package index file, version 1.1
#
if {[package vsatisfies [package provide Tcl] 9.0-]} {
    package ifneeded Tktable 2.12.1 [list apply {{dir} {
	# Load library
	load [file join $dir libtcl9Tktable2.12.1.so] [string totitle Tktable]

	# Source init file
	set initScript [file join $dir tkTable.tcl]
	if {[file exists $initScript]} {
	    source -encoding utf-8 $initScript
	}
    }} $dir]
} else {
    if {![package vsatisfies [package provide Tcl] 8.5]} {return}
    package ifneeded Tktable 2.12.1 [list apply {{dir} {
	# Load library
	if {[string tolower [file extension libTktable2.12.1.so]] in [list .dll .dylib .so]} {
	    # Load dynamic library
	    load [file join $dir libTktable2.12.1.so] [string totitle Tktable]
	} else {
	    # Static library
	    load {} [string totitle Tktable]
	}

	# Source init file
	set initScript [file join $dir tkTable.tcl]
	if {[file exists $initScript]} {
	    source -encoding utf-8 $initScript
	}
    }} $dir]
}
