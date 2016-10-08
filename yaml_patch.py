import yaml

# monkey patch to Mark
from yaml import Mark as _Mark
from wcwidth import wcswidth
class Mark(_Mark):
    def get_snippet(self, indent=4, max_length=75):
        if self.buffer is None:
            return None
        head = ''
        start = self.pointer
        while start > 0 and self.buffer[start-1] not in '\0\r\n\x85\u2028\u2029':
            start -= 1
            if wcswidth(self.buffer[start:self.pointer]) > max_length/2-1:
                head = ' ... '
                start += 5
                break
        tail = ''
        end = self.pointer
        while end < len(self.buffer) and self.buffer[end] not in '\0\r\n\x85\u2028\u2029':
            end += 1
            if wcswidth(self.buffer[self.pointer:end]) > max_length/2-1:
                tail = ' ... '
                end -= 5
                break
        snippet = self.buffer[start:end]
        return ' '*indent + head + snippet + tail + '\n'  \
                + ' '*(indent+wcswidth(self.buffer[start:self.pointer])+len(head)) + '^'
                
yaml.Mark = Mark
yaml.reader.Mark = Mark


from yaml.reader import Reader
from yaml.scanner import Scanner
from yaml.parser import Parser
from yaml.composer import Composer
from yaml.constructor import Constructor
from yaml.resolver import Resolver

# monkey patch to Loader
class ProcessLoader(yaml.Loader):
    def __init__(self, filename):
        self.filename = filename
        with open(self.filename, encoding='utf-8') as fp:
            stream = self.preprocess(fp.read())
        Reader.__init__(self, stream)
        self.name = self.filename
        
        Scanner.__init__(self)
        Parser.__init__(self)
        Composer.__init__(self)
        Constructor.__init__(self)
        Resolver.__init__(self)
        
    def preprocess(self, text):
        elements = []
        last_i = None
        multiline_mode = False
        for i, line in enumerate(text.split('\n')):
            # comment
            if line.strip()[:2] == '--':
                line = '# ' + line[2:]
            if not line.strip() or line.strip()[0] == '#':
                elements.append([0, '', line])
                continue
            line = line.replace('@', '\\@')
            
            # indents
            indent = 0
            while line[indent] == ' ':
                indent += 1
                
            # multiline
            if line.strip() == '|':
                multiline_mode = True
                elements.append([indent, '- ', '|'])
                continue
            if multiline_mode == True:
                # first line indent
                multiline_mode = indent
            if multiline_mode and multiline_mode > indent:
                    multiline_mode = False
            
            if multiline_mode:
                elements.append([multiline_mode, '  ', line[multiline_mode:]])
            else:
                context = line[indent:].strip()
                if context[0] == '[':
                    context = '$' + context
                if last_i is not None and indent > elements[last_i][0]:
                    if not elements[last_i][2].endswith(':'):
                        elements[last_i][2] += ':'
                elements.append([indent, '- ', context])
                
            last_i = i
            
        return '\n'.join(' ' * indent + mid + context for indent, mid, context in elements)
    
