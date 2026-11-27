PROPS = {}; DIALOGS = []
class InfoTag:
    def __init__(self): self.d = {}
    def __getattr__(self, n):
        if n.startswith('set'):
            return lambda *v: self.d.__setitem__(n[3:].lower(), v[0] if len(v) == 1 else v)
        raise AttributeError(n)
class ListItem:
    def __init__(self, label='', path='', offscreen=False):
        self.label, self.path, self.props, self.art, self.tag, self.mime, self.ctx = label, path, {}, {}, InfoTag(), None, []
    def setArt(self, a): self.art.update(a)
    def setProperty(self, k, v): self.props[k] = v
    def getVideoInfoTag(self): return self.tag
    def addContextMenuItems(self, c): self.ctx += c
    def setMimeType(self, m): self.mime = m
    def setContentLookup(self, b): pass
    def setPath(self, p): self.path = p
class Window:
    def __init__(self, id): pass
    def getProperty(self, k): return PROPS.get(k, '')
    def setProperty(self, k, v): PROPS[k] = v
    def clearProperty(self, k): PROPS.pop(k, None)
class Dialog:
    INPUT = 'beach'
    def notification(self, *a): DIALOGS.append(('notify',) + a)
    def ok(self, *a): DIALOGS.append(('ok',) + a)
    def textviewer(self, *a): DIALOGS.append(('text',) + a)
    def input(self, *a): return Dialog.INPUT
class DialogProgress:
    def create(self, *a): pass
    def update(self, *a): pass
    def iscanceled(self): return False
    def close(self): pass
class DialogProgressBG(DialogProgress): pass
def _getlabel2(self): return getattr(self, 'l2', '')
ListItem.__init__orig = ListItem.__init__
def _li_init(self, label='', label2='', path='', offscreen=False):
    ListItem.__init__orig(self, label, path, offscreen); self.l2 = label2
ListItem.__init__ = _li_init
ListItem.setLabel2 = lambda self, v: setattr(self, 'l2', v)
ListItem.getLabel2 = _getlabel2
ListItem.getProperty = lambda self, k: self.props.get(k, '')
class Action:
    def __init__(self, i): self.i = i
    def getId(self): return self.i
class Control:
    def __init__(self): self.items = []; self.sel = 0; self.width = None
    def reset(self): self.items = []; self.sel = 0
    def addItems(self, items): self.items += items
    def selectItem(self, i): self.sel = i
    def getSelectedPosition(self): return self.sel if self.items else -1
    def size(self): return len(self.items)
    def getListItem(self, i): return self.items[i]
    def setWidth(self, w): self.width = w
class WindowXML:
    def __new__(cls, *a, **k): o = object.__new__(cls); o._ctl = {}; o._props = {}; o._focus = None; o.closed = False; return o
    def getControl(self, i): return self._ctl.setdefault(i, Control())
    def setProperty(self, k, v): self._props[k] = v
    def getProperty(self, k): return self._props.get(k, "")
    def setFocusId(self, i): self._focus = i
    def close(self): self.closed = True
    def doModal(self): self.onInit()
Dialog.CTX = 0
Dialog.contextmenu = lambda self, opts: (DIALOGS.append(('ctx', opts)), Dialog.CTX)[1]
WindowXML.getFocusId = lambda self: self._focus
Dialog.ANSWERS = []
def _next(self, *a, **k):
    DIALOGS.append(('ask',) + a[:1]); return Dialog.ANSWERS.pop(0)
Dialog.select = _next; Dialog.multiselect = _next; Dialog.yesno = _next
Dialog.input = lambda self, *a, **k: Dialog.ANSWERS.pop(0) if Dialog.ANSWERS else Dialog.INPUT
ListItem.setLabel = lambda self, v: setattr(self, 'label', v)
_NEXT_ID = [3000]
class ControlButton(Control):
    def __init__(self, x, y, w, h, label, **kw):
        Control.__init__(self); _NEXT_ID[0] += 1; self._id = _NEXT_ID[0]
        self.x, self.y, self.w, self.h, self.label, self.kw = x, y, w, h, label, kw
    def getId(self): return self._id
Control.setImage = lambda self, v: setattr(self, 'image', v)
Control.setLabel = lambda self, v: setattr(self, 'label', v)
Control.setPosition = lambda self, x, y: setattr(self, 'pos', (x, y))
Control.setVisible = lambda self, v: setattr(self, 'visible', v)
def _add(self, cs):
    self._added = getattr(self, '_added', []) + list(cs)
def _remove(self, cs):
    ids = {c.getId() for c in cs}; self._added = [c for c in getattr(self, '_added', []) if c.getId() not in ids]
WindowXML.addControls = _add
WindowXML.removeControls = _remove
def _setFocus(self, c): self._focus = c.getId()
WindowXML.setFocus = _setFocus
OVERLAYS = []
class WindowXMLDialog(WindowXML):
    def show(self):
        self.shown = True; OVERLAYS.append(self); self.onInit()
    def close(self): self.closed = True
Dialog.BROWSE = ''
Dialog.NUMERIC = ''
Dialog.browse = lambda self, *a, **k: Dialog.BROWSE
Dialog.numeric = lambda self, *a, **k: Dialog.NUMERIC
