# table.tcl --
#
# Version align with tkTable 2.7, jeff at hobbs org
# This file defines the default bindings for Tk table widgets
# and provides procedures that help in implementing those bindings.
#

#--------------------------------------------------------------------------
# ::tktable::Priv elements used in this file:
#
# x && y -		Coords in widget
# afterId -		Token returned by "after" for autoscanning.
# tablePrev -		The last element to be selected or deselected
#			during a selection operation.
# mouseMoved -		Boolean to indicate whether mouse moved while
#			the button was pressed.
# borderInfo -		Boolean to know if the user clicked on a border
# borderB1 -		Boolean that set whether B1 can be used for the
#			interactiving resizing
#--------------------------------------------------------------------------

namespace eval ::tktable {
    # Ensure that a namespace is created for us
    variable Priv
    array set Priv [list x 0 y 0 afterId {} mouseMoved 0 \
	    borderInfo {} borderB1 1]
}

# ::tktable::ClipboardKeysyms --
# This procedure is invoked to identify the keys that correspond to
# the "copy", "cut", and "paste" functions for the clipboard.
#
# Arguments:
# copy -	Name of the key (keysym name plus modifiers, if any,
#		such as "Meta-y") used for the copy operation.
# cut -		Name of the key used for the cut operation.
# paste -	Name of the key used for the paste operation.

proc ::tktable::ClipboardKeysyms {copy cut paste} {
    bind Table <$copy>	{tk_tableCopy %W}
    bind Table <$cut>	{tk_tableCut %W}
    bind Table <$paste>	{tk_tablePaste %W}
}
::tktable::ClipboardKeysyms <Copy> <Cut> <Paste>

##
## Interactive cell resizing, affected by -resizeborders option
##
bind Table <3>		{
    ## You might want to check for cell returned if you want to
    ## restrict the resizing of certain cells
    %W border mark %x %y
}
bind Table <B3-Motion>	{ %W border dragto %x %y }

## Button events

bind Table <1> { ::tktable::Button1 %W %x %y }
bind Table <B1-Motion> { ::tktable::B1Motion %W %x %y }

bind Table <ButtonRelease-1> {
    if {$::tktable::Priv(borderInfo) eq "" && [winfo exists %W]} {
	::tktable::CancelRepeat
	%W activate @%x,%y
    }
}
bind Table <Double-1> {
    # empty
}

bind Table <Shift-1>	{::tktable::BeginExtend %W [%W index @%x,%y]}
bind Table <Control-1>	{::tktable::BeginToggle %W [%W index @%x,%y]}
bind Table <B1-Enter>	{::tktable::CancelRepeat}
bind Table <B1-Leave>	{
    if {$::tktable::Priv(borderInfo) eq ""} {
	array set ::tktable::Priv {x %x y %y}
	::tktable::AutoScan %W
    }
}
bind Table <2> {
    %W scan mark %x %y
    array set ::tktable::Priv {x %x y %y}
    set ::tktable::Priv(mouseMoved) 0
}
bind Table <B2-Motion> {
    if {(%x != $::tktable::Priv(x)) || (%y != $::tktable::Priv(y))} {
	set ::tktable::Priv(mouseMoved) 1
    }
    if {$::tktable::Priv(mouseMoved)} { %W scan dragto %x %y }
}
bind Table <ButtonRelease-2> {
    if {!$::tktable::Priv(mouseMoved)} { tk_tablePaste %W [%W index @%x,%y] }
}

## Mouse wheel events

