##
## Small python text editor based on the
## Very simple VT100 terminal text editor widget
## Copyright (c) 2015 Paul Sokolovsky (initial code)
## Copyright (c) 2015 Robert Hammelrath (additional code)
## Distributed under MIT License
## Changes:
## - Ported the code to PyBoard and Wipy (still runs on Linux or Darwin)
##   It uses VCP_USB on Pyboard and sys.stdin on WiPy, or UART, if selected.
## - changed read keyboard function to comply with char-by-char input
## - added support for TAB, BACKTAB, SAVE, DEL and Backspace joining lines,
##   Find, Replace, Goto Line, UNDO, GET file, Auto-Indent, Set Flags,
##   Copy/Delete & Paste, Indent, Un-Indent
## - Added mouse support for pointing and scrolling (not WiPy)
## - handling tab (0x09) on reading & writing files,
## - Added a status line, line number column and single line prompts for
##   Quit, Save, Find, Replace, Flags and Goto
## - moved main into a function with some optional parameters
##
import sys, gc
#ifdef LINUX
if sys.platform in ("linux", "darwin"):
    import os, signal, tty, termios
#endif
#ifdef DEFINES
#define KEY_UP          0x0b
#define KEY_DOWN        0x0d
#define KEY_LEFT        0x1f
#define KEY_RIGHT       0x0f
#define KEY_HOME        0x10
#define KEY_END         0x03
#define KEY_PGUP        0x17
#define KEY_PGDN        0x19
#define KEY_QUIT        0x11
#define KEY_ENTER       0x0a
#define KEY_BACKSPACE   0x08
#define KEY_DELETE      0x7f
#define KEY_WRITE       0x13
#define KEY_TAB         0x09
#define KEY_BACKTAB     0x15
#define KEY_FIND        0x06
#define KEY_GOTO        0x07
#define KEY_FIRST       0x02
#define KEY_LAST        0x14
#define KEY_FIND_AGAIN  0x0e
#define KEY_YANK        0x18
#define KEY_ZAP         0x16
#define KEY_TOGGLE      0x01
#define KEY_REPLC       0x12
#define KEY_DUP         0x04
#define KEY_MOUSE       0x1b
#define KEY_SCRLUP      0x1c
#define KEY_SCRLDN      0x1d
#define KEY_REDRAW      0x05
#define KEY_UNDO        0x1a
#define KEY_GET         0x1e
#define KEY_MARK        0x0c
#define KEY_INDENT      0xffff
#else
KEY_UP        = 0x0b
KEY_DOWN      = 0x0d
KEY_LEFT      = 0x1f
KEY_RIGHT     = 0x0f
KEY_HOME      = 0x10
KEY_END       = 0x03
KEY_PGUP      = 0x17
KEY_PGDN      = 0x19
KEY_QUIT      = 0x11
KEY_ENTER     = 0x0a
KEY_BACKSPACE = 0x08
KEY_DELETE    = 0x7f
KEY_WRITE     = 0x13
KEY_TAB       = 0x09
KEY_BACKTAB   = 0x15
KEY_FIND      = 0x06
KEY_GOTO      = 0x07
KEY_MOUSE     = 0x1b
KEY_SCRLUP    = 0x1c
KEY_SCRLDN    = 0x1d
KEY_FIND_AGAIN= 0x0e
KEY_REDRAW    = 0x05
KEY_UNDO      = 0x1a
KEY_YANK      = 0x18
KEY_ZAP       = 0x16
KEY_DUP       = 0x04
KEY_FIRST     = 0x02
KEY_LAST      = 0x14
KEY_REPLC     = 0x12
KEY_MOUSE     = 0x1b
KEY_SCRLUP    = 0x1c
KEY_SCRLDN    = 0x1d
KEY_TOGGLE    = 0x01
KEY_GET       = 0x1e
KEY_MARK      = 0x0c
KEY_INDENT    = 0xffff
#endif

