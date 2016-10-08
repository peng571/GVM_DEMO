import copy


class MatchError(Exception):
    def __init__(self, pos, c, needs):
        self.pos = pos
        self.c = c
        self.needs = needs
        
    def __str__(self):
        if self.needs:
            return 'on pos {}, need {}, but "{}"'.format(self.pos, self.needs, self.c)
        else:
            return 'on pos {}, not allow "{}"'.format(self.pos, self.c)
        
        
class Regex(object):
    _id = 0
    def __init__(self, empty):
        # empty denotes whether the regular expression
        # can match the empty string
        self.empty = empty
        # mark that is shifted through the regex
        self.marked = False
        self.children = []
        self.id = self.__class__._id
        self.__class__._id += 1
        
    def reset(self):
        """ reset all marks in the regular expression """
        for c in self.children:
            c.reset()
        self.marked = False
        
    def shift(self, c, mark):
        """ shift the mark from left to right, matching character c."""
        # _shift is implemented in the concrete classes
        marked = self._shift(c, mark)
        self.marked = marked
        return marked
        
    def __str__(self):
        lines = ['{} {} {}'.format(self.id, self.__class__.__name__, self.marked)]
        for c in self.children:
            lines.extend('  ' + line for line in str(c).split('\n'))
        return '\n'.join(lines)

        
    def match(self, s):
        if not s:
            return self.empty
        
        needs_list = []
        last_match_pos = None
        needs_list.append(self.detect(True))
        prev_result = result = self.shift(s[0], True)
        # print(s[0], needs_list[0])
        # print(self)
        
        for i, c in enumerate(s[1:]):
            needs_list.append(self.detect(False))
            result = self.shift(c, False)
            if prev_result and not result:
                last_match_pos = i
            prev_result = result
            # print(c, needs_list[i+1])
            # print(self)
            
        error_pos = None
        if last_match_pos is None:
            for i, needs in reversed(list(enumerate(needs_list))):
                if needs != []:
                    error_pos = i
                    break
        elif last_match_pos != len(s) - 1:
            error_pos = last_match_pos + 1
            
        if error_pos:
            raise MatchError(error_pos, s[error_pos], needs_list[error_pos])
        
        self.reset()
        return result
        
class Consumer:
    def __init__(self, c):
        self.c = c
        
    def match(self, c):
        return c == self.c
        
        
class Char(Regex):
    def __init__(self, c, empty=False):
        super().__init__(empty=empty)
        self.consumer = Consumer(c)

    def _shift(self, c, mark):
        return mark and self.consumer.match(c)
        
    def detect(self, mark):
        if mark:
            return [self.consumer.c]
        return []
        
    def __str__(self):
        return '{} {} {} "{}"'.format(self.id, self.__class__.__name__, self.marked, self.c)
        
class Repetition(Regex):
    def __init__(self, child):
        super().__init__(empty=True)
        self.children = [child]

    def _shift(self, c, mark):
        return self.children[0].shift(c, mark or self.marked)
    
    def detect(self, mark):
        return self.children[0].detect(mark or self.marked)
        
class Alternative(Regex):
    def __init__(self, *children):
        super().__init__(empty=any(node.empty for node in children))
        self.children = children
        
    def _shift(self, c, mark):
        marked = False
        for node in self.children:
            if marked:
                node.reset()
            if not marked:
                marked = node.shift(c, mark)
        return marked
        
    def detect(self, mark):
        return sum([node.detect(mark) for node in self.children], [])

class Binary(Regex):
    
    def __init__(self, left, right):
        super().__init__(empty=left.empty and right.empty)
        self.children = [left, right]
        
        
    def _shift(self, c, mark):
        old_marked_left = self.children[0].marked
        marked_left = self.children[0].shift(c, mark)
        marked_right = self.children[1].shift(
            c, old_marked_left or (mark and self.children[0].empty))
        return (marked_left and self.children[1].empty) or marked_right
        
    def detect(self, mark):
        detect_left = self.children[0].detect(mark)
        detect_right = self.children[1].detect(self.children[0].marked or (mark and self.children[0].empty))
        return detect_left + detect_right
            
def Sequence(*regexs):
    assert len(regexs) > 0
    if len(regexs) == 1:
        return regexs[0]
    return Binary(Sequence(*regexs[:-1]), regexs[-1])
    
def Optional(regex):
    opt = copy.deepcopy(regex)
    opt.empty = True
    return opt
    
def Ranged(regex, min=0, max=None):
    subs = []
    for i in range(min):
        subs.append(copy.deepcopy(regex))
    if max is None:
        subs.append(Repetition(copy.deepcopy(regex)))
    else:
        for i in range(max-min):
            subs.append(Optional(regex))
    return Sequence(*subs)

tree = Ranged(Sequence(Char('a')), 3, 4)
tree = Sequence(Repetition(Sequence(Char('a', empty=True), Alternative(Char('b'), Char('e')), Char('c'))), Char('d'))
print(tree.match('bcdqp'))

