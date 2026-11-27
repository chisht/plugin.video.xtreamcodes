import os
def translatePath(p): return p
class File:
    def __init__(self, path, mode='r'): self.f = open(path, mode)
    def read(self): return self.f.read()
    def write(self, s): self.f.write(s)
    def close(self): self.f.close()
