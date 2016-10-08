import re
import copy
from collections import namedtuple
import yaml

def _asdict(o):
    return dict(zip(o._fields, o))
    

def createReactClass(clsName, attrs, desc):
    cls = namedtuple(clsName, 'name ' + attrs)
    def render(self):
        if desc:
            print(desc.format(**_asdict(self)))
    def act(self, hunter):
        pass
            
    cls.render = render
    cls.act = act
    return cls

def createConditClass(clsName, attrs):
    cls = namedtuple(clsName, 'name ' + attrs)
    def vaildate(self, hunter, last_act = None):
        return True
    cls.vaildate = vaildate
    return cls

    
    
#class Item(namedtuple('Item', 'name desc reacts')):
#    pass

class Item(namedtuple('Item', 'name conseqs')):
    pass
    
class Option(namedtuple('Option', 'name reacts condits default')):
    _defaults = {'condits': [], 'default': False}
    
    def title(self):
        return '{name}'.format(**_asdict(self))
        
    def vaildate(self, hunter, last_act):
        allpass = True
        for condit in self.condits:
            if not condit.vaildate(hunter, last_act):
                allpass = False
        return allpass


class Quest(namedtuple('Quest', 'name reacts options')):
    _defaults = {'options': []}
    
    def avaliable_options(self, hunter):
        _avaliable_options = []
        default_option = None
        for option in self.options:
            if option.default:
                default_option = option
                continue
            if option.vaildate(hunter, None):
                _avaliable_options.append(option)
        return _avaliable_options, default_option
        
    def prompt(self, hunter):
        hunter.do_reacts(self.reacts)
            
        avaliable_options, default_option = self.avaliable_options(hunter)
        if not avaliable_options:
            if default_option and default_option.vaildate(hunter, None):
                hunter.do_reacts(default_option.reacts)
            return
        for i, option in enumerate(avaliable_options):
            print('{}. {}'.format(i+1, option.title()))
                
        sel = input('--> ')
        selected = avaliable_options[min(max(1, int(sel)), len(avaliable_options)) - 1]
        hunter.do_reacts(selected.reacts)

            
class Status(namedtuple('Status', 'name props attribs')):
    pass
    
        
class Hunter:
    def __init__(self):
        self.health = 5
        self.items = []
        self.status = []
        self.props = {'speed': 1}
        
    def pickup_item(self, item):
        self.items.append(item)
        self.do_conseqs(item.conseqs, 'pickup')
        
    def drop_item(self, item):
        self.items.remove(item)
        self.do_conseqs(item.conseqs, 'drop')
        
    def get_prop(self, name):
        p = self.props.get(name, 0)
        for st in self.status:
            p += st.props.get(name, 0)
        return p
    
    def do_reacts(self, reacts):
        for react in reacts:
            react.render()
            react.act(self)
            
    def do_conseqs(self, conseqs, result):
        for option in conseqs:
            if option.vaildate(self, result):
                self.do_reacts(option.reacts)
                
    @property
    def r(self):
        import random
        return random.random()

class Root:
    _fields = ('name', 'quests')
    def __init__(self, name, quests):
        self.quests = quests
        
''' 
class Maze:
    def __init__(self):
        pass
        
    def show_road(self):
        pass
'''
        
class DescReact(createReactClass('DescReact', 'content', '{content}')):
    pass
    
class DamageReact(createReactClass('DamageReact', 'damage', '受到{damage}傷害')):
    def act(self, hunter):
        hunter.health -= int(self.damage)
        
class GainItemReact(createReactClass('GainItemReact', 'item', '拿到{item.name}')):
    def act(self, hunter):
        hunter.items.append(self.item)

# TODO: dynamic prop
class SpeedChallengeReact(createReactClass('SpeedChallengeReact', 'level conseqs', None)):
    def act(self, hunter):
        result = int(self.level) < hunter.get_prop('speed')
        hunter.do_conseqs(self.conseqs, result)

        
react_database = {
    r'字幕$': DescReact,
    r'^> (?P<content>.*)$': DescReact,
    r'受傷$': DamageReact,
    r'受傷(?P<damage>\d+)$': DamageReact,
    r'速度檢定$': SpeedChallengeReact,
    r'速度檢定(?P<level>\d+)$': SpeedChallengeReact,
}

class AttrNumberCompCondit(createConditClass('AttrNumberCompCondit', 'attr comp value')):
    def vaildate(self, hunter, last_act):
        a, v = getattr(hunter, self.attr), float(self.value)
        if self.comp == '<':
            return a < v
        if self.comp == '>':
            return a > v
        if self.comp == '=':
            return a == v
class PassCondit(createConditClass('PassCondit', '')):
    def vaildate(self, hunter, last_act):
        return bool(last_act)
        