class Editor:

    KEYMAP = { ## Gets lengthy
    b"\x1b[A" : KEY_UP,
    b"\x1b[B" : KEY_DOWN,
    b"\x1b[D" : KEY_LEFT,
    b"\x1b[C" : KEY_RIGHT,
    b"\x1b[H" : KEY_HOME, ## in Linux Terminal
    b"\x1bOH" : KEY_HOME, ## Picocom, Minicom
    b"\x1b[1~": KEY_HOME, ## Putty
    b"\x1b[F" : KEY_END,  ## Linux Terminal
    b"\x1bOF" : KEY_END,  ## Picocom, Minicom
    b"\x1b[4~": KEY_END,  ## Putty
    b"\x1b[5~": KEY_PGUP,
    b"\x1b[6~": KEY_PGDN,
    b"\x03"   : KEY_QUIT, ## Ctrl-C
    b"\r"     : KEY_ENTER,
    b"\x7f"   : KEY_BACKSPACE, ## Ctrl-? (127)
    b"\x1b[3~": KEY_DELETE,
    b"\x1b[Z" : KEY_BACKTAB, ## Shift Tab
    b"\x1b[3;5~": KEY_YANK, ## Ctrl-Del
#ifndef BASIC
## keys mapped onto themselves
    b"\x11"   : KEY_QUIT, ## Ctrl-Q
    b"\n"     : KEY_ENTER,
    b"\x08"   : KEY_BACKSPACE,
    b"\x13"   : KEY_WRITE,  ## Ctrl-S
    b"\x06"   : KEY_FIND, ## Ctrl-F
    b"\x0e"   : KEY_FIND_AGAIN, ## Ctrl-N
    b"\x07"   : KEY_GOTO, ##  Ctrl-G
    b"\x05"   : KEY_REDRAW, ## Ctrl-E
    b"\x1a"   : KEY_UNDO, ## Ctrl-Z
    b"\x09"   : KEY_TAB,
    b"\x15"   : KEY_BACKTAB, ## Ctrl-U
    b"\x12"   : KEY_REPLC, ## Ctrl-R
    b"\x18"   : KEY_YANK, ## Ctrl-X
    b"\x16"   : KEY_ZAP, ## Ctrl-V
    b"\x04"   : KEY_DUP, ## Ctrl-D
    b"\x0c"   : KEY_MARK, ## Ctrl-L
##
    b"\x1b[M" : KEY_MOUSE,
    b"\x01"   : KEY_TOGGLE, ## Ctrl-A
    b"\x14"   : KEY_FIRST, ## Ctrl-T
    b"\x02"   : KEY_LAST,  ## Ctrl-B
    b"\x1b[1;5H": KEY_FIRST,
    b"\x1b[1;5F": KEY_LAST,
    b"\x0f"   : KEY_GET, ## Ctrl-O
#endif
    }

    def __init__(self, tab_size, undo_limit):
        self.top_line = self.cur_line = self.row = self.col = self.tcol = self.margin = 0
        self.tab_size = tab_size
        self.changed = " "
        self.message = self.find_pattern = ""
        self.fname = None
        self.content = [""]
        self.undo = []
        self.undo_limit = max(undo_limit, 0)
        self.undo_zero = 0
        self.case = "n"
        self.autoindent = "y"
        self.yank_buffer = []
        self.mark = -1
        self.check_mark = -1
        self.mark_tab = False
        self.msg_find = "Find: "
#ifndef BASIC
        self.replc_pattern = ""
        self.write_tabs = "n"
#endif
#ifdef LINUX
    if sys.platform in ("linux", "darwin"):
        def wr(self,s):
            if isinstance(s, str):
                s = bytes(s, "utf-8")
            os.write(1, s)

        def rd(self):
            while True:
                try: ## WINCH causes interrupt
                    return os.read(self.sdev,1)
                except:
                    if Editor.winch: ## simulate REDRAW key
                        Editor.winch = False
                        return b'\x05'

        def init_tty(self, device, baud):
            self.org_termios = termios.tcgetattr(device)
            tty.setraw(device)
            self.sdev = device
            if sys.implementation.name == "cpython":
                signal.signal(signal.SIGWINCH, Editor.signal_handler)

        def deinit_tty(self):
            import termios
            termios.tcsetattr(self.sdev, termios.TCSANOW, self.org_termios)

        @staticmethod
        def signal_handler(sig, frame):
            signal.signal(signal.SIGWINCH, signal.SIG_IGN)
            Editor.winch = True
            return True