if {[package vcompare [package present Tk] 8.7] >= 0} {
    bind Table <MouseWheel> {tk::MouseWheel %W y %D -40.0}
    bind Table <Option-MouseWheel> {tk::MouseWheel %W y %D -12.0}
    bind Table <Shift-MouseWheel> {tk::MouseWheel %W x %D -40.0}
    bind Table <Shift-Option-MouseWheel> {tk::MouseWheel %W x %D -12.0}

} else {
    if {[tk windowingsystem] eq "aqua"} {
	bind Table <MouseWheel>		{%W yview scroll [expr {-%D}] units}
	bind Table <Shift-MouseWheel>	{%W xview scroll [expr {-%D}] units}
	bind Table <Option-MouseWheel>	{%W yview scroll [expr {-10 * %D}] units}
	bind Table <Shift-Option-MouseWheel> {%W xview scroll [expr {-10 * %D}] units}
    } else {
	bind Table <MouseWheel>		{%W yview scroll [expr {-%D / 120}] units}
	bind Table <Shift-MouseWheel>	{%W xview scroll [expr {-%D / 120}] units}
    }

    if {[tk windowingsystem] eq "x11"} {
	bind Table <Button-4>		{%W yview scroll -5 units}
	bind Table <Shift-Button-4>	{%W xview scroll -5 units}
	bind Table <Button-5>		{%W yview scroll  5 units}
	bind Table <Shift-Button-5>	{%W xview scroll  5 units}
    }
}

## Touchpad scrolling
#
if {[package vcompare [package present Tk] 8.7] >= 0} {
bind Table <TouchpadScroll> {
    if {%# %% 5 != 0} {
        return
    }
    lassign [tk::PreciseScrollDeltas %D] tk::Priv(deltaX) tk::Priv(deltaY)
    if {$tk::Priv(deltaX) != 0} {
 	%W xview scroll [expr {-$tk::Priv(deltaX)}] units
    }
    if {$tk::Priv(deltaY) != 0} {
	%W yview scroll [expr {-$tk::Priv(deltaY)}] units
    }
}
}

## Key events

# This forces a cell commit if an active cell exists
bind Table <<Table_Commit>> {
    catch {%W activate active}
}
# Remove this if you don't want cell commit to occur on every Leave for
# the table (via mouse) or FocusOut (loss of focus by table).
event add <<Table_Commit>> <Leave> <FocusOut>

bind Table <Shift-Up>		{::tktable::ExtendSelect %W -1  0}
bind Table <Shift-Down>		{::tktable::ExtendSelect %W  1  0}
bind Table <Shift-Left>		{::tktable::ExtendSelect %W  0 -1}
bind Table <Shift-Right>	{::tktable::ExtendSelect %W  0  1}
bind Table <Prior>		{%W yview scroll -1 pages; %W activate topleft}
bind Table <Next>		{%W yview scroll  1 pages; %W activate topleft}
bind Table <Control-Prior>	{%W xview scroll -1 pages}
bind Table <Control-Next>	{%W xview scroll  1 pages}
bind Table <Home>		{%W see origin}
bind Table <End>		{%W see end}
bind Table <Control-Home> {
    %W selection clear all
    %W activate origin
    %W selection set active
    %W see active
}
bind Table <Control-End> {
    %W selection clear all
    %W activate end
    %W selection set active
    %W see active
}
bind Table <Shift-Control-Home>	{::tktable::DataExtend %W origin}
bind Table <Shift-Control-End>	{::tktable::DataExtend %W end}
bind Table <Select>		{::tktable::BeginSelect %W [%W index active]}
bind Table <Shift-Select>	{::tktable::BeginExtend %W [%W index active]}
bind Table <Control-slash>	{::tktable::SelectAll %W}
bind Table <Control-backslash> {
    if {[string match browse [%W cget -selectmode]]} {%W selection clear all}
}
bind Table <Up>			{::tktable::MoveCell %W -1  0}
bind Table <Down>		{::tktable::MoveCell %W  1  0}
bind Table <Left>		{::tktable::MoveCell %W  0 -1}
bind Table <Right>		{::tktable::MoveCell %W  0  1}
bind Table <KeyPress>		{::tktable::Insert %W %A}
bind Table <BackSpace>		{::tktable::BackSpace %W}
bind Table <Delete>		{%W delete active insert}
bind Table <Escape>		{%W reread}

#bind Table <Return>		{::tktable::MoveCell %W 1 0}
bind Table <Return>		{::tktable::Insert %W "\n"}

bind Table <Control-Left>	{%W icursor [expr {[%W icursor]-1}]}
bind Table <Control-Right>	{%W icursor [expr {[%W icursor]+1}]}
bind Table <Control-e>		{%W icursor end}
bind Table <Control-a>		{%W icursor 0}
bind Table <Control-k>		{%W delete active insert end}
bind Table <Control-equal>	{::tktable::ChangeWidth %W active  1}
bind Table <Control-minus>	{::tktable::ChangeWidth %W active -1}

