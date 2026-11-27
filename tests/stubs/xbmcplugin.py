ITEMS = []; RESOLVED = []; ENDED = []
for i, n in enumerate(['SORT_METHOD_UNSORTED','SORT_METHOD_LABEL','SORT_METHOD_VIDEO_YEAR','SORT_METHOD_VIDEO_RATING','SORT_METHOD_EPISODE']):
    globals()[n] = i
def addDirectoryItem(h, url, li, folder=False, total=0): ITEMS.append((url, li, folder))
def endOfDirectory(h, succeeded=True, cacheToDisc=True, **k): ENDED.append(succeeded)
def setContent(h, c): pass
def addSortMethod(h, s): pass
def setResolvedUrl(h, ok, li): RESOLVED.append((ok, li))