#endif
#ifdef PYBOARD
    if sys.platform == "pyboard":
        def wr(self,s):
            ns = 0
            while ns < len(s): # complicated but needed, since USB_VCP.write() has issues
                res = self.serialcomm.write(s[ns:])
                if res != None:
                    ns += res

        def rd(self):
            while not self.serialcomm.any():
                pass
            return self.serialcomm.read(1)

        def init_tty(self, device, baud):
            import pyb
            self.sdev = device
            if self.sdev:
                self.serialcomm = pyb.UART(device, baud)
            else:
                self.serialcomm = pyb.USB_VCP()
                self.serialcomm.setinterrupt(-1)

        def deinit_tty(self):
            if not self.sdev:
                self.serialcomm.setinterrupt(3)
#endif
#ifdef WIPY
    if sys.platform == "WiPy":
        def wr(self, s):
            sys.stdout.write(s)

        def rd(self):
            while True:
                try:
                    ch = sys.stdin.read(1)
                    if ch != "\x00":
                        return ch.encode()
                except: pass

        def init_tty(self, device, baud):
            pass

        def deinit_tty(self):
            pass
#endif
    def goto(self, row, col):
        self.wr("\x1b[{};{}H".format(row + 1, col + 1))

    def clear_to_eol(self):
        self.wr(b"\x1b[0K")

    def cursor(self, onoff):
        if onoff:
            self.wr(b"\x1b[?25h")
        else:
            self.wr(b"\x1b[?25l")

    def hilite(self, mode):
        if mode == 1:
            self.wr(b"\x1b[1m")
        if mode == 2:
            self.wr(b"\x1b[7m")
        else:
            self.wr(b"\x1b[0m")

#ifndef BASIC
    def mouse_reporting(self, onoff):
        if onoff:
            self.wr('\x1b[?9h') ## enable mouse reporting
        else:
            self.wr('\x1b[?9l') ## disable mouse reporting
#endif
    def scroll_region(self, stop):
        if stop:
            self.wr('\x1b[1;{}r'.format(stop)) ## enable partial scrolling
        else:
            self.wr('\x1b[r') ## full scrolling

    def scroll_up(self, scrolling):
        self.scrbuf[scrolling:] = self.scrbuf[:-scrolling]
        self.scrbuf[:scrolling] = [''] * scrolling
        self.goto(0, 0)
        self.wr("\x1bM" * scrolling)

    def scroll_down(self, scrolling):
        self.scrbuf[:-scrolling] = self.scrbuf[scrolling:]
        self.scrbuf[-scrolling:] = [''] * scrolling
        self.goto(self.height - 1, 0)
        self.wr("\x1bD " * scrolling)

    def set_screen_parms(self):
        self.cursor(False)
        self.wr('\x1b[999;999H\x1b[6n')
        pos = b''
        char = self.rd() ## expect ESC[yyy;xxxR
        while char != b'R':
            pos += char
            char = self.rd()
        (self.height, self.width) = [int(i, 10) for i in pos[2:].split(b';')]
        self.height -= 1
        self.scrbuf = ["\x01"] * self.height ## force delete
        self.scroll_region(self.height)

    def get_input(self):  ## read from interface/keyboard one byte each and match against function keys
        while True:
            in_buffer = self.rd()
            if in_buffer == b'\x1b': ## starting with ESC, must be fct
                while True:
                    in_buffer += self.rd()
                    c = chr(in_buffer[-1])
                    if c == '~' or (c.isalpha() and c != 'O'):
                        break
            if in_buffer in self.KEYMAP:
                c = self.KEYMAP[in_buffer]
                if c != KEY_MOUSE:
                    return c
#ifndef BASIC
                else: ## special for mice
                    mf = ord((self.rd())) ## read 3 more chars
                    self.mouse_x = ord(self.rd()) - 33
                    self.mouse_y = ord(self.rd()) - 33
                    if mf == 0x61:
                        return KEY_SCRLDN
                    elif mf == 0x60:
                        return KEY_SCRLUP
                    else:
                        return KEY_MOUSE ## do nothing but set the cursor
#endif
            elif len(in_buffer) == 1: ## but only if a single char
                return in_buffer[0]

    def display_window(self): ## Update window and status line