class FailureCondit(createConditClass('PassCondit', '')):
    def vaildate(self, hunter, last_act):
        return not bool(last_act)
        
condit_database = {
    r'^(?P<attr>[a-z_]+) (?P<comp>>|<|=) (?P<value>\d+(.\d+)?)$': AttrNumberCompCondit,
    r'通過': PassCondit,
    r'失敗': FailureCondit,
}
    


from yaml import MarkedYAMLError
class Builder:
    builder_list = []
    translate_attr_table = {
        '描述': 'desc',
    }
    from yaml.representer import Representer
    from yaml.constructor import Constructor
    yaml_representer = Representer()
    yaml_constructor = Constructor()
        
    def __init__(self, _cls, k_pattern, k_belong, **kwargs):
        self.cls = _cls
        self.k_pattern = k_pattern
        self.k_belong = k_belong
        self.ksub_cls = kwargs.get('ksub_cls', None)
        self.ksub_belong = kwargs.get('ksub_belong', None)
        self.vsub_cls = kwargs.get('vsub_cls', None)
        self.vsub_belong = kwargs.get('vsub_belong', None)
        self.vsub_spliter = kwargs.get('vsub_spliter', None)
        
    @classmethod
    def _wrap_to_node(cls, obj, ref=None):
        if not isinstance(obj, yaml.Node):
            obj = cls.yaml_representer.represent_data(obj)
        if ref:
            obj.start_mark = ref.start_mark
            obj.end_mark = ref.end_mark
        if isinstance(obj, yaml.SequenceNode):
            for v in obj.value:
                cls._wrap_to_node(v, ref)
        if isinstance(obj, yaml.MappingNode):
            for k, v in obj.value:
                cls._wrap_to_node(k, ref)
                cls._wrap_to_node(v, ref)
        return obj
        
    @classmethod
    def _unwrap_from_node(cls, node):
        if isinstance(node, yaml.Node):
            return cls.yaml_constructor.construct_object(node)
        return node
        
    @classmethod
    def _offset_mark(cls, mark, offset):
        mark = copy.deepcopy(mark)
        mark.column += offset
        mark.pointer += offset
        return mark
        
    @classmethod
    def text_match(cls, text, classmap):
        assert isinstance(text, yaml.ScalarNode)
        # regex match
        _cls = kwargs_list =  None
        for regex, match_cls in classmap.items():
            m = re.compile(regex).match(text.value)
            if m:
                _cls = match_cls
                kwargs_list = [cls._wrap_to_node({_k:_v}, text) for _k, _v in m.groupdict().items()]
                break
        return _cls, kwargs_list
    
    def build_vsub(self, value, init_kwargs):
        ref_node = value
        if self.vsub_cls:
            assert isinstance(self.vsub_cls, dict)
            for value_text in self.vsub_spliter.split(value.value):
                _cls, _kwlist = self.text_match(self._wrap_to_node(value_text, ref_node), self.vsub_cls)
                if _cls:
                    sub = self.common_from_data(_cls, value, self._wrap_to_node(_kwlist, ref_node))
                    init_kwargs.setdefault(self.vsub_belong, []).append(sub)
                else:
                    raise MarkedYAMLError(None, None, '找不到可符合的類別', ref_node.start_mark)
                    
    def build_ksub(self, key_text, init_kwargs):
        ref_node = key_text
        if self.ksub_cls:
            assert isinstance(self.ksub_cls, dict)
            _cls, _kwlist = self.text_match(key_text, self.ksub_cls)
            if _cls:
                sub = self.common_from_data(_cls, key_text, self._wrap_to_node(_kwlist, ref_node))
                init_kwargs.setdefault(self.ksub_belong, []).append(sub)
    
    def from_kvlist(self, key, values, parent_kwargs):
        assert isinstance(parent_kwargs, dict)
        assert isinstance(values, (yaml.SequenceNode, yaml.ScalarNode))
        if key.value.startswith(self.k_pattern):
            key_text = copy.copy(key)
            key_text.value = key.value[len(self.k_pattern):]
            key_text.start_mark = self._offset_mark(key.start_mark, len(self.k_pattern))
            # let title decide which class to create
            # and decide defualt kwargs
            if isinstance(self.cls, dict):
                _cls, _kwlist = self.text_match(key_text, self.cls)
                if _cls:
                    values.value.extend(_kwlist)
                else:
                    raise MarkedYAMLError(None, None, '找不到可符合的類別', key_text.start_mark)
            else:
                _cls = self.cls
                
            init_kwargs = {}
            self.build_ksub(key_text, init_kwargs)
            if isinstance(values, yaml.ScalarNode):
                self.build_vsub(values, init_kwargs)
            object = self.common_from_data(_cls, key, values, init_kwargs)
            parent_kwargs.setdefault(self.k_belong, []).append(object)
            return True
        return False
        
    @classmethod
    def global_from_kvlist(cls, key, values, parent_kwargs):
        for builder in cls.builder_list:
            if builder.from_kvlist(key, values, parent_kwargs):
                return True
        return False
    
    @classmethod
    def common_from_data(cls, target_cls, name, kwlist, init_kwargs=None):
        args = []
        build_kwargs =  copy.deepcopy(getattr(target_cls, '_defaults', {}))
        build_kwargs.update(init_kwargs or {})
        for v in kwlist.value:
            if isinstance(v, yaml.MappingNode):
                objk, objv = v.value[0]
                objk.value = cls.translate_attr_table.get(objk.value, objk.value)
                # objk, objv is constructor
                if cls.global_from_kvlist(objk, objv, build_kwargs):
                    continue
                # objk, objv is attributes
                attr = cls._unwrap_from_node(objk)
                if attr not in target_cls._fields:
                    raise MarkedYAMLError(None, None, '類別沒有這個屬性', objk.start_mark)
                build_kwargs[attr] = cls._unwrap_from_node(objv)
            else:
                if isinstance(v, yaml.ScalarNode):
                    if cls.global_from_kvlist(v, cls._wrap_to_node([], v), build_kwargs):
                        # element v is constructor
                        continue
                # element v is fixed-position attributes, maybe is array
                args.append(v)
        
        # check args and kwargs of creation
        extra = list(target_cls._fields)
        for attr in build_kwargs.keys():
            extra.remove(attr)
        if 'name' in extra:
            args = [name] + args
            
        for arg in args:
            if len(extra) == 0:
                raise MarkedYAMLError(None, None, '多餘的條目', arg.start_mark)
            extra.pop(0)
        if len(extra) > 0:
            raise MarkedYAMLError(None, None, '還有未指定的屬性: {}'.format(extra[0]), kwlist.start_mark)
            
        build_args = [cls._unwrap_from_node(arg) for arg in args]
        return target_cls(*build_args, **build_kwargs)
        
        
        
