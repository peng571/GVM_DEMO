import sys
import msvcrt
from wcwidth import wcswidth
from collections import namedtuple

Ratain = namedtuple('Ratain', '')
Anwser = namedtuple('Anwser', 'value')
    
class NumberCommand:
    def __init__(self, begin=0, end=9):
        assert end >= begin
        self.digit, _end = 0, end
        while(_end != 0):
            self.digit += 1
            _end = _end // 10
        self.begin, self.end = begin, end
        self.prompt = '{{:0{0}d}}-{{:0{0}d}}'.format(self.digit).format(begin, end)
        
    def __call__(self, buf):
        vaildate = all(ord(c) in range(ord('0'), ord('9')+1) for c in buf)
        if len(buf) < self.digit:
            if vaildate:
                return Ratain()
            else:
                return None
        if vaildate and int(buf) in range(self.begin, self.end+1):
            return Anwser(int(buf))
    
class OneCharCommand:
    def __init__(self, char, value=None, help=''):
        self.char = char
        self.value = value or char
        display = char
        self.prompt = display + ('='+help if help else '')
        
    def __call__(self, buf):
        if buf == self.char:
            return Anwser(self.value)
            
class Inputer:

    def __init__(self):
        self.buf = ''
        self.commands = [NumberCommand(begin=1, end=100), OneCharCommand('c', help='幫助'), OneCharCommand('[enter]', 'enter')]
        self.showed = ''
        self.showed_awnser = ''
        self.last_status = ' '
        
    def clear(self):
        counts = range(wcswidth(self.showed))
        for i in counts:
            msvcrt.putwch('\b')
        for i in counts:
            msvcrt.putwch(' ')
        for i in counts:
            msvcrt.putwch('\b')
        self.showed = ''
        
    def print_(self, string):
        self.clear()
        sys.stdout.write(string + '\n')
        
    def tick(self):
        self.clear()
        
        input_area = self.showed_awnser + '_' * (12-wcswidth(self.showed_awnser)) + self.last_status
        for c in input_area:
            msvcrt.putwch(c)
        self.showed += input_area
        prompt = ' ({})'.format(' '.join(cmd.prompt for cmd in self.commands))
        for c in prompt:
            msvcrt.putwch(c)
        self.showed += prompt
        
        c = msvcrt.getwch()
        if c == '\r':
            c = '[enter]'
        if c == '\003':
            raise KeyboardInterrupt
        if c == '\b':
            self.buf = self.buf[:-1]
        else:
            self.buf = self.buf + c
        
        status = None
        for cmd in self.commands:
            result = cmd(self.buf)
            if isinstance(result, Ratain) and not isinstance(status, Anwser):
                status = result
            elif isinstance(result, Anwser):
                status = result
                break
        
        if isinstance(status, Ratain):
            self.showed_awnser = self.buf
            self.last_status = ' '
        elif isinstance(status, Anwser):
            self.showed_awnser = self.buf
            self.buf = ''
            self.last_status = '*'
            return status.value
        else:
            self.showed_awnser = ''
            self.buf = ''
            self.last_status = '!'
        
if __name__ == '__main__':
    import time
    ip = Inputer()
    while 1:
        awnser = ip.tick()
        if awnser:
            ip.print_(str(awnser))
            
        #if awnser:
        #    break
    
    