## Force cur_line and col to be in the reasonable bounds
        self.cur_line = min(self.total_lines - 1, max(self.cur_line, 0))
        self.col = max(0, min(self.tcol, len(self.content[self.cur_line])))
## Check if Column is out of view, and align margin if needed
        if self.col >= self.width + self.margin:
            self.margin = self.col - self.width + (self.width >> 2)
        elif self.col < self.margin:
            self.margin = max(self.col - (self.width >> 2), 0)
## if cur_line is out of view, align top_line to the given row
        if not (self.top_line <= self.cur_line < self.top_line + self.height): # Visible?
            self.top_line = max(self.cur_line - self.row, 0)
## in any case, align row to top_line and cur_line
        self.row = self.cur_line - self.top_line
## update_screen
        self.cursor(False)
        i = self.top_line
        for c in range(self.height):
            if i == self.total_lines: ## at empty bottom screen part
                if self.scrbuf[c] != '':
                    self.goto(c, 0)
                    self.clear_to_eol()
                    self.scrbuf[c] = ''
            else:
                l = self.content[i][self.margin:self.margin + self.width]
                if l != self.scrbuf[c] or i == self.check_mark: ## line changed, print it
                    self.goto(c, 0)
                    if i == self.mark:
                        self.hilite(2)
                        self.wr(l)
                        if l == "": self.wr(' ') ## add a spaces
                        self.hilite(0)
                    else:
                        self.wr(l)
                        if i == self.check_mark: self.check_mark = -1
                    if len(l) < self.width:
                        self.clear_to_eol()
                    self.scrbuf[c] = l
                i += 1
## display Status-Line
        self.goto(self.height, 0)
        self.hilite(1)
        self.wr("[{}] {} Row: {} Col: {}  {}".format(
            self.total_lines, self.changed, self.cur_line + 1,
            self.col + 1, self.message[:self.width - 25]))
        self.hilite(0)
        self.clear_to_eol() ## once moved up for mate/xfce4-terminal issue with scroll region
        self.goto(self.row, self.col - self.margin)
        self.cursor(True)

    def spaces(self, line, pos = None): ## count spaces
        if pos == None: ## at line start
            return len(line) - len(line.lstrip(" "))
        else: ## left to pos
            return len(line[:pos]) - len(line[:pos].rstrip(" "))

    def line_range(self):
        if self.mark < 0:
            return (self.cur_line, self.cur_line + 1)
        else:
            if self.mark < self.cur_line:
                return (self.mark, self.cur_line + 1)
            else:
                return (self.cur_line, self.mark + 1)

    def line_edit(self, prompt, default):  ## simple one: only 4 fcts
        self.goto(self.height, 0)
        self.hilite(1)
        self.wr(prompt)
        self.wr(default)
        self.clear_to_eol()
        res = default
        while True:
            key = self.get_input()  ## Get Char of Fct.
            if key in (KEY_ENTER, KEY_TAB): ## Finis
                self.hilite(0)
                return res
            elif key == KEY_QUIT: ## Abort
                self.hilite(0)
                return None
            elif key == KEY_BACKSPACE: ## Backspace
                if (len(res) > 0):
                    res = res[:len(res)-1]
                    self.wr('\b \b')
            elif key == KEY_DELETE: ## Delete prev. Entry
                self.wr('\b \b' * len(res))
                res = ''
            elif key >= 0x20: ## char to be added at the end
                if len(prompt) + len(res) < self.width - 2:
                    res += chr(key)
                    self.wr(chr(key))

    def find_in_file(self, pattern, pos, end):
        self.find_pattern = pattern # remember it
        if self.case != "y":
            pattern = pattern.lower()
        spos = pos
        for line in range(self.cur_line, end):
            if self.case != "y":
                match = self.content[line][spos:].lower().find(pattern)
#ifndef BASIC
            else:
                match = self.content[line][spos:].find(pattern)
#endif
            if match >= 0:
                break
            spos = 0
        else:
            self.message = "No match: " + pattern
            return 0
        self.tcol = match + spos
        self.cur_line = line
        return len(pattern)

    def cursor_down(self):
        if self.cur_line < self.total_lines - 1:
            self.cur_line += 1
            if self.cur_line == self.top_line + self.height:
                self.scroll_down(1)

    def handle_cursor_keys(self, key): ## keys which move, sanity checks later
        if key == KEY_DOWN:
            self.cursor_down()
        elif key == KEY_UP:
            if self.cur_line > 0:
                self.cur_line -= 1
                if self.cur_line < self.top_line:
                    self.scroll_up(1)
        elif key == KEY_LEFT:
#ifndef BASIC
            if self.col == 0 and self.cur_line > 0:
                self.cur_line -= 1
                self.col = len(self.content[self.cur_line])
                if self.cur_line < self.top_line:
                    self.scroll_up(1)
            else:
#endif
                self.tcol = self.col - 1
        elif key == KEY_RIGHT:
#ifndef BASIC
            if self.col >= len(self.content[self.cur_line]) and self.cur_line < self.total_lines - 1:
                self.cursor_down()
                self.tcol = 0
            else:
#endif
                self.tcol = self.col + 1
        elif key == KEY_HOME:
            self.tcol = self.spaces(self.content[self.cur_line]) if self.col == 0 else 0
        elif key == KEY_END:
            self.tcol = len(self.content[self.cur_line])
        elif key == KEY_PGUP:
            self.cur_line -= self.height
        elif key == KEY_PGDN:
            self.cur_line += self.height
        elif key == KEY_FIND:
            pat = self.line_edit(self.msg_find, self.find_pattern)
            if pat:
                self.find_in_file(pat, self.col, self.total_lines)
                self.row = self.height >> 1
        elif key == KEY_FIND_AGAIN:
            if self.find_pattern:
                self.find_in_file(self.find_pattern, self.col + 1, self.total_lines)
                self.row = self.height >> 1
        elif key == KEY_GOTO: ## goto line
            line = self.line_edit("Goto Line: ", "")
            if line:
                try:
                    self.cur_line = int(line) - 1
                    self.row = self.height >> 1
                except:
                    pass
#ifndef BASIC
        elif key == KEY_MOUSE: ## Set Cursor
            if self.mouse_y < self.height:
                self.tcol = self.mouse_x + self.margin
                self.cur_line = self.mouse_y + self.top_line
        elif key == KEY_SCRLUP: ##
            if self.top_line > 0:
                self.top_line = max(self.top_line - 3, 0)
                self.cur_line = min(self.cur_line, self.top_line + self.height - 1)
                self.scroll_up(3)
        elif key == KEY_SCRLDN: ##
            if self.top_line + self.height < self.total_lines:
                self.top_line = min(self.top_line + 3, self.total_lines - 1)
                self.cur_line = max(self.cur_line, self.top_line)
                self.scroll_down(3)
        elif key == KEY_TOGGLE: ## Toggle Autoindent/Statusline/Search case
            pat = self.line_edit("Case Sensitive Search {}, Autoindent {}, Tab Size {}, Write Tabs {}: ".format(self.case, self.autoindent, self.tab_size, self.write_tabs), "")
            try:
                res =  [i.strip().lower() for i in pat.split(",")]
                if res[0]: self.case       = 'y' if res[0][0] == 'y' else 'n'
                if res[1]: self.autoindent = 'y' if res[1][0] == 'y' else 'n'
                if res[2]:
                    try: self.tab_size = int(res[2])
                    except: pass
                if res[3]: self.write_tabs = 'y' if res[3][0] == 'y' else 'n'
            except:
                pass
        elif key == KEY_FIRST: ## first line
            self.cur_line = 0
        elif key == KEY_LAST: ## last line
            self.cur_line = self.total_lines - 1
            self.row = self.height - 1 ## will be fixed if required