# (startswith, class, parent_attr, child_class, child_attr)
parser_class_table = [
    ('$[情結] ', Quest, 'quests', None, None),
    ('$[選項] ', Option, 'options', None, None),
    ('$[預設] ', Option, 'options', None, None),
    ('$[後果] ', Option, 'conseqs', condit_database, 'condits'),
    ('< ', react_database, 'reacts', None, None),
    ('?-', condit_database, 'condits', None, None),
    ('$[條件] ', condit_database, 'condits', None, None),
]
Builder.builder_list.extend([
    Builder(Quest, '$[情結] ', 'quests'),
    Builder(Option, '$[選項] ', 'options'),
    Builder(Option, '$[預設] ', 'options'),
    Builder(Option, '$[後果] ', 'conseqs'),
    Builder(react_database, '< ', 'reacts'),
    Builder(condit_database, '?- ', 'condits'),
    Builder(condit_database, '$[條件] ', 'condits'),

])
        
        
        
        
'''
class ClassLoader:
    translate_attr_table = {
        '描述': 'desc',
    }
    
    def __init__(self):
        from yaml.representer import Representer
        from yaml.constructor import Constructor
        self.yaml_representer = Representer()
        self.yaml_constructor = Constructor()
        
    def _wrap_to_node(self, obj, ref=None):
        if not isinstance(obj, yaml.Node):
            obj = self.yaml_representer.represent_data(obj)
        if ref:
            obj.start_mark = ref.start_mark
            obj.end_mark = ref.end_mark
        if isinstance(obj, yaml.SequenceNode):
            for v in obj.value:
                self._wrap_to_node(v, ref)
        if isinstance(obj, yaml.MappingNode):
            for k, v in obj.value:
                self._wrap_to_node(k, ref)
                self._wrap_to_node(v, ref)
        return obj
        
    def _unwrap_from_node(self, node):
        if isinstance(node, yaml.Node):
            return self.yaml_constructor.construct_object(node)
        return node
        
    def _offset_mark(self, mark, offset):
        mark = copy.deepcopy(mark)
        mark.column += offset
        mark.pointer += offset
        return mark
        
        
    def title_match(self, title, classmap, parent_node):
        # regex match
        cls = kwargs_list =  None
        for regex, match_cls in classmap.items():
            m = re.compile(regex).match(title)
            if m:
                cls = match_cls
                kwargs_list = [self._wrap_to_node({_k:_v}, parent_node) for _k, _v in m.groupdict().items()]
                break
        return cls, kwargs_list
        
    # list match
    def string_match(self, string, parent_kwargs, elements):
        assert isinstance(parent_kwargs, dict)
        assert isinstance(elements, yaml.SequenceNode)
        #if not isinstance(elements, yaml.SequenceNode):
        #    return False
        
        print(string)
        for pattern, _cls, _attr, child_class, child_attr in parser_class_table:
            title = string.value[len(pattern):]
            title_mark = self._offset_mark(string.start_mark, len(pattern))
            
            if string.value.startswith(pattern):
                if isinstance(_cls, dict):
                    # regex match
                    _cls, _kwlist = self.title_match(title, _cls, string)
                    if _cls:
                        elements.value.extend(_kwlist)
                    else:
                        raise MarkedYAMLError(None, None, '找不到可符合的類別', title_mark)
                
                _default_kwargs = copy.deepcopy(getattr(_cls, '_defaults', None))
                
                if child_class and isinstance(child_class, dict):
                    child_class, _kwlist = self.title_match(title, child_class, string)
                    if child_class:
                        child = self.common_from_data(child_class, title, self._wrap_to_node(_kwlist, string))
                        _default_kwargs.setdefault(child_attr, []).append(child)
                        
                new = self.common_from_data(_cls, title, elements, copy.deepcopy(_default_kwargs))
                parent_kwargs.setdefault(_attr, []).append(new)
                return True
                
        return False
        
    def common_from_data(self, cls, k, values, default_kwargs=None):
        if not isinstance(values, yaml.SequenceNode):
            values = self._wrap_to_node([values])
            
        # if cls == SpeedChallengeReact:
            # print(k)
            # print(values)
            # print(default_kwargs)
            
        args = []
        kwargs = getattr(cls, 'defaults', {})
        kwargs.update(default_kwargs or {})
        build_kwargs = copy.deepcopy(kwargs)
        for v in values.value:
            if isinstance(v, yaml.MappingNode):
                objk, objv = v.value[0]
                objk.value = self.translate_attr_table.get(objk.value, objk.value)
                #print(v)
                # objk, objv is constructor
                if isinstance(objv, yaml.SequenceNode) and self.string_match(objk, build_kwargs, objv):
                    continue
                if isinstance(objv, yaml.ScalarNode) and self.one_line_match(objk, build_kwargs, objv):
                    continue
                # objk, objv is attributes
                attr = self._unwrap_from_node(objk)
                if attr not in cls._fields:
                    raise MarkedYAMLError(None, None, '類別沒有這個屬性', objk.start_mark)
                build_kwargs[attr] = self._unwrap_from_node(objv)
            else:
                if isinstance(v, yaml.ScalarNode):
                    if self.string_match(v, build_kwargs, self._wrap_to_node([], v)):
                        # element v is constructor
                        continue
                # element v is fixed-position attributes, maybe is array
                args.append(v)
        
        # check args and kwargs of creation
        extra = list(cls._fields)
        extra.remove('name')
        for attr in build_kwargs.keys():
            extra.remove(attr)
        for arg in args:
            if len(extra) == 0:
                raise MarkedYAMLError(None, None, '多餘的條目', arg.start_mark)
            extra.pop()
        if len(extra) > 0:
            raise MarkedYAMLError(None, None, '還有未指定的屬性: {}'.format(extra[0]), values.start_mark)
            
        build_args = [k] + [self._unwrap_from_node(arg) for arg in args]
        return cls(*build_args, **build_kwargs)
        
    def parser(self, data):
        root = self.common_from_data(Root, None, data)
        return root
'''

        

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

class ProcessLoader(yaml.Loader):
    def __init__(self, filename):
        self.filename = filename
        with open('sample2.yaml', encoding='utf-8') as fp:
            stream = self.preprocess(fp.read())
        Reader.__init__(self, stream)
        self.name = self.filename
        
        Scanner.__init__(self)
        Parser.__init__(self)
        Composer.__init__(self)
        Constructor.__init__(self)
        Resolver.__init__(self)
        
    def preprocess(self, text):
        new_lines = []
        for line in text.split('\n'):
            if not line.strip() or line.strip()[0] == '#':
                continue
            white_count = 0
            for t in line:
                if t == ' ':
                    white_count += 1
                else:
                    break
            
            new_lines.append(' ' * white_count + '- ' + line[white_count:])
        return '\n'.join(new_lines)
    
def parse(filename):
    data = yaml.compose(filename, ProcessLoader)
    #root = self.common_from_data(Root, None, data)
    #root = ClassLoader().parser(data)
    root = Builder.common_from_data(Root, None, data)
    return root
    
root = parse('sample2.yaml')
quests = root.quests
h = Hunter()
quests[0].prompt(h)