# Ignore all Alt, Meta, and Control keypresses unless explicitly bound.
# Otherwise, if a widget binding for one of these is defined, the
# <KeyPress> class binding will also fire and insert the character,
# which is wrong.  Ditto for Tab.

bind Table <Alt-KeyPress>	{# nothing}
bind Table <Meta-KeyPress>	{# nothing}
bind Table <Control-KeyPress>	{# nothing}
bind Table <Any-Tab>		{# nothing}
if {[string match "macintosh" $::tcl_platform(platform)]} {
    bind Table <Command-KeyPress> {# nothing}
}

# ::tktable::GetSelection --
#   This tries to obtain the default selection.  On Unix, we first try
#   and get a UTF8_STRING, a type supported by modern Unix apps for
#   passing Unicode data safely.  We fall back on the default STRING
#   type otherwise.  On Windows, only the STRING type is necessary.
# Arguments:
#   w	The widget for which the selection will be retrieved.
#	Important for the -displayof property.
#   sel	The source of the selection (PRIMARY or CLIPBOARD)
# Results:
#   Returns the selection, or an error if none could be found
#
if {$::tcl_platform(platform) ne "unix"} {
    proc ::tktable::GetSelection {w {sel PRIMARY}} {
	if {[catch {selection get -displayof $w -selection $sel} txt]} {
	    return -code error "could not find default selection"
	} else {
	    return $txt
	}
    }
} else {
    proc ::tktable::GetSelection {w {sel PRIMARY}} {
	if {[catch {selection get -displayof $w -selection $sel \
		-type UTF8_STRING} txt] \
		&& [catch {selection get -displayof $w -selection $sel} txt]} {
	    return -code error "could not find default selection"
	} else {
	    return $txt
	}
    }
}

# ::tktable::CancelRepeat --
# A copy of tkCancelRepeat, just in case it's not available or changes.
# This procedure is invoked to cancel an auto-repeat action described
# by ::tktable::Priv(afterId).  It's used by several widgets to auto-scroll
# the widget when the mouse is dragged out of the widget with a
# button pressed.
#
# Arguments:
# None.

proc ::tktable::CancelRepeat {} {
    variable Priv
    after cancel $Priv(afterId)
    set Priv(afterId) {}
}

# ::tktable::Insert --
#
#   Insert into the active cell
#
# Arguments:
#   w	- the table widget
#   s	- the string to insert
# Results:
#   Returns nothing
#
proc ::tktable::Insert {w s} {
    if {$s ne {}} {
	$w insert active insert $s
    }
}

# ::tktable::BackSpace --
#
#   BackSpace in the current cell
#
# Arguments:
#   w	- the table widget
# Results:
#   Returns nothing
#
proc ::tktable::BackSpace {w} {
    set cur [$w icursor]
    if {$cur ne {} && $cur > 0} {
	$w delete active [expr {$cur-1}]
    }
}

# ::tktable::Button1 --
#
# This procedure is called to handle selecting with mouse button 1.
# It will distinguish whether to start selection or mark a border.
#
# Arguments:
#   w	- the table widget
#   x	- x coord
#   y	- y coord
# Results:
#   Returns nothing
#
proc ::tktable::Button1 {w x y} {
    variable Priv
    #
    # $Priv(borderInfo) is null if the user did not click on a border
    #
    if {$Priv(borderB1) == 1} {
	set Priv(borderInfo) [$w border mark $x $y]
	# account for what resizeborders are set [Bug 876320] (ferenc)
	set rbd [$w cget -resizeborders]
	if {$rbd eq "none" || ![llength $Priv(borderInfo)]
	    || ($rbd eq "col" && [lindex $Priv(borderInfo) 1] eq "")
	    || ($rbd eq "row" && [lindex $Priv(borderInfo) 0] eq "")} {
	    set Priv(borderInfo) ""
	}
    } else {
	set Priv(borderInfo) ""
    }
    if {$Priv(borderInfo) eq ""} {
	#
	# Only do this when a border wasn't selected
	#
	if {[winfo exists $w]} {
	    ::tktable::BeginSelect $w [$w index @$x,$y]
	    focus $w
	}
	array set Priv [list x $x y $y]
	set Priv(mouseMoved) 0
    }
}

# ::tktable::B1Motion --
#
# This procedure is called to start processing mouse motion events while
# button 1 moves while pressed.  It will distinguish whether to change
# the selection or move a border.
#
# Arguments:
#   w	- the table widget
#   x	- x coord
#   y	- y coord
# Results:
#   Returns nothing
#
proc ::tktable::B1Motion {w x y} {
    variable Priv

    # If we already had motion, or we moved more than 1 pixel,
    # then we start the Motion routine
    if {$Priv(borderInfo) ne ""} {
	#
	# If the motion is on a border, drag it and skip the rest
	# of this binding.
	#
	$w border dragto $x $y
    } else {
	#
	# If we already had motion, or we moved more than 1 pixel,
	# then we start the Motion routine
	#
	if {
	    $::tktable::Priv(mouseMoved)
	    || abs($x-$::tktable::Priv(x)) > 1
	    || abs($y-$::tktable::Priv(y)) > 1
	} {
	    set ::tktable::Priv(mouseMoved) 1
	}
	if {$::tktable::Priv(mouseMoved)} {
	    ::tktable::Motion $w [$w index @$x,$y]
	}
    }
}

# ::tktable::BeginSelect --
#
# This procedure is typically invoked on button-1 presses. It begins
# the process of making a selection in the table. Its exact behavior
# depends on the selection mode currently in effect for the table;
# see the Motif documentation for details.
#
# Arguments:
# w	- The table widget.
# el	- The element for the selection operation (typically the
#	one under the pointer).  Must be in row,col form.

proc ::tktable::BeginSelect {w el} {
    variable Priv
    if {[scan $el %d,%d r c] != 2} return
    switch [$w cget -selectmode] {
	multiple {
	    if {[$w tag includes title $el]} {
		## in the title area
		if {$r < [$w cget -titlerows]+[$w cget -roworigin]} {
		    ## We're in a column header
		    if {$c < [$w cget -titlecols]+[$w cget -colorigin]} {
			## We're in the topleft title area
			set inc topleft
			set el2 end
		    } else {
			set inc [$w index topleft row],$c
			set el2 [$w index end row],$c
		    }
		} else {
		    ## We're in a row header
		    set inc $r,[$w index topleft col]
		    set el2 $r,[$w index end col]
		}
	    } else {
		set inc $el
		set el2 $el
	    }
	    if {[$w selection includes $inc]} {
		$w selection clear $el $el2
	    } else {
		$w selection set $el $el2
	    }
	}
	extended {
	    $w selection clear all
	    if {[$w tag includes title $el]} {
		if {$r < [$w cget -titlerows]+[$w cget -roworigin]} {
		    ## We're in a column header
		    if {$c < [$w cget -titlecols]+[$w cget -colorigin]} {
			## We're in the topleft title area
			$w selection set $el end
		    } else {
			$w selection set $el [$w index end row],$c
		    }
		} else {
		    ## We're in a row header
		    $w selection set $el $r,[$w index end col]
		}
	    } else {
		$w selection set $el
	    }
	    $w selection anchor $el
	    set Priv(tablePrev) $el
	}
	default {
	    if {![$w tag includes title $el]} {
		$w selection clear all
		$w selection set $el
		set Priv(tablePrev) $el
	    }
	    $w selection anchor $el
	}
    }
}

# ::tktable::Motion --
#
# This procedure is called to process mouse motion events while
# button 1 is down. It may move or extend the selection, depending
# on the table's selection mode.
#
# Arguments:
# w	- The table widget.
# el	- The element under the pointer (must be in row,col form).

proc ::tktable::Motion {w el} {
    variable Priv
    if {![info exists Priv(tablePrev)]} {
	set Priv(tablePrev) $el
	return
    }
    if {[string match $Priv(tablePrev) $el]} return
    switch [$w cget -selectmode] {
	browse {
	    $w selection clear all
	    $w selection set $el
	    set Priv(tablePrev) $el
	}
	extended {
	    # avoid tables that have no anchor index yet.
	    if {[catch {$w index anchor}]} { return }
	    scan $Priv(tablePrev) %d,%d r c
	    scan $el %d,%d elr elc
	    if {[$w tag includes title $el]} {
		if {$r < [$w cget -titlerows]+[$w cget -roworigin]} {
		    ## We're in a column header
		    if {$c < [$w cget -titlecols]+[$w cget -colorigin]} {
			## We're in the topleft title area
			$w selection clear anchor end
		    } else {
			$w selection clear anchor [$w index end row],$c
		    }
		    $w selection set anchor [$w index end row],$elc
		} else {
		    ## We're in a row header
		    $w selection clear anchor $r,[$w index end col]
		    $w selection set anchor $elr,[$w index end col]
		}
	    } else {
		$w selection clear anchor $Priv(tablePrev)
		$w selection set anchor $el
	    }
	    set Priv(tablePrev) $el
	}
    }
}

# ::tktable::BeginExtend --
#
# This procedure is typically invoked on shift-button-1 presses. It
# begins the process of extending a selection in the table. Its
# exact behavior depends on the selection mode currently in effect
# for the table; see the Motif documentation for details.
#
# Arguments:
# w - The table widget.
# el - The element for the selection operation (typically the
# one under the pointer). Must be in numerical form.

proc ::tktable::BeginExtend {w el} {
    # avoid tables that have no anchor index yet.
    if {[catch {$w index anchor}]} { return }
    if {[string match extended [$w cget -selectmode]] &&
	[$w selection includes anchor]} {
	::tktable::Motion $w $el
    }
}

# ::tktable::BeginToggle --
#
# This procedure is typically invoked on control-button-1 presses. It
# begins the process of toggling a selection in the table. Its
# exact behavior depends on the selection mode currently in effect
# for the table; see the Motif documentation for details.
#
# Arguments:
# w - The table widget.
# el - The element for the selection operation (typically the
# one under the pointer). Must be in numerical form.

proc ::tktable::BeginToggle {w el} {
    if {[string match extended [$w cget -selectmode]]} {
	variable Priv
	set Priv(tablePrev) $el
	$w selection anchor $el
	if {[$w tag includes title $el]} {
	    scan $el %d,%d r c
	    if {$r < [$w cget -titlerows]+[$w cget -roworigin]} {
		## We're in a column header
		if {$c < [$w cget -titlecols]+[$w cget -colorigin]} {
		    ## We're in the topleft title area
		    set end end
		} else {
		    set end [$w index end row],$c
		}
	    } else {
		## We're in a row header
		set end $r,[$w index end col]
	    }
	} else {
	    ## We're in a non-title cell
	    set end $el
	}
	if {[$w selection includes  $end]} {
	    $w selection clear $el $end
	} else {
	    $w selection set   $el $end
        }
    }
}

# ::tktable::AutoScan --
# This procedure is invoked when the mouse leaves an table window
# with button 1 down. It scrolls the window up, down, left, or
# right, depending on where the mouse left the window, and reschedules
# itself as an "after" command so that the window continues to scroll until
# the mouse moves back into the window or the mouse button is released.
#
# Arguments:
# w - The table window.

proc ::tktable::AutoScan {w} {
    if {![winfo exists $w]} return
    variable Priv
    set x $Priv(x)
    set y $Priv(y)
    if {$y >= [winfo height $w]} {
	$w yview scroll 1 units
    } elseif {$y < 0} {
	$w yview scroll -1 units
    } elseif {$x >= [winfo width $w]} {
	$w xview scroll 1 units
    } elseif {$x < 0} {
	$w xview scroll -1 units
    } else {
	return
    }
    ::tktable::Motion $w [$w index @$x,$y]
    set Priv(afterId) [after 50 ::tktable::AutoScan $w]
}

# ::tktable::MoveCell --
#
# Moves the location cursor (active element) by the specified number
# of cells and changes the selection if we're in browse or extended
# selection mode.  If the new cell is "hidden", we skip to the next
# visible cell if possible, otherwise just abort.
#
# Arguments:
# w - The table widget.
# x - +1 to move down one cell, -1 to move up one cell.
# y - +1 to move right one cell, -1 to move left one cell.

proc ::tktable::MoveCell {w x y} {
    if {[catch {$w index active row} r]} return
    set c [$w index active col]
    set cell [$w index [incr r $x],[incr c $y]]
    while {[set true [$w hidden $cell]] ne {}} {
	# The cell is in some way hidden
	if {[$w index active] ne $true} {
	    # The span cell wasn't the previous cell, so go to that
	    set cell $true
	    break
	}
	if {$x > 0} {incr r} elseif {$x < 0} {incr r -1}
	if {$y > 0} {incr c} elseif {$y < 0} {incr c -1}
	if {[$w index $r,$c] ne $cell} {
	    set cell [$w index $r,$c]
	} else {
	    # We couldn't find a non-hidden cell, just don't move
	    return
	}
    }
    $w activate $cell
    $w see active
    switch [$w cget -selectmode] {
	browse {
	    $w selection clear all
	    $w selection set active
	}
	extended {
	    variable Priv
	    $w selection clear all
	    $w selection set active
	    $w selection anchor active
	    set Priv(tablePrev) [$w index active]
	}
    }
}

# ::tktable::ExtendSelect --
#
# Does nothing unless we're in extended selection mode; in this
# case it moves the location cursor (active element) by the specified
# number of cells, and extends the selection to that point.
#
# Arguments:
# w - The table widget.
# x - +1 to move down one cell, -1 to move up one cell.
# y - +1 to move right one cell, -1 to move left one cell.

proc ::tktable::ExtendSelect {w x y} {
    if {[$w cget -selectmode] ne "extended" ||
	[catch {$w index active row} r]} return
    set c [$w index active col]
    $w activate [incr r $x],[incr c $y]
    $w see active
    ::tktable::Motion $w [$w index active]
}

# ::tktable::DataExtend
#
# This procedure is called for key-presses such as Shift-KEndData.
# If the selection mode isnt multiple or extend then it does nothing.
# Otherwise it moves the active element to el and, if we're in
# extended mode, extends the selection to that point.
#
# Arguments:
# w - The table widget.
# el - An integer cell number.

proc ::tktable::DataExtend {w el} {
    set mode [$w cget -selectmode]
    if {[string match extended $mode]} {
	$w activate $el
	$w see $el
	if {[$w selection includes anchor]} {::tktable::Motion $w $el}
    } elseif {[string match multiple $mode]} {
	$w activate $el
	$w see $el
    }
}

# ::tktable::SelectAll
#
# This procedure is invoked to handle the "select all" operation.
# For single and browse mode, it just selects the active element.
# Otherwise it selects everything in the widget.
#
# Arguments:
# w - The table widget.

proc ::tktable::SelectAll {w} {
    if {[regexp {^(single|browse)$} [$w cget -selectmode]]} {
	$w selection clear all
	catch {$w selection set active}
    } elseif {[$w cget -selecttitles]} {
	$w selection set [$w cget -roworigin],[$w cget -colorigin] end
    } else {
	$w selection set origin end
    }
}

# ::tktable::ChangeWidth --
#
# Adjust the widget of the specified cell by $a.
#
# Arguments:
# w - The table widget.
# i - cell index
# a - amount to adjust by

proc ::tktable::ChangeWidth {w i a} {
    set tmp [$w index $i col]
    if {[set width [$w width $tmp]] >= 0} {
	$w width $tmp [incr width $a]
    } else {
	$w width $tmp [incr width [expr {-$a}]]
    }
}

# tk_tableCopy --
#
# This procedure copies the selection from a table widget into the
# clipboard.
#
# Arguments:
# w -		Name of a table widget.

proc tk_tableCopy w {
    if {[selection own -displayof $w] eq $w} {
	clipboard clear -displayof $w
	catch {clipboard append -displayof $w [::tktable::GetSelection $w]}
    }
}

# tk_tableCut --
#
# This procedure copies the selection from a table widget into the
# clipboard, then deletes the selection (if it exists in the given
# widget).
#
# Arguments:
# w -		Name of a table widget.

proc tk_tableCut w {
    if {[selection own -displayof $w] eq $w} {
	clipboard clear -displayof $w
	catch {
	    clipboard append -displayof $w [::tktable::GetSelection $w]
	    $w cursel {}
	    $w selection clear all
	}
    }
}

# tk_tablePaste --
#
# This procedure pastes the contents of the clipboard to the specified
# cell (active by default) in a table widget.
#
# Arguments:
# w -		Name of a table widget.
# cell -	Cell to start pasting in.
#
proc tk_tablePaste {w {cell {}}} {
    if {$cell ne {}} {
	if {[catch {::tktable::GetSelection $w} data]} return
    } else {
	if {[catch {::tktable::GetSelection $w CLIPBOARD} data]} {
	    return
	}
	set cell active
    }
    tk_tablePasteHandler $w [$w index $cell] $data
    if {[$w cget -state] eq "normal"} {focus $w}
}

# tk_tablePasteHandler --
#
# This procedure handles how data is pasted into the table widget.
# This handles data in the default table selection form.
#
# NOTE: this allows pasting into all cells except title cells,
#       even those with -state disabled
#
# Arguments:
# w -		Name of a table widget.
# cell -	Cell to start pasting in.
#
proc tk_tablePasteHandler {w cell data} {
    #
    # Don't allow pasting into the title cells
    #
    if {[$w tag includes title $cell]} {
        return
    }

    set rows	[expr {[$w cget -rows]-[$w cget -roworigin]}]
    set cols	[expr {[$w cget -cols]-[$w cget -colorigin]}]
    set r	[$w index $cell row]
    set c	[$w index $cell col]
    set rsep	[$w cget -rowseparator]
    set csep	[$w cget -colseparator]
    set vcmd	[$w cget -validatecommand]

    ## Assume separate rows are split by row separator if specified
    ## If you were to want multi-character row separators, you would need:
    # regsub -all $rsep $data <newline> data
    # set data [join $data <newline>]
    if {$rsep ne {}} {
	set data [split $data $rsep]
    }
    set row	$r
    foreach line $data {
	if {$row > $rows} break
	set col	$c
	## Assume separate cols are split by col separator if specified
	## Unless a -separator was specified
	if {$csep ne {}} {
	    set line [split $line $csep]
	}
	## If you were to want multi-character col separators, you would need:
	# regsub -all $csep $line <newline> line
	# set line [join $line <newline>]
	foreach item $line {
	    if {$col > $cols} break
	    set oldTxt [$w get $row,$col]
	    if {![string equal $item $oldTxt] && $vcmd ne ""} {
		set vldCmd [string map [list %W $w %r $row %c $col %s $oldTxt %S $item] $vcmd]
		if {![eval $vldCmd]} {
		    incr col
		    continue ;# skip update
		}
	    }
	    $w set $row,$col $item
	    incr col
	}
	incr row
    }
}

# tktable::Sort --
#
# This procedure handles how data is sorted in the table widget.
# This isn't currently used by tktable, but can be called by the user.
# It's behavior may change in the future.
#
# Arguments:
# w -		Name of a table widget.
# start -	start cell of rectangle to sort
# end -		end cell of rectangle to sort
# col -		column within rectangle to sort on
# args -	passed to lsort proc (ie: -integer -decreasing)

proc ::tktable::Sort {w start end col args} {
    set start [$w index $start]
    set end   [$w index $end]
    scan $start %d,%d sr sc
    scan $end   %d,%d er ec
    if {($col < $sc) || ($col > $ec)} {
	return -code error "$col is not within sort range $sc to $ec"
    }
    set col [expr {$col - $sc}]

    set data {}
    for {set i $sr} {$i <= $er} {incr i} {
	lappend data [$w get $i,$sc $i,$ec]
    }

    set i $sr
    foreach row [eval [list lsort -index $col] $args [list $data]] {
	$w set row $i,$sc $row
	incr i
    }
}