#endif
        else:
            return False
        return True

    def undo_add(self, lnum, text, key, span = 1):
        self.changed = '*'
        if self.undo_limit > 0 and (
           len(self.undo) == 0 or key == 0 or self.undo[-1][3] != key or self.undo[-1][0] != lnum):
            if len(self.undo) >= self.undo_limit: ## drop oldest undo
                del self.undo[0]
                self.undo_zero -= 1
            self.undo.append((lnum, span, text, key, self.col))

    def handle_edit_key(self, key): ## keys which change content
        l = self.content[self.cur_line]
        if key == KEY_ENTER:
            self.undo_add(self.cur_line, [l], 0, 2)
            self.content[self.cur_line] = l[:self.col]
            ni = 0
            if self.autoindent == "y": ## Autoindent
                ni = min(self.spaces(l), self.col)  ## query indentation
                r = l.partition("\x23")[0].rstrip() ## \x23 == #
                if r and r[-1] == ':' and self.col >= len(r): ## look for : as the last non-space before comment
                    ni += self.tab_size
            self.cur_line += 1
            self.content[self.cur_line:self.cur_line] = [' ' * ni + l[self.col:]]
            self.total_lines += 1
            self.tcol = ni
        elif key == KEY_BACKSPACE:
            if self.col > 0:
                self.undo_add(self.cur_line, [l], KEY_BACKSPACE)
                self.content[self.cur_line] = l[:self.col - 1] + l[self.col:]
                self.tcol = self.col - 1
#ifndef BASIC
            elif self.cur_line > 0: # at the start of a line, but not the first
                self.undo_add(self.cur_line - 1, [self.content[self.cur_line - 1], l], 0)
                self.tcol = len(self.content[self.cur_line - 1])
                self.content[self.cur_line - 1] += self.content.pop(self.cur_line)
                self.cur_line -= 1
                self.total_lines -= 1
#endif
        elif key == KEY_DELETE:
            if self.col < len(l):
                self.undo_add(self.cur_line, [l], KEY_DELETE)
                self.content[self.cur_line] = l[:self.col] + l[self.col + 1:]
            elif (self.cur_line + 1) < self.total_lines: ## test for last line
                self.undo_add(self.cur_line, [l, self.content[self.cur_line + 1]], 0)
                self.content[self.cur_line] = l + self.content.pop(self.cur_line + 1)
                self.total_lines -= 1
        elif key == KEY_TAB:
            if self.mark >= 0:
                self.mark_tab = True
                lrange = self.line_range()
                self.undo_add(lrange[0], self.content[lrange[0]:lrange[1]], KEY_INDENT, lrange[1] - lrange[0]) ## undo replaces
                for i in range(lrange[0],lrange[1]):
                    if len(self.content[i]) > 0:
                        self.content[i] = ' ' * (self.tab_size - self.spaces(self.content[i]) % self.tab_size) + self.content[i]
            else:
                self.undo_add(self.cur_line, [l], KEY_TAB)
                ni = self.tab_size - self.col % self.tab_size ## determine spaces to add
                self.content[self.cur_line] = l[:self.col] + ' ' * ni + l[self.col:]
                self.tcol = self.col + ni
        elif key == KEY_BACKTAB:
            if self.mark >= 0:
                self.mark_tab = True
                lrange = self.line_range()
                self.undo_add(lrange[0], self.content[lrange[0]:lrange[1]], KEY_INDENT, lrange[1] - lrange[0]) ## undo replaces
                for i in range(lrange[0],lrange[1]):
                    ns = self.spaces(self.content[i])
                    if ns > 0:
                        self.content[i] = self.content[i][(ns - 1) % self.tab_size + 1:]
            else:
                ni = min((self.col - 1) % self.tab_size + 1, self.spaces(l, self.col)) ## determine spaces to drop
                if ni > 0:
                    self.undo_add(self.cur_line, [l], KEY_BACKTAB)
                    self.content[self.cur_line] = l[:self.col - ni] + l[self.col:]
                    self.tcol = self.col - ni
#ifndef BASIC
        elif key == KEY_REPLC:
            count = 0
            pat = self.line_edit(self.msg_find, self.find_pattern)
            if pat:
                rpat = self.line_edit("Replace with: ", self.replc_pattern)
                if rpat != None:
                    self.replc_pattern = rpat
                    q = ''
                    if self.mark >= 0: ## Replace in Marked area
                        lrange = self.line_range()
                        self.cur_line = lrange[0]
                    else:
                        lrange = (self.cur_line, self.total_lines)
                    self.tcol = self.col
                    while True:
                        ni = self.find_in_file(pat, self.tcol, lrange[1])
                        if ni:
                            if q != 'a':
                                self.message = "Replace (yes/No/all/quit) ? "
                                self.display_window()
                                key = self.get_input()  ## Get Char of Fct.
                                q = chr(key).lower()
                            if q == 'q' or key == KEY_QUIT:
                                break
                            elif q in ('a','y'):
                                self.undo_add(self.cur_line, [self.content[self.cur_line]], 0)
                                self.content[self.cur_line] = self.content[self.cur_line][:self.tcol] + rpat + self.content[self.cur_line][self.tcol + ni:]
                                self.tcol += len(rpat)
                                count += 1
                            else: ## everything else is no
                                self.tcol += 1
                        else:
                            break
                    self.message = "'{}' replaced {} times".format(pat, count)
        elif key == KEY_GET:
            fname = self.line_edit("Insert File: ", "")
            if fname:
                (content, self.message) = self.get_file(fname)
                if content:
                    self.undo_add(self.cur_line, None, 0, -len(content))
                    self.content[self.cur_line:self.cur_line] = content
                    self.total_lines = len(self.content)
#endif
        elif key == KEY_MARK:
            if self.mark < 0:
                self.mark = self.check_mark = self.cur_line
                self.mark_tab = False
            else:
                self.mark = -1
        elif key == KEY_YANK:  # delete line or line(s) into buffer
            lrange = self.line_range()
            self.yank_buffer = self.content[lrange[0]:lrange[1]]
            self.undo_add(lrange[0], self.content[lrange[0]:lrange[1]], 0, 0) ## undo inserts
            del self.content[lrange[0]:lrange[1]]
            if self.content == []: ## if all was wiped
                self.content = [""]
            self.total_lines = len(self.content)
            self.cur_line = lrange[0]
            self.mark = -1 ## unset line mark
        elif key == KEY_DUP:  # copy line(s) into buffer
            lrange = self.line_range()
            self.yank_buffer = self.content[lrange[0]:lrange[1]]
            self.mark = -1 ## unset line mark
        elif key == KEY_ZAP: ## insert buffer
            if self.yank_buffer:
                self.undo_add(self.cur_line, None, 0, -len(self.yank_buffer))
                self.content[self.cur_line:self.cur_line] = self.yank_buffer # insert lines
                self.total_lines += len(self.yank_buffer)
        elif key == KEY_WRITE:
            if False: pass
#ifndef BASIC
            elif self.mark >= 0:
                fname = self.line_edit("Save Mark: ", "")
                lrange = self.line_range()
                self.mark = -1
#endif
            else:
                fname = self.fname
                if fname == None:
                    fname = ""
                fname = self.line_edit("Save File: ", fname)
                lrange = (0, self.total_lines)
            if fname:
                try:
                    with open(fname, "w") as f:
                        for l in self.content[lrange[0]:lrange[1]]:
#ifndef BASIC
                            if self.write_tabs == 'y':
                                f.write(self.packtabs(l) + '\n')
                            else:
#endif
                                f.write(l + '\n')
                    self.changed = ' ' ## clear change flag
                    self.undo_zero = len(self.undo) ## remember state
                    self.fname = fname ## remember (new) name
                except Exception as err:
                    self.message = 'Could not save {}, {!r}'.format(fname, err)
        elif key == KEY_UNDO:
            if len(self.undo) > 0:
                action = self.undo.pop(-1) ## get action from stack
                if action[3] != KEY_INDENT:
                    self.cur_line = action[0]
                    self.tcol = action[4]
                if action[1] >= 0: ## insert or replace line
                    if action[0] < self.total_lines:
                        self.content[action[0]:action[0] + action[1]] = action[2] # insert lines
                    else:
                        self.content += action[2]
                else: ## delete lines
                    del self.content[action[0]:action[0] - action[1]]
                self.total_lines = len(self.content) ## brute force
                self.changed = ' ' if len(self.undo) == self.undo_zero else '*'
        elif key >= 0x20: ## character to be added
            self.undo_add(self.cur_line, [l], 0x20 if key == 0x20 else 0x41)
            self.content[self.cur_line] = l[:self.col] + chr(key) + l[self.col:]
            self.tcol = self.col + 1

    def edit_loop(self): ## main editing loop

        if len(self.content) == 0: ## check for empty content
            self.content = [""]
        self.total_lines = len(self.content)
        self.set_screen_parms()
#ifndef BASIC
        self.mouse_reporting(True) ## enable mouse reporting
#endif

        while True:
            self.display_window()  ## Update & display window
            key = self.get_input()  ## Get Char of Fct-key code
            self.message = '' ## clear message
            if self.mark_tab and key != KEY_TAB and key != KEY_BACKTAB:
                self.mark = -1

            if key == KEY_QUIT:
                if self.changed != ' ':
                    res = self.line_edit("Content changed! Quit without saving (y/N)? ", "N")
                    if not res or res[0].upper() != 'Y':
                        continue
## Do not leave cursor in the middle of screen
#ifndef BASIC
                self.mouse_reporting(False) ## disable mouse reporting, enable scrolling
#endif
                self.scroll_region(0)
                self.goto(self.height, 0)
                self.clear_to_eol()
                return None
            elif key == KEY_REDRAW:
                self.set_screen_parms()
                self.row = min(self.height - 1, self.row)
#ifdef LINUX
                if sys.platform in ("linux", "darwin") and sys.implementation.name == "cpython":
                    signal.signal(signal.SIGWINCH, Editor.signal_handler)
#endif
                if sys.implementation.name == "micropython":
                    gc.collect()
                    self.message = "{} Bytes Memory available".format(gc.mem_free())
            elif  self.handle_cursor_keys(key):
                pass
            else: self.handle_edit_key(key)

## packtabs: replace sequence of space by tab
#ifndef BASIC
    def packtabs(self, s):
        from _io import StringIO
        sb = StringIO()
        for i in range(0, len(s), 8):
            c = s[i:i + 8]
            cr = c.rstrip(" ")
            if c != cr: ## Spaces at the end of a section
                sb.write(cr + "\t") ## replace by tab
            else:
                sb.write(c)
        return sb.getvalue()
#endif
    def get_file(self, fname):
        try:
#ifdef LINUX
            if sys.implementation.name == "cpython":
                with open(fname, errors="ignore") as f:
                    content = f.readlines()
            else:
#endif
                with open(fname) as f:
                    content = f.readlines()
        except Exception as err:
            message = 'Could not load {}, {!r}'.format(fname, err)
            return (None, message)
        for i in range(len(content)):  ## strip and convert
            content[i] = expandtabs(content[i].rstrip('\r\n\t '))
        return (content, "")
## expandtabs: hopefully sometimes replaced by the built-in function
def expandtabs(s):
    from _io import StringIO
    if '\t' in s:
        sb = StringIO()
        pos = 0
        for c in s:
            if c == '\t': ## tab is seen
                sb.write(" " * (8 - pos % 8)) ## replace by space
                pos += 8 - pos % 8
            else:
                sb.write(c)
                pos += 1
        return sb.getvalue()
    else:
        return s

def pye(content = None, tab_size = 4, undo = 50, device = 0, baud = 115200):
## prepare content
    gc.collect() ## all (memory) is mine
    e = Editor(tab_size, undo)
    if type(content) == str and content: ## String = non-empty Filename
        e.fname = content
        (e.content, e.message) = e.get_file(e.fname)
        if e.content == None:  ## Error reading file
            print (e.message)
            return
    elif type(content) == list and len(content) > 0 and type(content[0]) == str:
        ## non-empty list of strings -> edit
        e.content = content
## edit
    e.init_tty(device, baud)
    e.edit_loop()
    e.deinit_tty()
## close
    return e.content if (e.fname == None) else e.fname

#ifdef LINUX
if __name__ == "__main__":
    if sys.platform in ("linux", "darwin"):
        import stat
        fd_tty = 0
        if len(sys.argv) > 1:
            name = sys.argv[1]
        else:
            name = ""
            if sys.implementation.name == "cpython":
                mode = os.fstat(0).st_mode
                if stat.S_ISFIFO(mode) or stat.S_ISREG(mode):
                    name = sys.stdin.readlines()
                    os.close(0) ## close and repopen /dev/tty
                    fd_tty = os.open("/dev/tty", os.O_RDONLY) ## memorized, if new fd
                    for i in range(len(name)):  ## strip and convert
                        name[i] = expandtabs(name[i].rstrip('\r\n\t '))
        pye(name, undo = 500, device=fd_tty)
    else:
        print ("\nSorry, this OS is not supported (yet)")
#endif